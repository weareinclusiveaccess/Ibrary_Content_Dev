"""LLM agent: assign topic-level POs and activities to the correct subtopic (content item)."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import structlog

from ibrary.config import (
    OPENAI_CURRICULUM_REFINE_MODEL,
    PIPELINE_SUBJECT,
    REFINE_TOPIC_PAUSE_SECONDS,
)
from ibrary.prompts.context import format_prompt
from ibrary.curriculum.refiner_schemas import (
    CurriculumRefinementReport,
    SubtopicAssignment,
    TopicRefinementResult,
)
from ibrary.curriculum.schemas import CurriculumUnit, ValidatedCurriculum

logger = structlog.get_logger(__name__)

AGENT_VERSION = "curriculum-refine-v1"
MAX_RETRIES = 5
RETRY_BACKOFF = 3

SYSTEM_PROMPT_TEMPLATE = """\
You refine {education_system} {subject} curriculum records.

Each **topic** has several **subtopics** (`content_text` items). Due to a data bug, every subtopic \
currently has the full topic-level list of performance_objectives, teachers_activities, and \
student_activities copied onto it. Your job is to assign only the items that belong to each subtopic.

Rules:
1. Match each performance_objective to the subtopic whose `content_text` it actually teaches.
2. Each objective should appear on **at most one** subtopic (usually exactly one).
3. Assign teacher and student activities by which subtopic they support (materials, specimens, tasks).
4. You may lightly fix OCR typos in strings; do **not** invent new objectives or activities.
5. Use only strings from the provided pools (minor wording cleanup allowed).
6. Empty lists are valid when nothing in the pool applies to that subtopic.
7. If pool size ≠ subtopic count, use semantic judgment (do not force 1:1 zip).
8. Return **one assignment object for every** content_index listed in the user message (no omissions).

Return JSON only:
{{
  "assignments": [
    {{
      "content_index": 0,
      "performance_objectives": ["..."],
      "teachers_activities": ["..."],
      "student_activities": ["..."],
      "rationale": "one short sentence"
    }}
  ]
}}
"""

USER_TEMPLATE = """\
**Subject:** {subject}
**Class:** {class_name}
**Theme:** {theme} (theme {theme_number})
**Topic {topic_number}:** {topic}

**Subtopics (content_index → content_text):**
{subtopics_block}

**Topic-level performance_objectives (assign each to the correct subtopic):**
{objectives_block}

**Topic-level teachers_activities:**
{teacher_block}

**Topic-level student_activities:**
{student_block}
"""


def _call_llm(
    system: str,
    user: str,
    *,
    metadata: dict | None = None,
) -> dict:
    from ibrary.llm.client import chat_completion_json

    return chat_completion_json(
        component="curriculum_refine",
        model=OPENAI_CURRICULUM_REFINE_MODEL,
        system=system,
        user=user,
        max_retries=MAX_RETRIES,
        retry_backoff=RETRY_BACKOFF,
        extra_create_kwargs={"temperature": 0.1},
        metadata=metadata,
    )


def _format_numbered(items: list[str]) -> str:
    if not items:
        return "(none)"
    return "\n".join(f"{i}. {s}" for i, s in enumerate(items))


def _format_subtopics(units: list[CurriculumUnit]) -> str:
    return "\n".join(f"{u.content_index}. {u.content_text}" for u in units)


def refine_topic_units(units: list[CurriculumUnit]) -> TopicRefinementResult:
    """Refine one topic's units (same theme_number + topic_number)."""
    if not units:
        raise ValueError("empty unit list")
    units = sorted(units, key=lambda u: u.content_index)
    head = units[0]

    user = format_prompt(
        USER_TEMPLATE,
        subject=PIPELINE_SUBJECT,
        class_name=head.class_name,
        theme=head.theme,
        theme_number=str(head.theme_number),
        topic_number=str(head.topic_number),
        topic=head.topic,
        subtopics_block=_format_subtopics(units),
        objectives_block=_format_numbered(head.performance_objectives),
        teacher_block=_format_numbered(head.teachers_activities),
        student_block=_format_numbered(head.student_activities),
    )
    raw = _call_llm(
        format_prompt(SYSTEM_PROMPT_TEMPLATE, subject=PIPELINE_SUBJECT),
        user,
        metadata={
            "theme_number": head.theme_number,
            "topic_number": head.topic_number,
            "subtopic_count": len(units),
        },
    )
    assignments_raw = raw.get("assignments") or []
    by_index: dict[int, SubtopicAssignment] = {}
    for item in assignments_raw:
        a = SubtopicAssignment.model_validate(item)
        by_index[a.content_index] = a

    assignments: list[SubtopicAssignment] = []
    for u in units:
        a = by_index.get(u.content_index)
        if a is None:
            logger.warning(
                "refine_missing_assignment",
                topic=head.topic_number,
                content_index=u.content_index,
            )
            assignments.append(
                SubtopicAssignment(
                    content_index=u.content_index,
                    rationale="LLM omitted this subtopic; left empty lists",
                )
            )
        else:
            assignments.append(a)

    return TopicRefinementResult(
        theme_number=head.theme_number,
        topic_number=head.topic_number,
        topic=head.topic,
        assignments=assignments,
    )


