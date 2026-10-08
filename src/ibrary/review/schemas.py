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
    theme: str | None = None
    overall_score: float | None = None
    passed: bool | None = None
    updated_at: str | None = None


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
    updated_at: str | None = None


class ReviewerNoteOut(BaseModel):
    author: str | None = None
    date: str | None = None
    text: str


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


class RejectRequest(BaseModel):
    """Reject a unit with a required reviewer note (no empty rejections)."""

    note: str = Field(min_length=1)
    checked_by: str | None = None


class PublishToDynamoResponse(BaseModel):
    curriculum_unit_id: str
    status: str
    published: bool


class PortalConfigResponse(BaseModel):
    """UI hints that the SPA reads on load (auth-required, any role)."""

    publish_enabled: bool


class NotesRequest(BaseModel):
    notes: str
    overall_score: float | None = None
    checked_by: str | None = None


class ReviewerRubricRequest(BaseModel):
    """Human UDL principle scores (1–10) from a reviewer."""

    representation: float = Field(ge=0, le=10)
    engagement: float = Field(ge=0, le=10)
    action_expression: float = Field(ge=0, le=10)
    notes: str = ""
    checked_by: str | None = None
    mark_verified: bool = True


class PortalUserOut(BaseModel):
    username: str
    email: str
    status: str
    enabled: bool
    groups: list[str] = Field(default_factory=list)


class CreatePortalUserRequest(BaseModel):
    email: str
    role: str = Field(pattern="^(admin|reviewer)$")
    temporary_password: str = Field(min_length=10)
    send_invite: bool = False


class CognitoStatusResponse(BaseModel):
    enabled: bool
    user_pool_id: str | None = None
    region: str | None = None
    groups: list[str] = Field(default_factory=list)
    login_enabled: bool = False


class ReviewLoginRequest(BaseModel):
    email: str
    password: str
    new_password: str | None = None
    challenge_session: str | None = None


class ReviewLoginUser(BaseModel):
    email: str
    role: str
    name: str


class ReviewLoginTokens(BaseModel):
    id_token: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 0
    token_type: str = "Bearer"


class ReviewLoginResponse(BaseModel):
    user: ReviewLoginUser | None = None
    tokens: ReviewLoginTokens | None = None
    challenge: str | None = None
    challenge_session: str | None = None


class ReviewRefreshRequest(BaseModel):
    refresh_token: str


class ReviewRefreshResponse(BaseModel):
    tokens: ReviewLoginTokens


class ReviewerScoreOut(BaseModel):
    id: int
    reviewer: str | None = None
    date: str | None = None
    representation: float
    engagement: float
    action_expression: float
    overall_score: float | None = None
    notes: str = ""
