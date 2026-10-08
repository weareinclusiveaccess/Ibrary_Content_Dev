"""Persist chunk relevance to Postgres and JSON file."""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import POSTGRES_SCHEMA
from ibrary.db import get_session
from ibrary.relevance.schemas import ChunkRelevanceResult, UnitRelevanceReport

_TBL = f"{POSTGRES_SCHEMA}.chunk_relevance"

logger = structlog.get_logger(__name__)
AGENT_VERSION = "relevance-v1"


def upsert_chunk_relevance(
    unit_id: str,
    result: ChunkRelevanceResult,
    *,
    content_hash: str | None = None,
) -> None:
    session = get_session()
    try:
        session.execute(
            sa_text(
                f"""
                INSERT INTO {_TBL} (
                    curriculum_unit_id, chunk_id, relevant, excerpt,
                    embedding_score, confidence, rationale, agent_version, content_hash
                ) VALUES (
                    :uid, :cid, :rel, :excerpt,
                    :escore, :conf, :rat, :agent, :hash
                )
                ON CONFLICT (curriculum_unit_id, chunk_id)
                DO UPDATE SET
                    relevant = EXCLUDED.relevant,
                    excerpt = EXCLUDED.excerpt,
                    embedding_score = EXCLUDED.embedding_score,
                    confidence = EXCLUDED.confidence,
                    rationale = EXCLUDED.rationale,
                    agent_version = EXCLUDED.agent_version,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = NOW()
                """
            ),
            {
                "uid": unit_id,
                "cid": result.chunk_id,
                "rel": result.relevant,
                "excerpt": result.excerpt,
                "escore": result.embedding_score,
                "conf": result.confidence,
                "rat": result.rationale,
                "agent": AGENT_VERSION,
                "hash": content_hash,
            },
        )
        session.commit()
    finally:
        session.close()


def save_relevance_json(reports: dict[str, UnitRelevanceReport], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "chunk_relevance.json"
    data = {uid: r.model_dump() for uid, r in reports.items()}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("chunk_relevance_saved", path=str(path), units=len(data))
    return path


def load_relevance_for_unit(unit_id: str) -> list[ChunkRelevanceResult]:
    session = get_session()
    try:
        rows = session.execute(
            sa_text(
                f"""
                SELECT chunk_id, relevant, excerpt, embedding_score, confidence, rationale
                FROM {_TBL}
                WHERE curriculum_unit_id = :uid AND relevant = true
                ORDER BY embedding_score DESC NULLS LAST
                """
            ),
            {"uid": unit_id},
        ).fetchall()
        return [
            ChunkRelevanceResult(
                chunk_id=r.chunk_id,
                relevant=True,
                excerpt=r.excerpt,
                embedding_score=r.embedding_score,
                confidence=r.confidence,
                rationale=r.rationale or "",
            )
            for r in rows
        ]
    finally:
        session.close()
