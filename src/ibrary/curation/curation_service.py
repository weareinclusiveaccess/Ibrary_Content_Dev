"""UDL content curation service — RAG flow with OpenAI LLM."""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import (
    MAX_CONTEXT_TOKENS,
    OPENAI_API_KEY,
    OPENAI_CURATION_MODEL,
    OPENAI_CURATION_REASONING_EFFORT,
)
from ibrary.curation.curated_postgres import upsert_curated_payloads
from ibrary.curation.prompts import (
    CURATION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    get_prompt_version,
)
from ibrary.curation.schemas import CuratedModule
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.db import get_session

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3


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


def alignment_matches(alignment: dict, unit_id: str) -> list[dict]:
    """Resolve chunk matches for a unit from alignment JSON (new or legacy format)."""
    entry = alignment.get(unit_id)
    if entry is None:
        return []
    if isinstance(entry, list):
        return entry
    if isinstance(entry, dict):
        m = entry.get("matches")
        if isinstance(m, list):
            return m
    return []


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


def _call_llm(system: str, user: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            create_kwargs: dict = {
                "model": OPENAI_CURATION_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
            }
            if OPENAI_CURATION_REASONING_EFFORT:
                create_kwargs["reasoning_effort"] = OPENAI_CURATION_REASONING_EFFORT
            else:
                create_kwargs["temperature"] = 0.3
            resp = client.chat.completions.create(**create_kwargs)
            text = resp.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as exc:
            logger.warning("llm_retry", attempt=attempt, error=str(exc))
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF**attempt)
    return {}


def _format_curriculum_activity_list(items: list[str]) -> str:
    """Render curriculum activity strings for the user prompt."""
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        return "(none listed in curriculum for this topic)"
    return "\n".join(f"- {line}" for line in cleaned)


def _coerce_str_list(val: object) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return []


def curate_unit(
    unit: CurriculumUnit,
    aligned_chunk_ids: list[str],
    *,
    alignment_matches: list[dict],
) -> CuratedModule | None:
    """Generate UDL-curated content for one curriculum unit via RAG."""
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

    user_prompt = CURATION_PROMPT_TEMPLATE.format(
        class_name=unit.class_name,
        theme=unit.theme,
        theme_number=unit.theme_number,
        topic_number=unit.topic_number,
        topic=unit.topic,
        subtopic=unit.content_text,
        objectives=objectives,
        curriculum_student_activities=curriculum_student_activities,
        curriculum_teacher_activities=curriculum_teacher_activities,
        alignment_scores=alignment_scores,
        textbook_content=textbook_context,
    )

    try:
        result = _call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.error("curation_failed", unit_id=unit.curriculum_unit_id, error=str(exc))
        return None

    return CuratedModule(
        curriculum_unit_id=unit.curriculum_unit_id,
        subject="Biology",
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
        accessibility_checklist=_coerce_str_list(result.get("accessibility_checklist")),
        textbook_chunk_refs=aligned_chunk_ids,
        model_version=_curation_model_version_label(),
        prompt_version=get_prompt_version(),
    )


def curate_all(
    units: list[CurriculumUnit],
    alignment: dict,
    *,
    resume_from: set[str] | None = None,
) -> list[CuratedModule]:
    """Run curation for all units.  Supports --resume by skipping already-curated."""
    modules: list[CuratedModule] = []
    for unit in units:
        if resume_from and unit.curriculum_unit_id in resume_from:
            continue

        matches = alignment_matches(alignment, unit.curriculum_unit_id)
        if not matches:
            logger.warning("no_alignment_skip", unit_id=unit.curriculum_unit_id)
            continue

        chunk_ids = [m["chunk_id"] for m in matches if not m.get("needs_review")]
        if not chunk_ids:
            chunk_ids = [m["chunk_id"] for m in matches]

        module = curate_unit(unit, chunk_ids, alignment_matches=matches)
        if module:
            modules.append(module)
    return modules


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
        d = mod.model_dump(by_alias=True)
        by_id[d["curriculum_unit_id"]] = d
    return [by_id[k] for k in sorted(by_id.keys())]


def save_curated(
    modules: list[CuratedModule],
    output_dir: str | Path,
    *,
    merge_existing: bool = True,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "curated_content.json"
    had_file = path.is_file()
    if merge_existing and had_file:
        existing = load_curated_json_array(path)
        data = merge_curated_payloads(existing, modules)
    else:
        data = [m.model_dump(by_alias=True) for m in modules]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    upsert_curated_payloads(data)
    logger.info(
        "curated_saved",
        path=str(path),
        written_modules=len(modules),
        total_modules=len(data),
        merged_from_existing=merge_existing and had_file,
    )
    return path
