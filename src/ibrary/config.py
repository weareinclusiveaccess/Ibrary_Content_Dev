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

# Review portal (Neon development branch or local); falls back to DATABASE_URL
DATABASE_URL_REVIEW: str = os.getenv("DATABASE_URL_REVIEW") or DATABASE_URL
REVIEW_API_HOST: str = os.getenv("REVIEW_API_HOST", "127.0.0.1")
REVIEW_API_PORT: int = int(os.getenv("REVIEW_API_PORT", "8090"))
REVIEW_S3_PRESIGN_SECONDS: int = int(os.getenv("REVIEW_S3_PRESIGN_SECONDS", "900"))

# Admin "Approve & publish" button wires through to DynamoDB only when this is true.
# Off by default so production environments can't accidentally publish before JWT
# auth + reject workflow have been exercised. Flip to "true" once cutover is ready.
PORTAL_PUBLISH_ENABLED: bool = os.getenv("PORTAL_PUBLISH_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)

# AWS region — defined before COGNITO_REGION because it falls back to this value.
AWS_DEFAULT_REGION: str = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

# Cognito (optional — user admin API + portal login)
COGNITO_USER_POOL_ID: str = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_APP_CLIENT_ID: str = os.getenv("COGNITO_APP_CLIENT_ID", "")
COGNITO_REGION: str = os.getenv("COGNITO_REGION") or AWS_DEFAULT_REGION
COGNITO_GROUP_ADMIN: str = os.getenv("COGNITO_GROUP_ADMIN", "admin")
COGNITO_GROUP_REVIEWER: str = os.getenv("COGNITO_GROUP_REVIEWER", "reviewer")

# PostgreSQL schema for all ORM tables (must match Alembic migrations)
POSTGRES_SCHEMA: str = os.getenv("POSTGRES_SCHEMA", "ibrary")

DYNAMODB_ENDPOINT_URL: str | None = os.getenv("DYNAMODB_ENDPOINT_URL")

S3_BUCKET: str = os.getenv("S3_BUCKET", "ibrary-content")
S3_ENDPOINT_URL: str | None = os.getenv("S3_ENDPOINT_URL") or None

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
# Chat model for judge and other non-curation calls (curation uses OPENAI_CURATION_* below).
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
# Include first N chars of chunk body in embedding text (0 = title/LO/summary only)
EMBEDDING_BODY_MAX_CHARS: int = int(os.getenv("EMBEDDING_BODY_MAX_CHARS", "2000"))

# Restrict vector search to curriculum textbook_chapters when available
ALIGNMENT_CHAPTER_FILTER: bool = os.getenv("ALIGNMENT_CHAPTER_FILTER", "true").lower() in (
    "1",
    "true",
    "yes",
)
# If chapter filter returns no matches, search all chapters
ALIGNMENT_CHAPTER_FILTER_FALLBACK: bool = os.getenv(
    "ALIGNMENT_CHAPTER_FILTER_FALLBACK", "true"
).lower() in ("1", "true", "yes")

# UDL curation (RAG → JSON module). GPT-5 family: set OPENAI_CURATION_REASONING_EFFORT (e.g. medium).
OPENAI_CURATION_MODEL: str = os.getenv("OPENAI_CURATION_MODEL", "gpt-5.1")
_curation_re_raw = os.getenv("OPENAI_CURATION_REASONING_EFFORT", "medium").strip().lower()
OPENAI_CURATION_REASONING_EFFORT: str | None = _curation_re_raw if _curation_re_raw else None

# filter_relevance step (per chunk × unit)
OPENAI_RELEVANCE_MODEL: str = os.getenv("OPENAI_RELEVANCE_MODEL", "gpt-4o-mini")

# curriculum refine: assign topic-level POs/activities to each subtopic
OPENAI_CURRICULUM_REFINE_MODEL: str = os.getenv("OPENAI_CURRICULUM_REFINE_MODEL", "gpt-4o-mini")
REFINE_TOPIC_PAUSE_SECONDS: float = float(os.getenv("REFINE_TOPIC_PAUSE_SECONDS", "2"))

# 1 = legacy full-chunk curation; 2 = align top-10 → filter_relevance → excerpt curation
PIPELINE_VERSION: int = int(os.getenv("PIPELINE_VERSION", "1"))

# v2 curate: PipelineOrchestrator (TextCurator → passthrough media/formula → assemble)
USE_CURATION_ORCHESTRATOR: bool = os.getenv(
    "USE_CURATION_ORCHESTRATOR", "true"
).lower() in ("1", "true", "yes")

# When filter_relevance leaves no excerpts, still curate from curriculum (not full alignment chunks)
CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS: bool = os.getenv(
    "CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS", "true"
).lower() in ("1", "true", "yes")

# Media / formula enrichment (Phase 2) — optional; orchestrator skips agents when not needed
OPENAI_ENRICHMENT_MODEL: str = os.getenv("OPENAI_ENRICHMENT_MODEL", "gpt-4o-mini")
CURATION_MAX_IMAGES: int = int(os.getenv("CURATION_MAX_IMAGES", "5"))
CURATION_MAX_FORMULAS: int = int(os.getenv("CURATION_MAX_FORMULAS", "12"))
MEDIA_TEXTBOOK_MIN_CONFIDENCE: float = float(os.getenv("MEDIA_TEXTBOOK_MIN_CONFIDENCE", "0.6"))
ENRICHMENT_ENABLE_IMAGES: bool = os.getenv("ENRICHMENT_ENABLE_IMAGES", "true").lower() in (
    "1",
    "true",
    "yes",
)
ENRICHMENT_ENABLE_FORMULAS: bool = os.getenv("ENRICHMENT_ENABLE_FORMULAS", "true").lower() in (
    "1",
    "true",
    "yes",
)
# When false (default), only run if TextCurator emitted placeholders (recommended)
ENRICHMENT_AUTO_IMAGES: bool = os.getenv("ENRICHMENT_AUTO_IMAGES", "false").lower() in (
    "1",
    "true",
    "yes",
)
ENRICHMENT_AUTO_FORMULAS: bool = os.getenv("ENRICHMENT_AUTO_FORMULAS", "false").lower() in (
    "1",
    "true",
    "yes",
)

ALIGNMENT_TOP_K: int = int(os.getenv("ALIGNMENT_TOP_K", "10"))
MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
ALIGNMENT_CONFIDENCE_THRESHOLD: float = float(
    os.getenv("ALIGNMENT_CONFIDENCE_THRESHOLD", "0.7")
)

JUDGE_PASS_THRESHOLD: float = float(os.getenv("JUDGE_PASS_THRESHOLD", "7.0"))
PROMPT_IMPROVEMENT_MIN_DELTA: float = float(os.getenv("PROMPT_IMPROVEMENT_MIN_DELTA", "0.25"))

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# LLM tracing (structlog + JSONL; optional LangSmith)
LLM_TRACE_ENABLED: bool = os.getenv("LLM_TRACE_ENABLED", "true").lower() in ("1", "true", "yes")
LLM_TRACE_LOG_PROMPTS: bool = os.getenv("LLM_TRACE_LOG_PROMPTS", "false").lower() in (
    "1",
    "true",
    "yes",
)
LLM_TRACE_JSONL_PATH: str = os.getenv("LLM_TRACE_JSONL_PATH", "data/logs/llm_traces.jsonl")
LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").lower() in ("1", "true", "yes")
LANGSMITH_API_KEY: str | None = os.getenv("LANGSMITH_API_KEY") or None
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "ibrary-pipeline")

# Subject-agnostic pipeline: display name for prompts (e.g. Biology, Chemistry)
PIPELINE_SUBJECT: str = os.getenv("PIPELINE_SUBJECT", "Biology")
# Slug for paths, unit-id prefixes, storage keys (e.g. biology, chemistry)
PIPELINE_SUBJECT_SLUG: str = os.getenv("PIPELINE_SUBJECT_SLUG", "biology")
# Curriculum system label used in refinement prompts
EDUCATION_SYSTEM_LABEL: str = os.getenv(
    "EDUCATION_SYSTEM_LABEL",
    "Nigerian Senior Secondary School",
)
