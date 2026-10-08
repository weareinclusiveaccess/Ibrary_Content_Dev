"""S3 key/URL helpers for subject-scoped textbook assets."""

from __future__ import annotations

from ibrary.config import PIPELINE_SUBJECT_SLUG, S3_BUCKET


def textbook_images_prefix(*, subject_slug: str | None = None) -> str:
    """Prefix inside the bucket, e.g. ``biology/textbook-images``."""
    slug = (subject_slug or PIPELINE_SUBJECT_SLUG).strip("/")
    return f"{slug}/textbook-images"


def textbook_image_s3_key(image_id: str, ext: str, *, subject_slug: str | None = None) -> str:
    """Object key: ``{subject}/textbook-images/{image_id}.{ext}``."""
    return f"{textbook_images_prefix(subject_slug=subject_slug)}/{image_id}.{ext}"


def textbook_image_s3_url(
    image_id: str,
    ext: str,
    *,
    bucket: str | None = None,
    subject_slug: str | None = None,
) -> str:
    """Full URI: ``s3://{bucket}/{subject}/textbook-images/{image_id}.{ext}``."""
    b = bucket or S3_BUCKET
    return f"s3://{b}/{textbook_image_s3_key(image_id, ext, subject_slug=subject_slug)}"
