"""Align curriculum units to textbook chunks via vector similarity."""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.alignment.embedder import embed_text
from ibrary.alignment.embedding_text import (
    build_unit_query_text,
    resolve_embedding_storage_version,
)
from ibrary.config import (
    ALIGNMENT_CHAPTER_FILTER,
    ALIGNMENT_CHAPTER_FILTER_FALLBACK,
    ALIGNMENT_CONFIDENCE_THRESHOLD,
    ALIGNMENT_TOP_K,
)
from ibrary.curriculum.schemas import CurriculumTopic, CurriculumUnit
from ibrary.db import get_session

logger = structlog.get_logger(__name__)


def _chapter_lookup(topics: list[CurriculumTopic] | None) -> dict[tuple[int, int], list[int]]:
    out: dict[tuple[int, int], list[int]] = {}
    if not topics:
        return out
    for t in topics:
        if t.textbook_chapters:
            out[(t.theme_number, t.topic_number)] = list(t.textbook_chapters)
    return out


def _resolve_chapters(
    unit: CurriculumUnit,
    topic_chapters: dict[tuple[int, int], list[int]],
) -> list[int]:
    if unit.textbook_chapters:
        return list(unit.textbook_chapters)
    return list(topic_chapters.get((unit.theme_number, unit.topic_number), []))


def _search_chunks(
    query_vec: list[float],
    *,
    storage_version: str,
    top_k: int,
    chapter_nums: list[int] | None,
) -> list:
    session = get_session()
    try:
        sql = """
                SELECT tce.chunk_id,
                       1 - (tce.embedding <=> :qvec ::vector) AS score,
                       tc.title,
                       tc.summary,
                       tc.chapter_num
                FROM textbook_chunk_embeddings tce
                JOIN textbook_chunks tc ON tc.chunk_id = tce.chunk_id
                WHERE tce.model_version = :model
                """
        params: dict = {"qvec": str(query_vec), "model": storage_version, "k": top_k}
        if chapter_nums:
            sql += " AND tc.chapter_num = ANY(:chapters)"
            params["chapters"] = chapter_nums
        sql += " ORDER BY tce.embedding <=> :qvec ::vector LIMIT :k"
        return session.execute(sa_text(sql), params).fetchall()
    finally:
        session.close()


def _rows_to_matches(rows) -> list[dict]:
    matches = []
    for row in rows:
        matches.append({
            "chunk_id": row.chunk_id,
            "score": round(float(row.score), 4),
            "title": row.title,
            "chapter_num": row.chapter_num,
            "needs_review": float(row.score) < ALIGNMENT_CONFIDENCE_THRESHOLD,
        })
    return matches


def align_unit(
    unit: CurriculumUnit,
    top_k: int = ALIGNMENT_TOP_K,
    storage_version: str | None = None,
    *,
    chapter_nums: list[int] | None = None,
    use_chapter_filter: bool = ALIGNMENT_CHAPTER_FILTER,
    chapter_filter_fallback: bool = ALIGNMENT_CHAPTER_FILTER_FALLBACK,
) -> list[dict]:
    """Return top-k matching textbook chunks for a curriculum unit."""
    storage_version = storage_version or resolve_embedding_storage_version()
    query_text = build_unit_query_text(unit)
    query_vec = embed_text(query_text)

    filter_chapters = (
        list(chapter_nums) if (use_chapter_filter and chapter_nums) else None
    )
    rows = _search_chunks(
        query_vec,
        storage_version=storage_version,
        top_k=top_k,
        chapter_nums=filter_chapters,
    )
    if not rows and filter_chapters and chapter_filter_fallback:
        logger.info(
            "alignment_chapter_fallback",
            unit_id=unit.curriculum_unit_id,
            chapters=filter_chapters,
        )
        rows = _search_chunks(
            query_vec,
            storage_version=storage_version,
            top_k=top_k,
            chapter_nums=None,
        )

    return _rows_to_matches(rows)


def align_all(
    units: list[CurriculumUnit],
    top_k: int = ALIGNMENT_TOP_K,
    storage_version: str | None = None,
    *,
    topics: list[CurriculumTopic] | None = None,
) -> dict[str, dict]:
    """Align all curriculum units; return mapping of unit_id → report row."""
    storage_version = storage_version or resolve_embedding_storage_version()
    topic_chapters = _chapter_lookup(topics)
    alignment: dict[str, dict] = {}

    for unit in units:
        chapters = _resolve_chapters(unit, topic_chapters)
        try:
            matches = align_unit(
                unit,
                top_k=top_k,
                storage_version=storage_version,
                chapter_nums=chapters or None,
            )
            alignment[unit.curriculum_unit_id] = {
                "theme": unit.theme,
                "theme_number": unit.theme_number,
                "topic_number": unit.topic_number,
                "topic": unit.topic,
                "content_index": unit.content_index,
                "content_text": unit.content_text,
                "textbook_chapters": chapters,
                "matches": matches,
            }
            if not matches:
                logger.warning(
                    "no_alignment",
                    unit_id=unit.curriculum_unit_id,
                    textbook_chapters=chapters,
                )
        except Exception as exc:
            logger.error("alignment_failed", unit_id=unit.curriculum_unit_id, error=str(exc))
            alignment[unit.curriculum_unit_id] = {
                "theme": unit.theme,
                "theme_number": unit.theme_number,
                "topic_number": unit.topic_number,
                "topic": unit.topic,
                "content_index": unit.content_index,
                "content_text": unit.content_text,
                "textbook_chapters": chapters,
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
