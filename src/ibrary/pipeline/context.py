"""Shared state passed between content pipeline sub-agents (any subject)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ibrary.curation.schemas import CuratedModule
from ibrary.curriculum.schemas import CurriculumUnit


@dataclass
class PipelineContext:
    """Mutable context for one curriculum unit (or a batch step)."""

    curriculum_unit_id: str
    unit: CurriculumUnit | None = None

    # align + filter_relevance
    alignment_matches: list[dict] = field(default_factory=list)
    relevance_results: list[dict] = field(default_factory=list)
    excerpt_chunks: list[dict] = field(default_factory=list)
    curriculum_only: bool = False

    # TextCuratorAgent
    content_blocks: list[dict] = field(default_factory=list)
    image_placeholders: list[dict] = field(default_factory=list)
    formula_placeholders: list[dict] = field(default_factory=list)

    # MediaLinkerAgent / FormulaAgent
    assets: list[dict] = field(default_factory=list)
    formulas: list[dict] = field(default_factory=list)

    # TextCuratorAgent / ModuleAssemblerAgent
    curated_module: CuratedModule | None = None
    learning_module: dict[str, Any] | None = None

    # audit trails
    media_resolution: list[dict] = field(default_factory=list)
    formula_resolution: list[dict] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
