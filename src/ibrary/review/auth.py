"""Reviewer API authentication (dev API key; Cognito later)."""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from ibrary.config import REVIEW_API_KEY

REVIEW_KEY_HEADER = APIKeyHeader(name="X-Review-Api-Key", auto_error=False)


def verify_review_key(key: str | None = Security(REVIEW_KEY_HEADER)) -> str:
    if not key or key != REVIEW_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Review-Api-Key")
    return key
