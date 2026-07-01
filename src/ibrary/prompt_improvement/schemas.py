"""Schemas for prompt iteration driven by UDL judge scores."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ibrary.judging.schemas import SubtopicJudgeResult


class PromptVersionComparison(BaseModel):
    """Judge comparison for one subtopic between two prompt versions."""

    curriculum_unit_id: str
    baseline_prompt_version: str
    candidate_prompt_version: str
    baseline_score: float
    candidate_score: float
    delta_overall: float = 0.0
    improved: bool = False
    baseline: SubtopicJudgeResult | None = None
    candidate: SubtopicJudgeResult | None = None


class PromptImprovementReport(BaseModel):
    """Aggregate result for a prompt-improvement run."""

    baseline_prompt_version: str
    candidate_prompt_version: str
    comparisons: list[PromptVersionComparison] = Field(default_factory=list)
    mean_baseline: float = 0.0
    mean_candidate: float = 0.0
    mean_delta: float = 0.0
    improved: bool = False
    units_improved: int = 0
    units_regressed: int = 0
