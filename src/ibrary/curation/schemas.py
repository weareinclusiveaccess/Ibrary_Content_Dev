"""Pydantic schemas for UDL-curated content modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImageRef(BaseModel):
    image_id: str
    s3_url: str
    caption: str = ""
    alt_text: str = ""


class CuratedModule(BaseModel):
    """A UDL-aligned curated content module for a curriculum subtopic."""

    curriculum_unit_id: str
    subject: str = "Biology"
    class_name: str = Field(alias="class")
    theme: str
    theme_number: int
    topic_number: int
    subtopic: str
    title: str
    learning_objectives: list[str] = []
    curated_content: str = Field(description="Markdown-formatted UDL content")
    key_takeaways: list[str] = []
    glossary_terms: dict[str, str] = Field(
        default_factory=dict, description="term → definition"
    )
    student_activities: list[str] = Field(
        default_factory=list,
        description="Concrete learner tasks aligned to the subtopic",
    )
    teacher_activities: list[str] = Field(
        default_factory=list,
        description="Concrete teaching moves for this subtopic",
    )
    accessibility_checklist: list[str] = Field(
        default_factory=list,
        description="Short statements of how accessibility/UDL were applied",
    )
    textbook_chunk_refs: list[str] = []
    model_version: str = ""
    prompt_version: str = ""
    images: list[ImageRef] = []
    status: str = "draft"
    udl_score: float | None = None

    model_config = {"populate_by_name": True}
