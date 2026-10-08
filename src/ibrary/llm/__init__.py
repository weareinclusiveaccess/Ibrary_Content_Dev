"""LLM client utilities with structured tracing."""

from ibrary.llm.client import chat_completion_json, create_embeddings, get_openai_client
from ibrary.llm.tracing import LLMTraceRecord, configure_tracing, emit_trace, trace_jsonl_path

__all__ = [
    "LLMTraceRecord",
    "chat_completion_json",
    "configure_tracing",
    "create_embeddings",
    "emit_trace",
    "get_openai_client",
    "trace_jsonl_path",
]
