"""LLM judge: evaluate text against CAST UDL Guidelines v3.0 + correctness & clarity."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path

import structlog

from ibrary.config import OPENAI_MODEL, PIPELINE_SUBJECT
from ibrary.prompts.context import format_prompt, resolve_subject
from ibrary.curation.schemas import CuratedModule
from ibrary.judging.prompts import (
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_TEMPLATE,
    get_judge_prompt_version,
)
from ibrary.judging.rubric import CHECKPOINT_BY_ID, rubric_summary_for_prompt
from ibrary.judging.schemas import CheckpointScore, SubtopicJudgeInput, SubtopicJudgeResult

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2
MAX_CONTENT_CHARS = 12_000

DEFAULT_PASS_THRESHOLD = 7.0


def enrich_checkpoint_scores(scores: list[CheckpointScore]) -> list[CheckpointScore]:
    """Attach principle and measures from ``CHECKPOINT_BY_ID`` to each score row."""
    enriched: list[CheckpointScore] = []
    for cp in scores:
        meta = CHECKPOINT_BY_ID.get(cp.checkpoint_id)
        if meta:
            enriched.append(
                cp.model_copy(
                    update={
                        "principle": meta["principle"],
                        "principle_display": meta["principle_display"],
                        "cast_guideline": meta["cast_guideline"],
                        "category": meta["category"],
                        "measures": meta["measures"],
                    }
                )
            )
        else:
            enriched.append(cp)
    return enriched


def _call_judge(
    system: str,
    user: str,
    *,
    metadata: dict | None = None,
) -> dict:
    from ibrary.llm.client import chat_completion_json

    return chat_completion_json(
        component="judge",
        model=OPENAI_MODEL,
        system=system,
        user=user,
        max_retries=MAX_RETRIES,
        retry_backoff=RETRY_BACKOFF,
        extra_create_kwargs={"temperature": 0.1},
        metadata=metadata,
    )


def _format_list(items: list[str], *, empty_label: str = "(none provided)") -> str:
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        return empty_label
    return "\n".join(f"- {line}" for line in cleaned)


def _build_judge_system_prompt(subject: str | None = None) -> str:
    return format_prompt(
        JUDGE_SYSTEM_PROMPT,
        subject=resolve_subject(subject),
        rubric=rubric_summary_for_prompt(),
    )


def _build_user_prompt(inp: SubtopicJudgeInput) -> str:
    return JUDGE_USER_TEMPLATE.format(
        subject=resolve_subject(inp.subject or None),
        class_name=inp.class_name or "(not specified)",
        subtopic=inp.subtopic or "(not specified — score content on its own merits)",
        title=inp.title or "(not specified)",
        objectives=_format_list(inp.learning_objectives),
        student_activities=_format_list(inp.student_activities),
        teacher_activities=_format_list(inp.teacher_activities),
        accessibility_checklist=_format_list(inp.accessibility_checklist),
        content=inp.content[:MAX_CONTENT_CHARS],
        takeaways=_format_list(inp.key_takeaways),
        glossary=json.dumps(inp.glossary_terms, indent=2) if inp.glossary_terms else "(none)",
    )


def _compute_passed(
    raw: dict,
    *,
    threshold: float,
) -> bool:
    """Pass requires overall, correctness, and clarity at or above threshold."""
    scores = [
        float(raw.get("overall_score") or 0),
        float(raw.get("correctness_score") or 0),
        float(raw.get("clarity_score") or 0),
    ]
    return all(s >= threshold for s in scores)


def _parse_result(raw: dict, inp: SubtopicJudgeInput, *, threshold: float) -> SubtopicJudgeResult:
    cps = enrich_checkpoint_scores(
        [
            CheckpointScore.model_validate(x)
            for x in raw.get("checkpoint_scores", [])
            if isinstance(x, dict)
        ]
    )
    overall = float(raw.get("overall_score", 0) or 0)
    return SubtopicJudgeResult(
        curriculum_unit_id=inp.curriculum_unit_id,
        subject=inp.subject,
        subtopic=inp.subtopic,
        prompt_version=inp.prompt_version,
        model_version=inp.model_version,
        judge_prompt_version=get_judge_prompt_version(),
        judge_model_version=OPENAI_MODEL,
        checkpoint_scores=cps,
        representation_score=raw.get("representation_score"),
        action_expression_score=raw.get("action_expression_score"),
        engagement_score=raw.get("engagement_score"),
        correctness_score=raw.get("correctness_score"),
        correctness_notes=str(raw.get("correctness_notes") or ""),
        clarity_score=raw.get("clarity_score"),
        clarity_notes=str(raw.get("clarity_notes") or ""),
        overall_score=overall,
        passed=_compute_passed(raw, threshold=threshold),
        recommendations=list(raw.get("recommendations") or []),
    )


def evaluate_content(
    inp: SubtopicJudgeInput,
    *,
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> SubtopicJudgeResult:
    """Run UDL v3 judge on any text. Only ``inp.content`` is required."""
    system = _build_judge_system_prompt(inp.subject)
    user = _build_user_prompt(inp)
    try:
        raw = _call_judge(
            system,
            user,
            metadata={
                "curriculum_unit_id": inp.curriculum_unit_id or None,
                "subtopic": inp.subtopic or None,
            },
        )
        return _parse_result(raw, inp, threshold=threshold)
    except Exception as exc:
        logger.error(
            "judge_failed",
            unit_id=inp.curriculum_unit_id or None,
            error=str(exc),
        )
        return SubtopicJudgeResult(
            curriculum_unit_id=inp.curriculum_unit_id,
            subject=inp.subject,
            subtopic=inp.subtopic,
            prompt_version=inp.prompt_version,
            model_version=inp.model_version,
            judge_prompt_version=get_judge_prompt_version(),
            judge_model_version=OPENAI_MODEL,
            overall_score=0,
            passed=False,
            error=str(exc),
        )


def evaluate_text(
    content: str,
    *,
    subtopic: str = "",
    subject: str = "",
    class_name: str = "",
    title: str = "",
    learning_objectives: list[str] | None = None,
    student_activities: list[str] | None = None,
    teacher_activities: list[str] | None = None,
    accessibility_checklist: list[str] | None = None,
    key_takeaways: list[str] | None = None,
    glossary_terms: dict[str, str] | None = None,
    curriculum_unit_id: str = "",
    prompt_version: str = "",
    model_version: str = "",
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> SubtopicJudgeResult:
    """Convenience: judge whenever you have body text (minimal call)."""
    inp = SubtopicJudgeInput(
        content=content,
        subtopic=subtopic,
        subject=subject,
        **{"class": class_name},
        title=title,
        learning_objectives=learning_objectives or [],
        student_activities=student_activities or [],
        teacher_activities=teacher_activities or [],
        accessibility_checklist=accessibility_checklist or [],
        key_takeaways=key_takeaways or [],
        glossary_terms=glossary_terms or {},
        curriculum_unit_id=curriculum_unit_id,
        prompt_version=prompt_version,
        model_version=model_version,
    )
    return evaluate_content(inp, threshold=threshold)


def module_to_judge_input(module: CuratedModule) -> SubtopicJudgeInput:
    """Map a curated module to judge input."""
    return SubtopicJudgeInput(
        content=module.curated_content,
        subtopic=module.subtopic,
        subject=module.subject,
        **{"class": module.class_name},
        title=module.title,
        learning_objectives=list(module.learning_objectives),
        student_activities=list(module.student_activities),
        teacher_activities=list(module.teacher_activities),
        accessibility_checklist=list(module.accessibility_checklist),
        key_takeaways=list(module.key_takeaways),
        glossary_terms=dict(module.glossary_terms),
        curriculum_unit_id=module.curriculum_unit_id,
        prompt_version=module.prompt_version,
        model_version=module.model_version,
    )


def evaluate_subtopic(
    module: CuratedModule,
    *,
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> SubtopicJudgeResult:
    """Judge a ``CuratedModule`` (wrapper around ``evaluate_content``)."""
    return evaluate_content(module_to_judge_input(module), threshold=threshold)


def evaluate_subtopics(
    modules: list[CuratedModule],
    *,
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> tuple[list[SubtopicJudgeResult], list[str]]:
    """Evaluate all modules in memory; return (results, flagged unit ids below threshold)."""
    results: list[SubtopicJudgeResult] = []
    flagged: list[str] = []
    for module in modules:
        result = evaluate_subtopic(module, threshold=threshold)
        results.append(result)
        if not result.passed and module.curriculum_unit_id:
            flagged.append(module.curriculum_unit_id)
            logger.warning(
                "subtopic_below_threshold",
                unit_id=module.curriculum_unit_id,
                overall=result.overall_score,
                correctness=result.correctness_score,
                clarity=result.clarity_score,
            )
    return results, flagged


def load_evaluation_json_array(path: str | Path) -> list:
    """Load ``udl_subtopic_evaluation.json``. Missing, empty, or invalid → []."""
    p = Path(path)
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("evaluation_json_invalid", path=str(p))
        return []
    if not isinstance(data, list):
        logger.warning("evaluation_json_not_array", path=str(p))
        return []
    return data


def load_evaluation_unit_ids(path: str | Path) -> set[str]:
    return {
        r["curriculum_unit_id"]
        for r in load_evaluation_json_array(path)
        if isinstance(r, dict) and r.get("curriculum_unit_id")
    }


def iter_modules_for_judge(
    output_dir: str | Path,
    *,
    curated_filename: str = "curated_content.json",
) -> Iterator[CuratedModule]:
    """Yield curated modules from Postgres when available, else from JSON file."""
    from ibrary.curation.curation_service import load_curated_json_array
    from ibrary.curation.curated_postgres import (
        count_curated_modules_postgres,
        iter_curated_modules_from_postgres,
    )

    out = Path(output_dir)
    if count_curated_modules_postgres() > 0:
        yield from iter_curated_modules_from_postgres()
        return

    for raw in load_curated_json_array(out / curated_filename):
        if isinstance(raw, dict):
            yield CuratedModule.model_validate(raw)


def append_evaluation_result(
    result: SubtopicJudgeResult,
    output_dir: str | Path,
    *,
    merge_existing: bool = True,
    filename: str = "udl_subtopic_evaluation.json",
) -> Path:
    """Upsert one judge result to Postgres and merge into the evaluation JSON file."""
    from ibrary.judging.judge_postgres import upsert_judge_result

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    upsert_judge_result(result)
    payload = result.model_dump()

    if merge_existing:
        existing = load_evaluation_json_array(path)
        by_id = {
            r["curriculum_unit_id"]: dict(r)
            for r in existing
            if isinstance(r, dict) and r.get("curriculum_unit_id")
        }
        by_id[result.curriculum_unit_id] = payload
        data = [by_id[k] for k in sorted(by_id.keys())]
    else:
        data = [payload]

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(
        "judge_result_saved",
        path=str(path),
        unit_id=result.curriculum_unit_id,
        total=len(data),
        passed=result.passed,
    )
    return path


def evaluate_all_curated(
    output_dir: str | Path,
    *,
    threshold: float = DEFAULT_PASS_THRESHOLD,
    resume_from: set[str] | None = None,
    merge_existing: bool = True,
    replace_evaluation: bool = False,
) -> tuple[int, int]:
    """Judge every curated module; persist each result immediately. Returns (judged, flagged)."""
    out = Path(output_dir)
    eval_path = out / "udl_subtopic_evaluation.json"
    if replace_evaluation:
        out.mkdir(parents=True, exist_ok=True)
        eval_path.write_text("[]", encoding="utf-8")

    skip = resume_from if resume_from is not None else (
        set() if replace_evaluation else load_evaluation_unit_ids(eval_path)
    )
    if skip:
        logger.info("resuming_judge", already_done=len(skip))

    judged = 0
    flagged = 0
    for module in iter_modules_for_judge(out):
        uid = module.curriculum_unit_id
        if skip and uid in skip:
            continue
        result = evaluate_subtopic(module, threshold=threshold)
        append_evaluation_result(result, out, merge_existing=True)
        judged += 1
        if not result.passed:
            flagged += 1
            logger.warning(
                "subtopic_below_threshold",
                unit_id=uid,
                overall=result.overall_score,
                correctness=result.correctness_score,
                clarity=result.clarity_score,
            )

    logger.info("evaluate_all_curated_complete", judged=judged, flagged=flagged, output_dir=str(out))
    return judged, flagged


def save_evaluation_report(
    results: list[SubtopicJudgeResult],
    output_dir: str | Path,
    *,
    filename: str = "udl_subtopic_evaluation.json",
) -> Path:
    """Save multiple results (each persisted immediately)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    for result in results:
        append_evaluation_result(result, out, merge_existing=True, filename=filename)
    data = load_evaluation_json_array(path)
    logger.info("judge_report_saved", path=str(path), count=len(data))
    return path
