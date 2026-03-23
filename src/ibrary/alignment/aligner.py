"""Align curriculum units to textbook chunks via vector similarity."""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.alignment.embedder import embed_text
from ibrary.config import ALIGNMENT_CONFIDENCE_THRESHOLD, ALIGNMENT_TOP_K, OPENAI_EMBEDDING_MODEL
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.db import get_session

logger = structlog.get_logger(__name__)


def _build_query_text(unit: CurriculumUnit) -> str:
    """Combine content item with topic title and objectives for embedding."""
    parts = [unit.topic, unit.content_text]
    if unit.performance_objectives:
        parts.append("; ".join(unit.performance_objectives))
    return "\n".join(parts)


def align_unit(
    unit: CurriculumUnit,
    top_k: int = ALIGNMENT_TOP_K,
    model_version: str | None = None,
) -> list[dict]:
    """Return top-k matching textbook chunks for a curriculum unit."""
    model_version = model_version or OPENAI_EMBEDDING_MODEL
    query_text = _build_query_text(unit)
    query_vec = embed_text(query_text, model_version)

    session = get_session()
    try:
        results = session.execute(
            sa_text(
                """
                SELECT tce.chunk_id,
                       1 - (tce.embedding <=> :qvec ::vector) AS score,
                       tc.title,
                       tc.summary
                FROM textbook_chunk_embeddings tce
                JOIN textbook_chunks tc ON tc.chunk_id = tce.chunk_id
                WHERE tce.model_version = :model
                ORDER BY tce.embedding <=> :qvec ::vector
                LIMIT :k
                """
            ),
            {"qvec": str(query_vec), "model": model_version, "k": top_k},
        ).fetchall()

        matches = []
        for row in results:
            matches.append({
                "chunk_id": row.chunk_id,
                "score": round(float(row.score), 4),
                "title": row.title,
                "needs_review": float(row.score) < ALIGNMENT_CONFIDENCE_THRESHOLD,
            })
        return matches
    finally:
        session.close()


def align_all(
    units: list[CurriculumUnit],
    top_k: int = ALIGNMENT_TOP_K,
    model_version: str | None = None,
) -> dict[str, dict]:
    """Align all curriculum units; return mapping of unit_id → report row.

    Each value includes curriculum labels (`content_text` is the subtopic / content
    item wording) plus `matches` (chunk alignments). Older files used unit_id → list
    only; see `alignment_matches` in curation for loading either shape.
    """
    alignment: dict[str, dict] = {}
    for unit in units:
        try:
            matches = align_unit(unit, top_k=top_k, model_version=model_version)
            alignment[unit.curriculum_unit_id] = {
                "theme": unit.theme,
                "theme_number": unit.theme_number,
                "topic_number": unit.topic_number,
                "topic": unit.topic,
                "content_index": unit.content_index,
                "content_text": unit.content_text,
                "matches": matches,
            }
            if not matches:
                logger.warning("no_alignment", unit_id=unit.curriculum_unit_id)
        except Exception as exc:
            logger.error("alignment_failed", unit_id=unit.curriculum_unit_id, error=str(exc))
            alignment[unit.curriculum_unit_id] = {
                "theme": unit.theme,
                "theme_number": unit.theme_number,
                "topic_number": unit.topic_number,
                "topic": unit.topic,
                "content_index": unit.content_index,
                "content_text": unit.content_text,
                "matches": [],
            }
    return alignment


def save_alignment(alignment: dict, output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "curriculum_textbook_alignment.json"
    path.write_text(json.dumps(alignment, indent=2), encoding="utf-8")
    logger.info("alignment_saved", path=str(path))
    return path
