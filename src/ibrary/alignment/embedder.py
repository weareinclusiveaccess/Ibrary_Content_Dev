"""Embed textbook chunks and store in pgvector."""

from __future__ import annotations

import structlog
from sqlalchemy import text as sa_text

from ibrary.alignment.embedding_text import (
    build_chunk_embedding_text,
    resolve_embedding_storage_version,
)
from ibrary.config import OPENAI_EMBEDDING_MODEL
from ibrary.db import get_session
from ibrary.llm.client import create_embeddings

logger = structlog.get_logger(__name__)


def embed_textbook_chunks(storage_version: str | None = None) -> int:
    """Embed chunks missing vectors for ``storage_version`` (see ``resolve_embedding_storage_version``)."""
    storage_version = storage_version or resolve_embedding_storage_version()
    session = get_session()
    try:
        rows = session.execute(
            sa_text(
                """
                SELECT tc.chunk_id, tc.title, tc.summary, tc.learning_objectives, tc.content
                FROM textbook_chunks tc
                LEFT JOIN textbook_chunk_embeddings tce
                    ON tc.chunk_id = tce.chunk_id AND tce.model_version = :model
                WHERE tce.id IS NULL
                """
            ),
            {"model": storage_version},
        ).fetchall()

        if not rows:
            logger.info("all_chunks_embedded", model_version=storage_version)
            return 0

        texts = [
            build_chunk_embedding_text(
                title=r.title or "",
                learning_objectives=r.learning_objectives or "",
                summary=r.summary or "",
                content=r.content or "",
            )
            for r in rows
        ]
        chunk_ids = [r.chunk_id for r in rows]

        batch_size = 100
        total = 0
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start : start + batch_size]
            batch_ids = chunk_ids[start : start + batch_size]
            embeddings = create_embeddings(
                batch_texts,
                component="embedder",
                model=OPENAI_EMBEDDING_MODEL,
                metadata={
                    "storage_version": storage_version,
                    "batch_start": start,
                    "batch_count": len(batch_texts),
                },
            )

            for cid, emb in zip(batch_ids, embeddings):
                session.execute(
                    sa_text(
                        """
                        INSERT INTO textbook_chunk_embeddings (chunk_id, embedding, model_version)
                        VALUES (:cid, :emb, :model)
                        ON CONFLICT (chunk_id, model_version) DO NOTHING
                        """
                    ),
                    {"cid": cid, "emb": str(emb), "model": storage_version},
                )
            total += len(batch_texts)

        session.commit()
        logger.info(
            "chunks_embedded",
            count=total,
            model_version=storage_version,
        )
        return total
    finally:
        session.close()


def embed_text(text: str) -> list[float]:
    """Embed a single text string (API model from ``OPENAI_EMBEDDING_MODEL``)."""
    return create_embeddings(
        [text],
        component="embedder_query",
        metadata={"query": True},
    )[0]
