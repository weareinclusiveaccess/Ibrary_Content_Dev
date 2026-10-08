"""Content pipeline orchestration and sub-agents (subject-agnostic)."""

from ibrary.pipeline.context import PipelineContext
from ibrary.pipeline.orchestrator import PipelineOrchestrator, create_orchestrator
from ibrary.pipeline.subagents import DEFAULT_SUBAGENTS, get_subagent

def __getattr__(name: str):
    if name == "openai_agents":
        from ibrary.pipeline import openai_agents as oa

        return oa
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_SUBAGENTS",
    "PipelineContext",
    "PipelineOrchestrator",
    "create_orchestrator",
    "get_subagent",
    "openai_agents",
]
