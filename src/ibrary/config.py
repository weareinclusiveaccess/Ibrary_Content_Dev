"""Central configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://ibrary:ibrary_dev@localhost:5432/ibrary",
)

DYNAMODB_ENDPOINT_URL: str | None = os.getenv("DYNAMODB_ENDPOINT_URL")
AWS_DEFAULT_REGION: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

S3_BUCKET: str = os.getenv("S3_BUCKET", "ibrary-content")
S3_ENDPOINT_URL: str | None = os.getenv("S3_ENDPOINT_URL") or None

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

ALIGNMENT_TOP_K: int = int(os.getenv("ALIGNMENT_TOP_K", "2"))
MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
ALIGNMENT_CONFIDENCE_THRESHOLD: float = float(
    os.getenv("ALIGNMENT_CONFIDENCE_THRESHOLD", "0.7")
)

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
