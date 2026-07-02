"""Configuration for the DynamoDB content read API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load shared project .env first, then optional content-api overrides.
# Use .env.content-api for API-only vars — never overwrite your main .env.
load_dotenv()
load_dotenv(Path(".env.content-api"), override=False)

AWS_DEFAULT_REGION: str = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
DYNAMODB_ENDPOINT_URL: str | None = os.getenv("DYNAMODB_ENDPOINT_URL") or None

PIPELINE_SUBJECT: str = os.getenv("PIPELINE_SUBJECT", "Biology")

CONTENT_API_HOST: str = os.getenv("CONTENT_API_HOST", "127.0.0.1")
CONTENT_API_PORT: int = int(os.getenv("CONTENT_API_PORT", "8080"))
_content_api_keys_raw = os.getenv("CONTENT_API_KEYS", "dev-key-change-me")
CONTENT_API_KEYS: frozenset[str] = frozenset(
    key.strip() for key in _content_api_keys_raw.split(",") if key.strip()
)
CONTENT_API_CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CONTENT_API_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
