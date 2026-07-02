"""OpenAPI response models for the content read API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    table: str = Field(examples=["CuratedContent"])
    region: str = Field(examples=["eu-west-1"])


class TopicItem(BaseModel):
    """Topic metadata stored in DynamoDB (entity_type=TOPIC)."""

    entity_type: str = Field(examples=["TOPIC"])
    topic_number: int = Field(examples=[1])
    topic: str = Field(description="Curriculum topic name")
    title: str = Field(description="Lesson title")
    learning_objectives: str = Field(
        description="JSON array string — parse before use",
        examples=['["State the characteristics of living things"]'],
    )
    glossary_terms: str = Field(
        description="JSON array string — parse before use",
        examples=["[]"],
    )


class SubtopicItem(BaseModel):
    """Full lesson content (entity_type=SUBTOPIC). Primary payload for the app."""

    entity_type: str = Field(examples=["SUBTOPIC"])
    curriculum_unit_id: str = Field(
        examples=["bio_sss1_theme1_topic1_content0"],
        description="Stable ID: bio_sss1_theme{T}_topic{N}_content{M}",
    )
    subtopic: str
    curated_content_md: str = Field(description="Main lesson body in Markdown")
    key_takeaways: str = Field(description="JSON array string")
    glossary_terms: str = Field(description="JSON array string")
    student_activities: str = Field(description="JSON array string")
    teacher_activities: str = Field(description="JSON array string")
    accessibility_checklist: str = Field(description="JSON object/array string")
    textbook_chunk_refs: str = Field(description="JSON array string")
    model_version: str | None = None
    prompt_version: str | None = None


class TopicListResponse(BaseModel):
    topics: list[dict[str, Any]]


class SubtopicListResponse(BaseModel):
    subtopics: list[dict[str, Any]]


class SubtopicSummaryItem(BaseModel):
    """Lightweight catalog row for browsing lessons before fetching full content."""

    subtopic: str = Field(
        examples=["Characteristics of living things"],
        description="Lesson title / curriculum content label",
    )
    PK: str = Field(
        examples=["SUBJECT#Biology#CLASS#SSS 1#THEME#1"],
        description="DynamoDB partition key",
    )
    SK: str = Field(
        examples=["TOPIC#01#CONTENT#0"],
        description="DynamoDB sort key — content index is the number after CONTENT#",
    )


class SubtopicSummaryListResponse(BaseModel):
    subtopics: list[SubtopicSummaryItem]


class ErrorResponse(BaseModel):
    detail: str
