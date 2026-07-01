"""Structured tracing for all OpenAI LLM calls (logs + optional JSONL + LangSmith)."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from ibrary.config import PROJECT_ROOT

logger = structlog.get_logger("llm.trace")

_tracing_configured = False


@dataclass
class LLMTraceRecord:
    """One row for analysis (JSONL export)."""

    trace_id: str
    timestamp: str
    component: str
    operation: str
    model: str
    latency_ms: float
    success: bool
    attempt: int = 1
    error: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    system_chars: int = 0
    user_chars: int = 0
    response_chars: int = 0
    batch_size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    system_preview: str = ""
    user_preview: str = ""
    response_preview: str = ""


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default).lower()).lower() in ("1", "true", "yes")


def configure_tracing() -> None:
    """Idempotent: LangSmith env + log path setup."""
    global _tracing_configured
    if _tracing_configured:
        return

    if _env_bool("LANGSMITH_TRACING", False) and os.getenv("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", os.environ["LANGSMITH_API_KEY"])
        project = os.getenv("LANGSMITH_PROJECT", "ibrary-pipeline")
        os.environ.setdefault("LANGCHAIN_PROJECT", project)
        logger.info("langsmith_tracing_enabled", project=project)

    path = trace_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _tracing_configured = True
    logger.info(
        "llm_tracing_configured",
        jsonl=str(path),
        log_prompts=_env_bool("LLM_TRACE_LOG_PROMPTS", False),
    )


def trace_enabled() -> bool:
    return _env_bool("LLM_TRACE_ENABLED", True)


def trace_log_prompts() -> bool:
    return _env_bool("LLM_TRACE_LOG_PROMPTS", False)


def trace_jsonl_path() -> Path:
    raw = os.getenv("LLM_TRACE_JSONL_PATH", "data/logs/llm_traces.jsonl")
    p = Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _preview(text: str, limit: int = 240) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


def _usage_fields(usage: Any) -> dict[str, int | None]:
    if usage is None:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


_TRACE_LOG_RESERVED = frozenset(
    {
        "trace_id",
        "component",
        "operation",
        "model",
        "latency_ms",
        "success",
        "attempt",
        "error",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "system_chars",
        "user_chars",
        "response_chars",
        "batch_size",
    }
)


def emit_trace(record: LLMTraceRecord) -> None:
    """Structlog + append JSONL."""
    if not trace_enabled():
        return

    extra_meta = {
        k: v for k, v in record.metadata.items() if k not in _TRACE_LOG_RESERVED
    }

    logger.info(
        "llm_call",
        trace_id=record.trace_id,
        component=record.component,
        operation=record.operation,
        model=record.model,
        latency_ms=round(record.latency_ms, 1),
        success=record.success,
        attempt=record.attempt,
        error=record.error,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        total_tokens=record.total_tokens,
        system_chars=record.system_chars,
        user_chars=record.user_chars,
        response_chars=record.response_chars,
        batch_size=record.batch_size,
        **extra_meta,
    )

    path = trace_jsonl_path()
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), default=str) + "\n")
    except OSError as exc:
        logger.warning("llm_trace_write_failed", path=str(path), error=str(exc))


def trace_chat_completion(
    *,
    component: str,
    model: str,
    system: str,
    user: str,
    call_fn,
    metadata: dict[str, Any] | None = None,
    attempt: int = 1,
) -> tuple[Any, LLMTraceRecord]:
    """Wrap a chat completion call; ``call_fn`` is zero-arg returning OpenAI response."""
    trace_id = str(uuid.uuid4())
    meta = dict(metadata or {})
    t0 = time.perf_counter()
    error_msg: str | None = None
    resp = None
    try:
        resp = call_fn()
        success = True
    except Exception as exc:
        success = False
        error_msg = str(exc)
        latency_ms = (time.perf_counter() - t0) * 1000
        record = LLMTraceRecord(
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            component=component,
            operation="chat_completion",
            model=model,
            latency_ms=latency_ms,
            success=False,
            attempt=attempt,
            error=error_msg,
            system_chars=len(system or ""),
            user_chars=len(user or ""),
            metadata=meta,
            system_preview=_preview(system) if trace_log_prompts() else "",
            user_preview=_preview(user) if trace_log_prompts() else "",
        )
        emit_trace(record)
        raise

    text = ""
    if resp and getattr(resp, "choices", None):
        text = resp.choices[0].message.content or ""
    usage = _usage_fields(getattr(resp, "usage", None))
    latency_ms = (time.perf_counter() - t0) * 1000
    record = LLMTraceRecord(
        trace_id=trace_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        component=component,
        operation="chat_completion",
        model=model,
        latency_ms=latency_ms,
        success=success,
        attempt=attempt,
        error=error_msg,
        system_chars=len(system or ""),
        user_chars=len(user or ""),
        response_chars=len(text),
        metadata=meta,
        system_preview=_preview(system) if trace_log_prompts() else "",
        user_preview=_preview(user) if trace_log_prompts() else "",
        response_preview=_preview(text) if trace_log_prompts() else "",
        **usage,
    )
    emit_trace(record)
    return resp, record


def trace_embeddings(
    *,
    component: str,
    model: str,
    texts: list[str],
    call_fn,
    metadata: dict[str, Any] | None = None,
) -> tuple[Any, LLMTraceRecord]:
    """Wrap an embeddings API call."""
    trace_id = str(uuid.uuid4())
    meta = dict(metadata or {})
    t0 = time.perf_counter()
    try:
        resp = call_fn()
        success = True
        error_msg = None
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        record = LLMTraceRecord(
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            component=component,
            operation="embedding",
            model=model,
            latency_ms=latency_ms,
            success=False,
            error=str(exc),
            batch_size=len(texts),
            user_chars=sum(len(t) for t in texts),
            metadata=meta,
        )
        emit_trace(record)
        raise

    usage = _usage_fields(getattr(resp, "usage", None))
    latency_ms = (time.perf_counter() - t0) * 1000
    record = LLMTraceRecord(
        trace_id=trace_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        component=component,
        operation="embedding",
        model=model,
        latency_ms=latency_ms,
        success=True,
        batch_size=len(texts),
        user_chars=sum(len(t) for t in texts),
        metadata=meta,
        **usage,
    )
    emit_trace(record)
    return resp, record
