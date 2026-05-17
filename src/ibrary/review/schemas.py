"""API schemas for the reviewer portal."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UnitListItem(BaseModel):
    curriculum_unit_id: str
    title: str | None = None
    subtopic: str | None = None
    class_name: str | None = None
    theme_number: int | None = None
    topic_number: int | None = None
    status: str
    overall_score: float | None = None
    passed: bool | None = None


class UnitListResponse(BaseModel):
    items: list[UnitListItem]
    total: int
    offset: int
    limit: int


class ImageAsset(BaseModel):
    image_id: str
    caption: str = ""
    alt_text: str = ""
    s3_url: str = ""
    display_url: str = ""


class UnitDetailResponse(BaseModel):
    curriculum_unit_id: str
    title: str | None = None
    subtopic: str | None = None
    class_name: str | None = None
    theme: str | None = None
    theme_number: int | None = None
    topic_number: int | None = None
    status: str
    learning_objectives: list[str] = Field(default_factory=list)
    curated_content_md: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    student_activities: list[str] = Field(default_factory=list)
    teacher_activities: list[str] = Field(default_factory=list)
    accessibility_checklist: list[str] = Field(default_factory=list)
    images: list[ImageAsset] = Field(default_factory=list)
    prompt_version: str | None = None
    model_version: str | None = None


class CheckpointScoreOut(BaseModel):
    checkpoint_id: str
    principle: str = ""
    principle_display: str = ""
    score: float
    notes: str = ""


class JudgeReportResponse(BaseModel):
    curriculum_unit_id: str
    overall_score: float | None = None
    passed: bool | None = None
    representation_score: float | None = None
    engagement_score: float | None = None
    action_expression_score: float | None = None
    correctness_score: float | None = None
    correctness_notes: str = ""
    clarity_score: float | None = None
    clarity_notes: str = ""
    checkpoint_scores: list[CheckpointScoreOut] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    judge_prompt_version: str | None = None
    judge_model_version: str | None = None
    error: str | None = None


class StatusUpdateRequest(BaseModel):
    status: str


class NotesRequest(BaseModel):
    notes: str
    overall_score: float | None = None
    checked_by: str | None = None
