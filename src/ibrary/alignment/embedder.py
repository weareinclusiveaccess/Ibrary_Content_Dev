"""Embed textbook chunks (title+summary) and store in pgvector."""

from __future__ import annotations

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL
from ibrary.db import get_session

logger = structlog.get_logger(__name__)


def _get_openai_embeddings(texts: list[str], model: str = OPENAI_EMBEDDING_MODEL) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in resp.data]


def embed_textbook_chunks(model_version: str | None = None) -> int:
    """Embed all textbook chunks that don't yet have embeddings for this model."""
    model_version = model_version or OPENAI_EMBEDDING_MODEL
    session = get_session()
    try:
        rows = session.execute(
            sa_text(
                """
                SELECT tc.chunk_id, tc.title, tc.summary
                FROM textbook_chunks tc
                LEFT JOIN textbook_chunk_embeddings tce
                    ON tc.chunk_id = tce.chunk_id AND tce.model_version = :model
                WHERE tce.id IS NULL
                """
            ),
            {"model": model_version},
        ).fetchall()

        if not rows:
            logger.info("all_chunks_embedded")
            return 0

        texts = [f"{r.title}\n{r.summary or ''}" for r in rows]
        chunk_ids = [r.chunk_id for r in rows]

        batch_size = 100
        total = 0
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start : start + batch_size]
            batch_ids = chunk_ids[start : start + batch_size]
            embeddings = _get_openai_embeddings(batch_texts, model_version)

            for cid, emb in zip(batch_ids, embeddings):
                session.execute(
                    sa_text(
                        """
                        INSERT INTO textbook_chunk_embeddings (chunk_id, embedding, model_version)
                        VALUES (:cid, :emb, :model)
                        ON CONFLICT (chunk_id, model_version) DO NOTHING
                        """
                    ),
                    {"cid": cid, "emb": str(emb), "model": model_version},
                )
            total += len(batch_texts)

        session.commit()
        logger.info("chunks_embedded", count=total)
        return total
    finally:
        session.close()


def embed_text(text: str, model: str | None = None) -> list[float]:
    """Embed a single text string and return the vector."""
    model = model or OPENAI_EMBEDDING_MODEL
    return _get_openai_embeddings([text], model)[0]
