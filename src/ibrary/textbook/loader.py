"""Load extracted textbook chunks into PostgreSQL (idempotent upsert)."""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ibrary.db import get_session
from ibrary.models import Textbook, TextbookChunk, TextbookImage
from ibrary.textbook.openstax_biology2e import ExtractedImage, TextbookChunkRecord

logger = structlog.get_logger(__name__)


def upsert_textbook(
    book_id: str,
    title: str,
    edition: str = "",
    source_path: str = "",
    subject: str | None = "biology",
) -> None:
    session = get_session()
    try:
        ins = pg_insert(Textbook).values(
            book_id=book_id,
            title=title,
            edition=edition,
            source_path=source_path,
            subject=subject,
        )
        stmt = ins.on_conflict_do_update(
            index_elements=["book_id"],
            set_={
                "title": ins.excluded.title,
                "edition": ins.excluded.edition,
                "source_path": ins.excluded.source_path,
                "subject": ins.excluded.subject,
            },
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

            ins = pg_insert(TextbookChunk).values(
                chunk_id=chunk.chunk_id,
                book_id=chunk.book_id,
                chapter_num=chunk.chapter_num,
                section_num=chunk.section_num,
                subsection_num=chunk.subsection_num,
                title=chunk.title,
                summary=chunk.summary,
                learning_objectives=chunk.learning_objectives,
                ancillary_content=chunk.ancillary_content,
                content=chunk.content,
                content_hash=chunk.content_hash,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
            )
            stmt = ins.on_conflict_do_update(
                index_elements=["chunk_id"],
                set_={
                    "title": ins.excluded.title,
                    "summary": ins.excluded.summary,
                    "learning_objectives": ins.excluded.learning_objectives,
                    "ancillary_content": ins.excluded.ancillary_content,
                    "content": ins.excluded.content,
                    "content_hash": ins.excluded.content_hash,
                    "page_start": ins.excluded.page_start,
                    "page_end": ins.excluded.page_end,
                },
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

            ins_img = pg_insert(TextbookImage).values(
                image_id=img.image_id,
                chunk_id=img.chunk_id,
                s3_url=url,
                caption=img.caption,
                alt_text=img.alt_text,
                page_num=img.page_num,
            )
            stmt = ins_img.on_conflict_do_update(
                index_elements=["image_id"],
                set_={
                    "chunk_id": ins_img.excluded.chunk_id,
                    "s3_url": ins_img.excluded.s3_url,
                    "caption": ins_img.excluded.caption,
                    "alt_text": ins_img.excluded.alt_text,
                    "page_num": ins_img.excluded.page_num,
                },
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
