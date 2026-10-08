"""UDL content curation service — RAG flow with OpenAI LLM."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import (
    CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS,
    MAX_CONTEXT_TOKENS,
    OPENAI_CURATION_MODEL,
    OPENAI_CURATION_REASONING_EFFORT,
    PIPELINE_SUBJECT,
    PIPELINE_VERSION,
    USE_CURATION_ORCHESTRATOR,
)
from ibrary.alignment.matches import alignment_matches
from ibrary.curation.curated_postgres import upsert_curated_payloads
from ibrary.curation.prompts import (
    format_curation_prompt,
    format_system_prompt,
    get_prompt_version,
)
from ibrary.curation.schemas import CuratedModule, module_for_json_export
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.db import get_session

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
STATUS_CURRICULUM_ONLY = "draft_curriculum_only"
_CURRICULUM_ONLY_REVIEW_NOTE = (
    "Generated without textbook excerpts (curriculum-only); verify accuracy before publish."
)
_CURRICULUM_ONLY_ALIGNMENT = (
    "No textbook chunks used — curriculum-only module "
    "(no excerpts passed relevance filtering)."
)
_CURRICULUM_ONLY_TEXTBOOK = (
    "No textbook excerpts are available for this subtopic. "
    "Write from the official curriculum and standard secondary-level knowledge only. "
    "Do not claim specific textbook figures, captions, or page references. "
    "State uncertainty where appropriate."
)


def load_curated_json_array(path: str | Path) -> list:
    """Load ``curated_content.json``. Missing, empty, or invalid JSON → []."""
    p = Path(path)
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("curated_json_invalid", path=str(p))
        return []
    if not isinstance(data, list):
        logger.warning("curated_json_not_array", path=str(p))
        return []
    return data
RETRY_BACKOFF = 2


def _fetch_chunk_rows_ordered(chunk_ids: list[str]) -> list[dict]:
    """Fetch chunk rows from PostgreSQL, preserving ``chunk_ids`` order."""
    if not chunk_ids:
        return []
    session = get_session()
    try:
        placeholders = ", ".join(f":id{i}" for i in range(len(chunk_ids)))
        params = {f"id{i}": cid for i, cid in enumerate(chunk_ids)}
        rows = session.execute(
            sa_text(
                f"SELECT chunk_id, title, content FROM textbook_chunks "
                f"WHERE chunk_id IN ({placeholders})"
            ),
            params,
        ).fetchall()
        by_id = {r.chunk_id: r for r in rows}
        return [
            {"chunk_id": cid, "title": by_id[cid].title, "content": by_id[cid].content}
            for cid in chunk_ids
            if cid in by_id
        ]
    finally:
        session.close()


def _attach_alignment_metadata(chunks: list[dict], alignment_matches: list[dict]) -> list[dict]:
    by_id = {m["chunk_id"]: m for m in alignment_matches}
    out: list[dict] = []
    for ch in chunks:
        m = by_id.get(ch["chunk_id"], {})
        out.append({
            **ch,
            "alignment_score": m.get("score"),
            "needs_review": m.get("needs_review", False),
        })
    return out


def _format_alignment_scores_for_chunks(chunk_ids: list[str], alignment_matches: list[dict]) -> str:
    """Human-readable block listing similarity per retrieved chunk (for the user prompt)."""
    by_id = {m["chunk_id"]: m for m in alignment_matches}
    lines = [
        "Each value is embedding similarity between this curriculum unit and the textbook chunk "
        "(higher ≈ closer match). Use this to judge how much to trust each excerpt.",
    ]
    for cid in chunk_ids:
        m = by_id.get(cid)
        if not m:
            lines.append(f"- `{cid}`: *(not present in alignment report)*")
            continue
        sc = m.get("score", "n/a")
        tit = m.get("title", "")
        nr = m.get("needs_review", False)
        suffix = " — **needs_review (weak match)**" if nr else ""
        lines.append(f"- `{cid}`: **{sc}** — *{tit}*{suffix}")
    return "\n".join(lines)


def _truncate_context(chunks: list[dict], max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    """Concatenate chunk content, truncating to stay within token budget.

    Rough estimate: 1 token ≈ 4 characters.
    """
    max_chars = max_tokens * 4
    parts: list[str] = []
    total = 0
    for chunk in chunks:
        score_note = ""
        if chunk.get("alignment_score") is not None:
            score_note = f" *(curriculum↔textbook similarity: {chunk['alignment_score']}"
            if chunk.get("needs_review"):
                score_note += "; flagged **needs_review**"
            score_note += ")*"
        header = f"### {chunk['title']}{score_note}\n- `chunk_id`: `{chunk['chunk_id']}`\n"
        content = chunk["content"]
        available = max_chars - total - len(header)
        if available <= 0:
            break
        if len(content) > available:
            content = content[:available] + "\n[... truncated]"
        parts.append(header + content)
        total += len(header) + len(content)
    return "\n\n".join(parts)


def _curation_model_version_label() -> str:
    if OPENAI_CURATION_REASONING_EFFORT:
        return f"{OPENAI_CURATION_MODEL};reasoning={OPENAI_CURATION_REASONING_EFFORT}"
    return OPENAI_CURATION_MODEL


def _call_llm(
    system: str,
    user: str,
    *,
    metadata: dict | None = None,
) -> dict:
    from ibrary.llm.client import chat_completion_json

    extra: dict = {}
    if OPENAI_CURATION_REASONING_EFFORT:
        extra["reasoning_effort"] = OPENAI_CURATION_REASONING_EFFORT
    else:
        extra["temperature"] = 0.3
    return chat_completion_json(
        component="curation",
        model=OPENAI_CURATION_MODEL,
        system=system,
        user=user,
        max_retries=MAX_RETRIES,
        retry_backoff=RETRY_BACKOFF,
        extra_create_kwargs=extra,
        metadata=metadata,
    )


def _format_curriculum_activity_list(items: list[str]) -> str:
    """Render curriculum activity strings for the user prompt."""
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        return "(none listed in curriculum for this topic)"
    return "\n".join(f"- {line}" for line in cleaned)


def _coerce_dict_list(val: object) -> list[dict]:
    if not isinstance(val, list):
        return []
    return [item for item in val if isinstance(item, dict)]


def _coerce_str_list(val: object) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return []


def resolve_curation_excerpts(
    unit_id: str,
    excerpts: list[dict] | None = None,
) -> tuple[list[dict], bool] | None:
    """Resolve v2 excerpts; return (excerpts, curriculum_only) or None to skip the unit."""
    if excerpts is None:
        from ibrary.relevance.context import build_curation_excerpts

        excerpts = build_curation_excerpts(unit_id)
    if excerpts:
        return excerpts, False
    if CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS:
        logger.warning("curriculum_only_fallback", unit_id=unit_id)
        return [], True
    logger.warning("no_relevant_excerpts", unit_id=unit_id)
    return None


def curate_unit(
    unit: CurriculumUnit,
    aligned_chunk_ids: list[str],
    *,
    alignment_matches: list[dict],
    excerpt_chunks: list[dict] | None = None,
    curriculum_only: bool = False,
) -> CuratedModule | None:
    """Generate UDL-curated content for one curriculum unit via RAG."""
    if curriculum_only:
        rows: list[dict] = []
        aligned_chunk_ids = []
        textbook_context = _CURRICULUM_ONLY_TEXTBOOK
        alignment_scores = _CURRICULUM_ONLY_ALIGNMENT
    elif excerpt_chunks:
        rows = excerpt_chunks
        aligned_chunk_ids = [r["chunk_id"] for r in rows]
    else:
        if not aligned_chunk_ids:
            logger.warning("skipped_no_chunks", unit_id=unit.curriculum_unit_id)
            return None
        rows = _fetch_chunk_rows_ordered(aligned_chunk_ids)
        if not rows:
            logger.warning("skipped_empty_chunks", unit_id=unit.curriculum_unit_id)
            return None

    chunks = _attach_alignment_metadata(rows, alignment_matches)
    textbook_context = _truncate_context(chunks)
    alignment_scores = _format_alignment_scores_for_chunks(aligned_chunk_ids, alignment_matches)
    objectives = "\n".join(f"- {o}" for o in unit.performance_objectives) or "- (none specified)"
    curriculum_student_activities = _format_curriculum_activity_list(unit.student_activities)
    curriculum_teacher_activities = _format_curriculum_activity_list(unit.teachers_activities)

    user_prompt = format_curation_prompt(
        subject=PIPELINE_SUBJECT,
        class_name=unit.class_name,
        theme=unit.theme,
        theme_number=str(unit.theme_number),
        topic_number=str(unit.topic_number),
        topic=unit.topic,
        subtopic=unit.content_text,
        objectives=objectives,
        curriculum_student_activities=curriculum_student_activities,
        curriculum_teacher_activities=curriculum_teacher_activities,
        alignment_scores=alignment_scores,
        textbook_content=textbook_context,
    )

    try:
        result = _call_llm(
            format_system_prompt(PIPELINE_SUBJECT),
            user_prompt,
            metadata={"curriculum_unit_id": unit.curriculum_unit_id},
        )
    except Exception as exc:
        logger.error("curation_failed", unit_id=unit.curriculum_unit_id, error=str(exc))
        return None

    checklist = _coerce_str_list(result.get("accessibility_checklist"))
    if curriculum_only and _CURRICULUM_ONLY_REVIEW_NOTE not in checklist:
        checklist = [_CURRICULUM_ONLY_REVIEW_NOTE, *checklist]

    return CuratedModule(
        curriculum_unit_id=unit.curriculum_unit_id,
        subject=PIPELINE_SUBJECT,
        **{"class": unit.class_name},
        theme=unit.theme,
        theme_number=unit.theme_number,
        topic_number=unit.topic_number,
        subtopic=unit.content_text,
        title=result.get("title", unit.content_text),
        learning_objectives=result.get("learning_objectives", unit.performance_objectives),
        curated_content=result.get("curated_content", ""),
        key_takeaways=result.get("key_takeaways", []),
        glossary_terms=result.get("glossary_terms", {}),
        student_activities=_coerce_str_list(result.get("student_activities")),
        teacher_activities=_coerce_str_list(result.get("teacher_activities")),
        accessibility_checklist=checklist,
        textbook_chunk_refs=aligned_chunk_ids,
        image_placeholders=_coerce_dict_list(result.get("image_placeholders")),
        formula_placeholders=_coerce_dict_list(result.get("formula_placeholders")),
        textbook_grounded=not curriculum_only,
        status=STATUS_CURRICULUM_ONLY if curriculum_only else "draft",
        model_version=_curation_model_version_label(),
        prompt_version=get_prompt_version(),
    )


def curate_unit_via_orchestrator(
    unit: CurriculumUnit,
    alignment: dict,
    *,
    excerpt_chunks: list[dict] | None = None,
) -> CuratedModule | None:
    """Run PipelineOrchestrator curate DAG for one unit (v2 excerpt path)."""
    from ibrary.pipeline.context import PipelineContext
    from ibrary.pipeline.orchestrator import create_orchestrator

    matches = alignment_matches(alignment, unit.curriculum_unit_id)
    if not matches:
        logger.warning("no_alignment_skip", unit_id=unit.curriculum_unit_id)
        return None

    curriculum_only = False
    excerpts = excerpt_chunks
    if excerpts is None and int(os.getenv("PIPELINE_VERSION", str(PIPELINE_VERSION))) >= 2:
        resolved = resolve_curation_excerpts(unit.curriculum_unit_id)
        if resolved is None:
            return None
        excerpts, curriculum_only = resolved

    ctx = PipelineContext(
        curriculum_unit_id=unit.curriculum_unit_id,
        unit=unit,
        alignment_matches=matches,
        excerpt_chunks=excerpts or [],
        curriculum_only=curriculum_only,
    )
    ctx = create_orchestrator().curate_unit(ctx)
    if ctx.errors:
        logger.warning(
            "orchestrator_errors",
            unit_id=unit.curriculum_unit_id,
            errors=ctx.errors,
        )
    return ctx.curated_module


def _curate_one_unit(
    unit: CurriculumUnit,
    alignment: dict,
) -> CuratedModule | None:
    """Curation for a single unit (orchestrator or direct)."""
    pipeline_v = int(os.getenv("PIPELINE_VERSION", str(PIPELINE_VERSION)))
    use_orch = USE_CURATION_ORCHESTRATOR and pipeline_v >= 2

    if use_orch:
        return curate_unit_via_orchestrator(unit, alignment)

    matches = alignment_matches(alignment, unit.curriculum_unit_id)
    if not matches:
        logger.warning("no_alignment_skip", unit_id=unit.curriculum_unit_id)
        return None

    if pipeline_v >= 2:
        resolved = resolve_curation_excerpts(unit.curriculum_unit_id)
        if resolved is None:
            return None
        excerpts, curriculum_only = resolved
        return curate_unit(
            unit,
            [],
            alignment_matches=matches,
            excerpt_chunks=excerpts or None,
            curriculum_only=curriculum_only,
        )

    chunk_ids = [m["chunk_id"] for m in matches if not m.get("needs_review")]
    if not chunk_ids:
        chunk_ids = [m["chunk_id"] for m in matches]
    return curate_unit(unit, chunk_ids, alignment_matches=matches)


def load_curated_unit_ids(path: str | Path) -> set[str]:
    """Unit ids present in ``curated_content.json`` (empty/invalid file → empty set)."""
    return {
        m["curriculum_unit_id"]
        for m in load_curated_json_array(path)
        if isinstance(m, dict) and m.get("curriculum_unit_id")
    }


def curate_all(
    units: list[CurriculumUnit],
    alignment: dict,
    *,
    resume_from: set[str] | None = None,
    output_dir: str | Path | None = None,
    merge_existing: bool = True,
) -> int:
    """Run curation for all units; persist each module immediately when ``output_dir`` is set.

    Returns the number of modules saved this run. Does not retain all modules in memory.
    """
    out = Path(output_dir) if output_dir is not None else None
    if out is not None and not merge_existing:
        out.mkdir(parents=True, exist_ok=True)
        (out / "curated_content.json").write_text("[]", encoding="utf-8")

    saved = 0
    for unit in units:
        if resume_from and unit.curriculum_unit_id in resume_from:
            continue

        module = _curate_one_unit(unit, alignment)
        if not module:
            continue
        if out is not None:
            append_curated_module(module, out, merge_existing=True)
            saved += 1
        else:
            raise ValueError("curate_all requires output_dir for incremental persistence")
    if out is not None:
        logger.info("curate_all_complete", saved=saved, output_dir=str(out))
    return saved


def select_units_for_curation(
    units: list[CurriculumUnit],
    *,
    curate_theme: int | None = None,
    curate_topic: int | None = None,
    curate_unit_ids: list[str] | None = None,
) -> list[CurriculumUnit]:
    """Subset units for partial curation. ``curate_unit_ids`` wins over theme/topic."""
    if curate_unit_ids:
        wanted = frozenset(curate_unit_ids)
        out = [u for u in units if u.curriculum_unit_id in wanted]
        found = {u.curriculum_unit_id for u in out}
        missing = sorted(wanted - found)
        if missing:
            raise ValueError(f"Unknown curriculum_unit_id(s): {missing}")
        return out
    if curate_theme is not None and curate_topic is not None:
        return [u for u in units if u.theme_number == curate_theme and u.topic_number == curate_topic]
    if curate_topic is not None:
        return [u for u in units if u.topic_number == curate_topic]
    if curate_theme is not None:
        return [u for u in units if u.theme_number == curate_theme]
    return list(units)


def merge_curated_payloads(
    existing: list[dict],
    new_modules: list[CuratedModule],
) -> list[dict]:
    """Merge by ``curriculum_unit_id``; new rows replace old. Output sorted by unit id."""
    by_id: dict[str, dict] = {m["curriculum_unit_id"]: dict(m) for m in existing}
    for mod in new_modules:
        d = module_for_json_export(mod)
        by_id[d["curriculum_unit_id"]] = d
    return [by_id[k] for k in sorted(by_id.keys())]


def append_curated_module(
    module: CuratedModule,
    output_dir: str | Path,
    *,
    merge_existing: bool = True,
) -> Path:
    """Upsert one module to Postgres and merge into ``curated_content.json``."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "curated_content.json"
    payload = module_for_json_export(module)
    upsert_curated_payloads([payload])

    if merge_existing:
        existing = load_curated_json_array(path)
        by_id = {
            m["curriculum_unit_id"]: dict(m)
            for m in existing
            if isinstance(m, dict) and m.get("curriculum_unit_id")
        }
        by_id[payload["curriculum_unit_id"]] = payload
        data = [by_id[k] for k in sorted(by_id.keys())]
    else:
        data = [payload]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(
        "curated_module_saved",
        path=str(path),
        unit_id=module.curriculum_unit_id,
        total_modules=len(data),
    )
    return path


def save_curated(
    modules: list[CuratedModule],
    output_dir: str | Path,
    *,
    merge_existing: bool = True,
) -> Path:
    """Save multiple modules (each persisted immediately; no batch hold in memory)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "curated_content.json"
    if not merge_existing:
        path.write_text("[]", encoding="utf-8")
    for module in modules:
        append_curated_module(module, out, merge_existing=True)
    data = load_curated_json_array(path)
    logger.info(
        "curated_saved",
        path=str(path),
        written_modules=len(modules),
        total_modules=len(data),
    )
    return path
