"""Prompt improvement loop — uses ``ibrary.judging`` to measure quality deltas."""

from ibrary.prompt_improvement.compare import (
    compare_curated_files,
    compare_prompt_versions,
    save_improvement_report,
)
from ibrary.prompt_improvement.schemas import PromptImprovementReport, PromptVersionComparison

__all__ = [
    "PromptImprovementReport",
    "PromptVersionComparison",
    "compare_curated_files",
    "compare_prompt_versions",
    "save_improvement_report",
]
