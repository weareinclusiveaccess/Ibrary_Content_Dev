"""Load extracted textbook chunks into PostgreSQL (idempotent upsert)."""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ibrary.db import get_session
from ibrary.models import Textbook, TextbookChunk, TextbookImage
from ibrary.textbook.extractor import ExtractedImage, TextbookChunkRecord

logger = structlog.get_logger(__name__)


def upsert_textbook(
    book_id: str,
    title: str,
    edition: str = "",
    source_path: str = "",
) -> None:
    session = get_session()
    try:
        stmt = (
            pg_insert(Textbook)
            .values(book_id=book_id, title=title, edition=edition, source_path=source_path)
            .on_conflict_do_nothing(index_elements=["book_id"])
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()


def upsert_chunks(chunks: list[TextbookChunkRecord]) -> int:
    """Insert or update textbook chunks.  Skip if content_hash unchanged."""
    session = get_session()
    upserted = 0
    try:
        for chunk in chunks:
            existing = session.get(TextbookChunk, chunk.chunk_id)
            if existing and existing.content_hash == chunk.content_hash:
                continue

            stmt = (
                pg_insert(TextbookChunk)
                .values(
                    chunk_id=chunk.chunk_id,
                    book_id=chunk.book_id,
                    chapter_num=chunk.chapter_num,
                    section_num=chunk.section_num,
                    subsection_num=chunk.subsection_num,
                    title=chunk.title,
                    summary=chunk.summary,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
                .on_conflict_do_update(
                    index_elements=["chunk_id"],
                    set_={
                        "title": chunk.title,
                        "summary": chunk.summary,
                        "content": chunk.content,
                        "content_hash": chunk.content_hash,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                    },
                )
            )
            session.execute(stmt)
            upserted += 1

        session.commit()
        logger.info("chunks_upserted", count=upserted)
    finally:
        session.close()
    return upserted


def save_images_to_s3(images: list[ExtractedImage], bucket: str) -> list[str]:
    """Upload images to S3 and return URLs.  Stores metadata in DB."""
    import boto3

    from ibrary.config import S3_ENDPOINT_URL

    s3_kwargs: dict = {}
    if S3_ENDPOINT_URL:
        s3_kwargs["endpoint_url"] = S3_ENDPOINT_URL
    s3 = boto3.client("s3", **s3_kwargs)

    urls: list[str] = []
    session = get_session()
    try:
        for img in images:
            key = f"textbook-images/{img.image_id}.{img.ext}"
            s3.put_object(Bucket=bucket, Key=key, Body=img.image_bytes)
            url = f"s3://{bucket}/{key}"
            urls.append(url)

            stmt = (
                pg_insert(TextbookImage)
                .values(
                    image_id=img.image_id,
                    chunk_id=img.chunk_id,
                    s3_url=url,
                    caption=img.caption,
                    alt_text=img.alt_text,
                    page_num=img.page_num,
                )
                .on_conflict_do_nothing(index_elements=["image_id"])
            )
            session.execute(stmt)

        session.commit()
        logger.info("images_uploaded", count=len(urls))
    except Exception:
        logger.warning("s3_upload_skipped", reason="S3 not available or bucket missing")
    finally:
        session.close()
    return urls


def save_images_locally(images: list[ExtractedImage], output_dir: str | Path) -> list[str]:
    """Fallback: save images to local directory when S3 is not configured."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for img in images:
        fname = f"{img.image_id}.{img.ext}"
        fpath = out / fname
        fpath.write_bytes(img.image_bytes)
        paths.append(str(fpath))
    logger.info("images_saved_locally", count=len(paths))
    return paths
