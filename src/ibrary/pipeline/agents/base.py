"""Base contract for content pipeline sub-agents."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ibrary.pipeline.context import PipelineContext


@runtime_checkable
class PipelineSubAgent(Protocol):
    """Single-responsibility step invoked by the orchestrator."""

    name: str

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Return updated context (may be the same object)."""
        ...


class AgentSkipped(Exception):
    """Raised when a sub-agent chooses to no-op (e.g. missing upstream data)."""