def apply_topic_refinement(
    units: list[CurriculumUnit],
    result: TopicRefinementResult,
) -> list[CurriculumUnit]:
    """Return updated units for this topic."""
    by_index = {a.content_index: a for a in result.assignments}
    updated: list[CurriculumUnit] = []
    for u in sorted(units, key=lambda x: x.content_index):
        a = by_index.get(u.content_index)
        if a is None:
            updated.append(u)
            continue
        updated.append(
            u.model_copy(
                update={
                    "performance_objectives": a.performance_objectives,
                    "teachers_activities": a.teachers_activities,
                    "student_activities": a.student_activities,
                }
            )
        )
    return updated


def group_units_by_topic(
    units: list[CurriculumUnit],
) -> dict[tuple[int, int], list[CurriculumUnit]]:
    groups: dict[tuple[int, int], list[CurriculumUnit]] = defaultdict(list)
    for u in units:
        groups[(u.theme_number, u.topic_number)].append(u)
    return dict(groups)


def load_completed_topic_keys(report_path: str | Path) -> set[tuple[int, int]]:
    """Topics already present in a saved refinement report."""
    path = Path(report_path)
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        report = CurriculumRefinementReport.model_validate(raw)
    except (json.JSONDecodeError, ValueError):
        return set()
    return {(r.theme_number, r.topic_number) for r in report.topic_results}


def load_refinement_report(report_path: str | Path) -> CurriculumRefinementReport | None:
    path = Path(report_path)
    if not path.is_file():
        return None
    try:
        return CurriculumRefinementReport.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, ValueError):
        return None


