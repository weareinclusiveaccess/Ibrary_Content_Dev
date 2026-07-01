"""Schemas for curriculum subtopic refinement (LLM assignment)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubtopicAssignment(BaseModel):
    """Refined objectives/activities for one subtopic within a topic."""

    content_index: int
    performance_objectives: list[str] = Field(default_factory=list)
    teachers_activities: list[str] = Field(default_factory=list)
    student_activities: list[str] = Field(default_factory=list)
    rationale: str = ""


class TopicRefinementResult(BaseModel):
    """LLM output for one curriculum topic (all subtopics)."""

    theme_number: int
    topic_number: int
    topic: str
    assignments: list[SubtopicAssignment] = Field(default_factory=list)


class CurriculumRefinementReport(BaseModel):
    """Summary written alongside refined curriculum_validated.json."""

    agent_version: str
    model: str
    topics_refined: int
    units_updated: int
    topic_results: list[TopicRefinementResult] = Field(default_factory=list)
