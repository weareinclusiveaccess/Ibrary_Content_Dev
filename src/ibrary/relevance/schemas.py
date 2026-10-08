"""Schemas for filter_relevance step."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkRelevanceResult(BaseModel):
    chunk_id: str
    relevant: bool
    excerpt: str | None = None
    embedding_score: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=10)
    rationale: str = ""


class UnitRelevanceReport(BaseModel):
    curriculum_unit_id: str
    results: list[ChunkRelevanceResult] = Field(default_factory=list)
