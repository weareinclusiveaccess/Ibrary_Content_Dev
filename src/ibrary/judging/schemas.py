"""Schemas for subtopic-level UDL evaluation."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CheckpointScore(BaseModel):
    """Score for one CAST UDL v3 checkpoint."""

    checkpoint_id: str
    score: float = Field(ge=0, le=10)
    notes: str = ""
    # Filled from CHECKPOINT_BY_ID when results are parsed (see enrich_checkpoint_scores)
    principle: str = Field(default="", description="Internal key: engagement | representation | action_expression")
    principle_display: str = Field(default="", description="CAST principle name")
    cast_guideline: str = Field(default="", description="Top-level CAST guideline number 1–9")
    category: str = Field(default="", description="Guideline sub-area slug")
    measures: str = Field(default="", description="What this checkpoint evaluates")


class SubtopicJudgeInput(BaseModel):
    """Input for UDL judging — only ``content`` is required; rest improves scoring."""

    content: str = Field(min_length=1, description="Module body or any text to evaluate")
    subtopic: str = Field(default="", description="Curriculum subtopic / content item wording")
    subject: str = ""
    class_name: str = Field(default="", alias="class")
    title: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    student_activities: list[str] = Field(default_factory=list)
    teacher_activities: list[str] = Field(default_factory=list)
    accessibility_checklist: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    glossary_terms: dict[str, str] = Field(default_factory=dict)

    curriculum_unit_id: str = ""
    prompt_version: str = ""
    model_version: str = ""

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def strip_content(self) -> SubtopicJudgeInput:
        if not self.content.strip():
            raise ValueError("content must be non-empty after stripping whitespace")
        return self


class SubtopicJudgeResult(BaseModel):
    """UDL + quality evaluation for one text / subtopic."""

    curriculum_unit_id: str = ""
    subject: str = ""
    subtopic: str = ""
    prompt_version: str = ""
    model_version: str = ""
    judge_prompt_version: str = ""
    judge_model_version: str = ""

    checkpoint_scores: list[CheckpointScore] = Field(default_factory=list)
    representation_score: float | None = None
    action_expression_score: float | None = None
    engagement_score: float | None = None

    # Additional quality dimensions (beyond UDL checkpoints)
    correctness_score: float | None = Field(
        default=None,
        description="Factual accuracy and alignment to subtopic/curriculum (1–10)",
    )
    correctness_notes: str = ""
    clarity_score: float | None = Field(
        default=None,
        description="Readability, structure, plain language for diverse learners (1–10)",
    )
    clarity_notes: str = ""

    overall_score: float | None = None
    passed: bool = False
    recommendations: list[str] = Field(default_factory=list)
    error: str | None = None
