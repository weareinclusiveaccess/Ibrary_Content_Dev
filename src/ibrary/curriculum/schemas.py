"""Pydantic schemas for curriculum data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CurriculumUnit(BaseModel):
    """A single subtopic (content item) from the curriculum."""

    curriculum_unit_id: str
    class_name: str = Field(alias="class")
    theme: str
    theme_number: int
    topic_number: int
    topic: str
    content_index: int
    content_text: str
    performance_objectives: list[str] = []

    model_config = {"populate_by_name": True}


class CurriculumTopic(BaseModel):
    """A curriculum topic containing multiple content items (subtopics)."""

    class_name: str = Field(alias="class")
    theme: str
    theme_number: int
    topic_number: int
    topic: str
    pdf_pages: list[int] = []
    performance_objectives: list[str] = []
    content: list[str] = []
    textbook_chapters: list[int] = []

    model_config = {"populate_by_name": True}


class ValidatedCurriculum(BaseModel):
    """Output of curriculum validation."""

    units: list[CurriculumUnit]
    topics: list[CurriculumTopic]
    unmapped_topics: list[dict] = []
