"""Function tools for OpenAI Agents SDK — wrap existing IBrary pipeline logic."""

from __future__ import annotations

import json

from agents import function_tool

from ibrary.config import PIPELINE_SUBJECT
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.prompts.context import resolve_subject


@function_tool
def score_chunk_relevance_tool(
    subtopic: str,
    topic: str,
    chunk_id: str,
    chunk_title: str,
    chunk_content: str,
    embedding_score: float,
    performance_objectives: str = "",
    subject: str = "",
) -> str:
    """Decide if a textbook chunk supports a curriculum subtopic; return JSON with relevant, excerpt, confidence, rationale."""
    from ibrary.relevance.scorer import score_chunk_relevance

    objectives = [o.strip() for o in performance_objectives.split(";") if o.strip()]
    unit = CurriculumUnit(
        curriculum_unit_id="tool-run",
        **{
            "class": "SSS 1",
            "theme": "",
            "theme_number": 1,
            "topic_number": 1,
            "topic": topic,
            "content_index": 0,
            "content_text": subtopic,
            "performance_objectives": objectives,
        },
    )
    result = score_chunk_relevance(
        unit,
        chunk_id=chunk_id,
        chunk_title=chunk_title,
        chunk_content=chunk_content,
        embedding_score=embedding_score,
        subject=resolve_subject(subject or None),
    )
    return result.model_dump_json()


@function_tool
def refine_curriculum_topic_tool(
    topic_units_json: str,
    subject: str = "",
) -> str:
    """Assign topic-level POs and activities to each subtopic. Input: JSON array of CurriculumUnit dicts for one topic."""
    from ibrary.curriculum.refiner import refine_topic_units
    from ibrary.curriculum.refiner_schemas import TopicRefinementResult

    raw = json.loads(topic_units_json)
    units = [CurriculumUnit.model_validate(u) for u in raw]
    result: TopicRefinementResult = refine_topic_units(units)
    return result.model_dump_json()


@function_tool
def curate_subtopic_tool(
    unit_json: str,
    alignment_matches_json: str,
    subject: str = "",
) -> str:
    """Generate UDL curated module JSON for one subtopic using alignment matches and Postgres chunks."""
    from ibrary.alignment.matches import alignment_matches
    from ibrary.curation.curation_service import curate_unit

    unit = CurriculumUnit.model_validate(json.loads(unit_json))
    matches = json.loads(alignment_matches_json)
    if isinstance(matches, dict):
        matches = alignment_matches(matches, unit.curriculum_unit_id)
    chunk_ids = [m["chunk_id"] for m in matches]
    module = curate_unit(unit, chunk_ids, alignment_matches=matches)
    if module is None:
        return json.dumps({"error": "curation_failed", "unit_id": unit.curriculum_unit_id})
    return module.model_dump_json(by_alias=True)


@function_tool
def judge_subtopic_content_tool(
    content: str,
    subtopic: str,
    subject: str = "",
    learning_objectives: str = "",
) -> str:
    """Score teaching content against CAST UDL v3 + correctness and clarity. Returns JSON SubtopicJudgeResult."""
    from ibrary.judging import evaluate_text

    objectives = [o.strip() for o in learning_objectives.split(";") if o.strip()]
    result = evaluate_text(
        content,
        subtopic=subtopic,
        subject=resolve_subject(subject or None),
        learning_objectives=objectives,
    )
    return result.model_dump_json()


@function_tool
def list_pipeline_agent_roles() -> str:
    """Return the fixed curation DAG step order for this project."""
    return json.dumps({
        "subject": resolve_subject(),
        "steps": [
            "relevance — filter aligned chunks per subtopic",
            "text_curator — UDL module body and placeholders",
            "media_linker — resolve image assets",
            "formula — LaTeX / chemistry formulas",
            "module_assembler — LearningModule v1 JSON",
        ],
        "orchestration": "manager calls specialists as tools (agents-as-tools pattern)",
    })
