"""Central OpenAI client with tracing for chat and embeddings."""

from __future__ import annotations

import json
import time
from typing import Any

from ibrary.config import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL
from ibrary.llm.tracing import configure_tracing, trace_chat_completion, trace_embeddings

_openai_client = None


def get_openai_client():
    """Shared OpenAI client; wrapped with LangSmith when configured."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    configure_tracing()
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    if _langsmith_enabled():
        try:
            from langsmith.wrappers import wrap_openai

            client = wrap_openai(client)
        except ImportError:
            pass
    _openai_client = client
    return _openai_client


def _langsmith_enabled() -> bool:
    import os

    return os.getenv("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes") and bool(
        os.getenv("LANGSMITH_API_KEY")
    )


def chat_completion_json(
    *,
    component: str,
    model: str,
    system: str,
    user: str,
    max_retries: int = 3,
    retry_backoff: float = 2,
    extra_create_kwargs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    """Chat completion with JSON object response; traced on every attempt."""
    client = get_openai_client()
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        if extra_create_kwargs:
            create_kwargs.update(extra_create_kwargs)

        try:
            resp, _ = trace_chat_completion(
                component=component,
                model=model,
                system=system,
                user=user,
                metadata=metadata,
                attempt=attempt,
                call_fn=lambda: client.chat.completions.create(**create_kwargs),
            )
            text = resp.choices[0].message.content or "{}"
            return json.loads(text)
        except json.JSONDecodeError as exc:
            last_exc = exc
            if attempt == max_retries:
                raise
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                raise
            time.sleep(retry_backoff**attempt)

    if last_exc:
        raise last_exc
    return {}


def create_embeddings(
    texts: list[str],
    *,
    component: str = "embedder",
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[list[float]]:
    """Embed a batch of strings with tracing."""
    model = model or OPENAI_EMBEDDING_MODEL
    client = get_openai_client()

    def _call():
        return client.embeddings.create(input=texts, model=model)

    resp, _ = trace_embeddings(
        component=component,
        model=model,
        texts=texts,
        metadata=metadata,
        call_fn=_call,
    )
    return [item.embedding for item in resp.data]
