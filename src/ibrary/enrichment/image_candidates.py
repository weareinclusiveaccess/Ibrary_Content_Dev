"""Load textbook image candidates for media linking."""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import POSTGRES_SCHEMA, PROJECT_ROOT
from ibrary.db import get_session

logger = structlog.get_logger(__name__)

_DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "docs"
    / "extracted_source_content"
    / "biology"
    / "textbook_image_manifest.json"
)


def _manifest_path() -> Path:
    import os

    raw = os.getenv("TEXTBOOK_IMAGE_MANIFEST", "")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return _DEFAULT_MANIFEST


def load_images_from_manifest(chunk_ids: list[str]) -> list[dict]:
    path = _manifest_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    wanted = set(chunk_ids)
    return [row for row in data if row.get("chunk_id") in wanted]


def load_images_from_db(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    session = get_session()
    try:
        placeholders = ", ".join(f":c{i}" for i in range(len(chunk_ids)))
        params = {f"c{i}": cid for i, cid in enumerate(chunk_ids)}
        rows = session.execute(
            sa_text(
                f"""
                SELECT image_id, chunk_id, s3_url, caption, alt_text, page_num
                FROM {POSTGRES_SCHEMA}.textbook_images
                WHERE chunk_id IN ({placeholders})
                """
            ),
            params,
        ).fetchall()
        return [
            {
                "image_id": r.image_id,
                "chunk_id": r.chunk_id,
                "s3_url": r.s3_url or "",
                "caption": r.caption or "",
                "alt_text": r.alt_text or "",
                "page_num": r.page_num,
            }
            for r in rows
        ]
    finally:
        session.close()


def load_image_candidates(chunk_ids: list[str]) -> list[dict]:
    """Postgres first, then local manifest fallback."""
    candidates = load_images_from_db(chunk_ids)
    if candidates:
        logger.info("image_candidates_db", count=len(candidates), chunks=len(chunk_ids))
        return candidates
    candidates = load_images_from_manifest(chunk_ids)
    logger.info("image_candidates_manifest", count=len(candidates), path=str(_manifest_path()))
    return candidates
