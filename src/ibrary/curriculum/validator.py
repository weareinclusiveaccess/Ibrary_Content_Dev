"""Validate curriculum JSON and assign curriculum_unit_ids (topics 1-6 only)."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from ibrary.curriculum.schemas import CurriculumTopic, CurriculumUnit, ValidatedCurriculum

logger = structlog.get_logger(__name__)

VALID_TOPIC_RANGE = range(1, 7)
VALID_CLASS = "SSS 1"


def _make_unit_id(theme_number: int, topic_number: int, content_index: int) -> str:
    return f"bio_sss1_theme{theme_number}_topic{topic_number}_content{content_index}"


def validate_curriculum(
    json_path: str | Path,
    *,
    class_filter: str = VALID_CLASS,
    topic_range: range = VALID_TOPIC_RANGE,
) -> ValidatedCurriculum:
    """Load, filter, and validate the structured curriculum JSON.

    Returns a ValidatedCurriculum with per-subtopic units and topic summaries.
    """
    path = Path(json_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    curriculum_items: list[dict] = raw.get("curriculum", [])

    topics: list[CurriculumTopic] = []
    units: list[CurriculumUnit] = []
    unmapped: list[dict] = []

    for item in curriculum_items:
        cls = item.get("class", "")
        topic_num = item.get("topic_number")

        if cls != class_filter or topic_num not in topic_range:
            unmapped.append({"topic_number": topic_num, "class": cls, "topic": item.get("topic")})
            continue

        topic = CurriculumTopic.model_validate(item)
        topics.append(topic)

        for idx, content_text in enumerate(topic.content):
            unit_id = _make_unit_id(topic.theme_number, topic.topic_number, idx)
            unit = CurriculumUnit(
                curriculum_unit_id=unit_id,
                **{
                    "class": topic.class_name,
                    "theme": topic.theme,
                    "theme_number": topic.theme_number,
                    "topic_number": topic.topic_number,
                    "topic": topic.topic,
                    "content_index": idx,
                    "content_text": content_text,
                    "performance_objectives": topic.performance_objectives,
                    "teachers_activities": topic.teachers_activities,
                    "student_activities": topic.student_activities,
                },
            )
            units.append(unit)

    logger.info(
        "curriculum_validated",
        topics=len(topics),
        units=len(units),
        unmapped=len(unmapped),
    )
    return ValidatedCurriculum(units=units, topics=topics, unmapped_topics=unmapped)


def save_validated(result: ValidatedCurriculum, output_dir: str | Path) -> Path:
    """Persist validation output to JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "curriculum_validated.json"
    path.write_text(result.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
    report = out / "curriculum_extraction_report.json"
    report.write_text(
        json.dumps({"unmapped_topics": result.unmapped_topics}, indent=2),
        encoding="utf-8",
    )
    logger.info("curriculum_saved", path=str(path))
    return path
