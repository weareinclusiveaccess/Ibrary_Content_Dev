"""Presigned HTTPS URLs for textbook images in S3."""

from __future__ import annotations

import structlog

from ibrary.config import AWS_DEFAULT_REGION, REVIEW_S3_PRESIGN_SECONDS, S3_ENDPOINT_URL

logger = structlog.get_logger(__name__)


def presign_s3_url(s3_url: str) -> str:
    """Return a short-lived HTTPS URL for ``s3://bucket/key``; passthrough on failure."""
    if not s3_url or not s3_url.startswith("s3://"):
        return s3_url
    try:
        import boto3
        from botocore.config import Config

        rest = s3_url[5:]
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            return s3_url

        client_kwargs: dict = {"region_name": AWS_DEFAULT_REGION}
        if S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = S3_ENDPOINT_URL
        client = boto3.client(
            "s3",
            config=Config(signature_version="s3v4"),
            **client_kwargs,
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=REVIEW_S3_PRESIGN_SECONDS,
        )
    except Exception as exc:
        logger.warning("s3_presign_failed", s3_url=s3_url, error=str(exc))
        return s3_url
