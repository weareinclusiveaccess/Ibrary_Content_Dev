"""Pydantic schemas for UDL-curated content modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


def _default_subject() -> str:
    from ibrary.config import PIPELINE_SUBJECT

    return PIPELINE_SUBJECT


class ImageRef(BaseModel):
    image_id: str
    s3_url: str
    caption: str = ""
    alt_text: str = ""


class FormulaRef(BaseModel):
    """LaTeX formula (math or chemistry \\ce{}) for KaTeX rendering."""

    formula_id: str
    kind: str = Field(description="chemistry | math")
    latex: str
    plain_text: str
    spoken_text: str = ""
    source: str = "generated"
    chunk_id: str | None = None
    confidence: float | None = None


class CuratedModule(BaseModel):
    """A UDL-aligned curated content module for a curriculum subtopic."""

    curriculum_unit_id: str
    subject: str = Field(default_factory=_default_subject)
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
    formulas: list[FormulaRef] = Field(default_factory=list)
    content_blocks: list[dict] = Field(default_factory=list)
    assets: list[dict] = Field(
        default_factory=list,
        description="Full MediaAsset metadata for LearningModule v1",
    )
    image_placeholders: list[dict] = Field(default_factory=list)
    formula_placeholders: list[dict] = Field(default_factory=list)
    textbook_grounded: bool = Field(
        default=True,
        description="False when curated without textbook excerpts (curriculum-only fallback)",
    )
    status: str = "draft"
    udl_score: float | None = None

    model_config = {"populate_by_name": True}


# Pipeline-only fields — not written to curated_content.json
_PIPELINE_INTERNAL_KEYS = frozenset({"image_placeholders", "formula_placeholders"})

# Omitted from JSON when empty (content_blocks disabled until app needs it)
_EXPORT_OMIT_IF_EMPTY = frozenset(
    {"images", "formulas", "assets", "content_blocks"}
)


def module_for_json_export(module: CuratedModule) -> dict:
    """Student/reviewer-facing payload for curated_content.json (no empty enrichment noise)."""
    data = module.model_dump(by_alias=True)
    for key in _PIPELINE_INTERNAL_KEYS:
        data.pop(key, None)
    for key in _EXPORT_OMIT_IF_EMPTY:
        if not data.get(key):
            data.pop(key, None)
    if module.udl_score is None:
        data.pop("udl_score", None)
    # Always export when false — reviewers need to see curriculum-only modules
    if module.textbook_grounded:
        data.pop("textbook_grounded", None)
    return data
