"""Run OpenAI Agents SDK workflows (async + sync helpers)."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents import Agent, Runner

from ibrary.pipeline.openai_agents.definitions import (
    ALL_AGENTS,
    curation_pipeline_manager,
    curation_triage_agent,
)


async def run_agent_async(
    agent: Agent,
    user_message: str,
    *,
    context: Any | None = None,
    metadata: dict | None = None,
) -> Any:
    """Run one agent turn; returns ``Runner`` result (``.final_output``)."""
    from ibrary.llm.tracing import LLMTraceRecord, configure_tracing, emit_trace

    configure_tracing()
    trace_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    success = False
    error_msg: str | None = None
    output = ""

    try:
        result = await Runner.run(agent, user_message, context=context)
        success = True
        output = str(getattr(result, "final_output", "") or "")
        return result
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        latency_ms = (time.perf_counter() - t0) * 1000
        emit_trace(
            LLMTraceRecord(
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                component="openai_agents",
                operation="agent_run",
                model=str(getattr(agent, "model", "unknown")),
                latency_ms=latency_ms,
                success=success,
                error=error_msg,
                user_chars=len(user_message),
                response_chars=len(output),
                metadata={
                    "agent_name": getattr(agent, "name", ""),
                    **(metadata or {}),
                },
                user_preview=user_message[:240],
                response_preview=output[:240],
            )
        )


def run_agent_sync(
    agent: Agent,
    user_message: str,
    *,
    context: Any | None = None,
    metadata: dict | None = None,
) -> Any:
    """Blocking wrapper around ``run_agent_async``."""
    return asyncio.run(
        run_agent_async(agent, user_message, context=context, metadata=metadata)
    )


def run_curation_manager(
    curriculum_unit_id: str,
    *,
    extra_instructions: str = "",
) -> Any:
    """Ask the curation manager to plan/run the per-unit pipeline."""
    prompt = (
        f"Curate curriculum unit: {curriculum_unit_id}. "
        f"Subject pipeline for one subtopic. {extra_instructions}".strip()
    )
    return run_agent_sync(
        curation_pipeline_manager,
        prompt,
        metadata={"curriculum_unit_id": curriculum_unit_id},
    )


def run_triage(user_message: str) -> Any:
    """Route a natural-language request via handoff triage agent."""
    return run_agent_sync(curation_triage_agent, user_message)


def get_agent(name: str) -> Agent:
    try:
        return ALL_AGENTS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown agent {name!r}. Known: {sorted(ALL_AGENTS)}") from exc