def refine_validated_curriculum(
    validated: ValidatedCurriculum,
    *,
    topic_keys: list[tuple[int, int]] | None = None,
    output_dir: str | Path | None = None,
    resume: bool = False,
    report_path: str | Path | None = None,
) -> tuple[ValidatedCurriculum, CurriculumRefinementReport]:
    """Refine all units (or selected topics) and return updated curriculum + report.

    When ``output_dir`` is set, saves after **each** topic so a connection error does not
    lose progress. Use ``resume=True`` to skip topics already in ``report_path``.
    """
    out_dir = Path(output_dir) if output_dir else None
    rpt_path = Path(report_path) if report_path else (out_dir / "curriculum_refinement_report.json" if out_dir else None)

    groups = group_units_by_topic(validated.units)
    if topic_keys is not None:
        wanted = set(topic_keys)
        groups = {k: v for k, v in groups.items() if k in wanted}

    unit_by_id = {u.curriculum_unit_id: u for u in validated.units}
    prior_results: list[TopicRefinementResult] = []
    if resume and rpt_path:
        prior = load_refinement_report(rpt_path)
        if prior:
            prior_results = list(prior.topic_results)
            for pr in prior_results:
                key = (pr.theme_number, pr.topic_number)
                if key not in groups:
                    continue
                refined_units = apply_topic_refinement(groups[key], pr)
                for u in refined_units:
                    unit_by_id[u.curriculum_unit_id] = u

    completed = {(r.theme_number, r.topic_number) for r in prior_results}
    topic_results: list[TopicRefinementResult] = list(prior_results)
    units_updated = len(unit_by_id)

    sorted_keys = sorted(groups.keys())
    for i, (theme_num, topic_num) in enumerate(sorted_keys):
        if (theme_num, topic_num) in completed:
            logger.info("refine_skip_completed", theme_number=theme_num, topic_number=topic_num)
            continue

        topic_units = groups[(theme_num, topic_num)]
        logger.info(
            "curriculum_refine_topic",
            theme_number=theme_num,
            topic_number=topic_num,
            subtopics=len(topic_units),
        )
        try:
            result = refine_topic_units(topic_units)
        except Exception:
            if out_dir:
                partial = ValidatedCurriculum(
                    units=sorted(
                        unit_by_id.values(),
                        key=lambda u: (u.theme_number, u.topic_number, u.content_index),
                    ),
                    topics=validated.topics,
                    unmapped_topics=validated.unmapped_topics,
                )
                partial_report = CurriculumRefinementReport(
                    agent_version=AGENT_VERSION,
                    model=OPENAI_CURRICULUM_REFINE_MODEL,
                    topics_refined=len(topic_results),
                    units_updated=len(unit_by_id),
                    topic_results=topic_results,
                )
                save_refinement_outputs(partial, partial_report, out_dir)
                logger.error(
                    "refine_failed_partial_saved",
                    theme_number=theme_num,
                    topic_number=topic_num,
                )
            raise

        topic_results = [r for r in topic_results if (r.theme_number, r.topic_number) != (theme_num, topic_num)]
        topic_results.append(result)
        refined_units = apply_topic_refinement(topic_units, result)
        for u in refined_units:
            unit_by_id[u.curriculum_unit_id] = u

        refined_units_list = sorted(
            unit_by_id.values(),
            key=lambda u: (u.theme_number, u.topic_number, u.content_index),
        )
        report = CurriculumRefinementReport(
            agent_version=AGENT_VERSION,
            model=OPENAI_CURRICULUM_REFINE_MODEL,
            topics_refined=len(topic_results),
            units_updated=len(unit_by_id),
            topic_results=topic_results,
        )
        validated_out = ValidatedCurriculum(
            units=refined_units_list,
            topics=validated.topics,
            unmapped_topics=validated.unmapped_topics,
        )
        if out_dir:
            save_refinement_outputs(validated_out, report, out_dir)

        if i + 1 < len(sorted_keys) and REFINE_TOPIC_PAUSE_SECONDS > 0:
            time.sleep(REFINE_TOPIC_PAUSE_SECONDS)

    refined_units_list = sorted(
        unit_by_id.values(),
        key=lambda u: (u.theme_number, u.topic_number, u.content_index),
    )
    report = CurriculumRefinementReport(
        agent_version=AGENT_VERSION,
        model=OPENAI_CURRICULUM_REFINE_MODEL,
        topics_refined=len(topic_results),
        units_updated=len(unit_by_id),
        topic_results=topic_results,
    )
    return (
        ValidatedCurriculum(
            units=refined_units_list,
            topics=validated.topics,
            unmapped_topics=validated.unmapped_topics,
        ),
        report,
    )


def save_refinement_outputs(
    validated: ValidatedCurriculum,
    report: CurriculumRefinementReport,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    validated_path = out / "curriculum_validated.json"
    report_path = out / "curriculum_refinement_report.json"
    validated_path.write_text(validated.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        "curriculum_refinement_saved",
        validated=str(validated_path),
        report=str(report_path),
    )
    return validated_path, report_path
