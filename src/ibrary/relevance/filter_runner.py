"""Run filter_relevance for curriculum units using alignment top-k matches."""

from __future__ import annotations

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import ALIGNMENT_TOP_K, POSTGRES_SCHEMA
from ibrary.alignment.matches import alignment_matches
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.db import get_session
from ibrary.relevance.schemas import UnitRelevanceReport
from ibrary.relevance.scorer import score_chunk_relevance
from ibrary.relevance.store import upsert_chunk_relevance

logger = structlog.get_logger(__name__)


def _fetch_chunk(unit_id: str, chunk_id: str) -> dict | None:
    session = get_session()
    try:
        row = session.execute(
            sa_text(
                f"""
                SELECT chunk_id, title, content, content_hash, content AS body
                FROM {POSTGRES_SCHEMA}.textbook_chunks
                WHERE chunk_id = :cid
                """
            ),
            {"cid": chunk_id},
        ).fetchone()
        if not row:
            return None
        return {
            "chunk_id": row.chunk_id,
            "title": row.title,
            "content": row.body,
            "content_hash": row.content_hash,
        }
    finally:
        session.close()


def filter_relevance_for_units(
    units: list[CurriculumUnit],
    alignment: dict,
    *,
    max_chunks: int | None = None,
) -> dict[str, UnitRelevanceReport]:
    """For each unit, score relevance on each aligned chunk (up to top-k)."""
    limit = max_chunks or ALIGNMENT_TOP_K
    reports: dict[str, UnitRelevanceReport] = {}

    for unit in units:
        matches = alignment_matches(alignment, unit.curriculum_unit_id)[:limit]
        results = []
        for m in matches:
            cid = m["chunk_id"]
            row = _fetch_chunk(unit.curriculum_unit_id, cid)
            if not row:
                logger.warning("chunk_missing", chunk_id=cid)
                continue
            result = score_chunk_relevance(
                unit,
                chunk_id=cid,
                chunk_title=row["title"] or cid,
                chunk_content=row["content"] or "",
                embedding_score=float(m.get("score", 0)),
            )
            upsert_chunk_relevance(
                unit.curriculum_unit_id,
                result,
                content_hash=row.get("content_hash"),
            )
            results.append(result)
            logger.info(
                "relevance_scored",
                unit_id=unit.curriculum_unit_id,
                chunk_id=cid,
                relevant=result.relevant,
            )
        reports[unit.curriculum_unit_id] = UnitRelevanceReport(
            curriculum_unit_id=unit.curriculum_unit_id,
            results=results,
        )
    return reports
