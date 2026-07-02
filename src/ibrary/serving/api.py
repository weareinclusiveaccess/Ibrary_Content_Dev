"""Internal read API over DynamoDB curated content."""

from __future__ import annotations

import os
from typing import Annotated

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Path, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader

from ibrary.config import (
    AWS_DEFAULT_REGION,
    CONTENT_API_CORS_ORIGINS,
    CONTENT_API_KEYS,
    DYNAMODB_ENDPOINT_URL,
    PIPELINE_SUBJECT,
)
from ibrary.serving.keys import TABLE_NAME, build_pk
from ibrary.serving.schemas import (
    ErrorResponse,
    HealthResponse,
    SubtopicItem,
    SubtopicListResponse,
    SubtopicSummaryItem,
    SubtopicSummaryListResponse,
    TopicItem,
    TopicListResponse,
)

_PUBLIC_URL = os.getenv(
    "CONTENT_API_PUBLIC_URL",
    "https://ibrary-content-api-latest.onrender.com",
)

app = FastAPI(
    title="IBrary Content API",
    version="0.3.0",
    description="""
Read-only HTTP API for published biology lesson content stored in DynamoDB.

## Authentication

All `/topics*` routes require the **`X-API-Key`** header. Click **Authorize** above
and paste the API key shared by the IBrary team.

`/health` is public (no key).

## Typical integration flow

1. `GET /topics` — list topics for a class + theme
2. `GET /topics/{topic_number}/subtopics/summary` — lightweight catalog (title + keys only)
3. `GET /topics/{topic_number}/subtopics/{content_index}` — fetch full lesson

## Important

- **`curated_content_md`** is Markdown — render to HTML in your app
- Fields like `key_takeaways`, `glossary_terms` are **JSON strings** — call `JSON.parse` (JS) or `json.loads` (Python)
- Map unit ID `bio_sss1_theme1_topic1_content0` → `theme_number=1`, `topic_number=1`, `content_index=0`
    """,
    openapi_tags=[
        {"name": "system", "description": "Health and metadata (no API key)"},
        {"name": "content", "description": "Curriculum topics and lessons (API key required)"},
    ],
    servers=[
        {"url": _PUBLIC_URL, "description": "Production (Render)"},
        {"url": "http://127.0.0.1:8080", "description": "Local development"},
    ],
)

_cors_origins = CONTENT_API_CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

API_KEY_HEADER = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key issued by IBrary. Required for all `/topics*` endpoints.",
)


def _get_table():
    kwargs: dict = {"region_name": AWS_DEFAULT_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(TABLE_NAME)


def _verify_key(key: str | None = Security(API_KEY_HEADER)):
    if not key or key not in CONTENT_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return key


def _dynamo_call(fn):
    try:
        return fn()
    except (ClientError, BotoCoreError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"DynamoDB unavailable: {exc}",
        ) from exc


ClassName = Annotated[
    str,
    Query(description="Nigerian curriculum class", examples=["SSS 1"]),
]
ThemeNumber = Annotated[
    int,
    Query(ge=1, description="Theme number (1–4)", examples=[1]),
]
Subject = Annotated[
    str,
    Query(description="Subject display name", examples=["Biology"]),
]
TopicNumberPath = Annotated[
    int,
    Path(ge=1, description="Topic number within the theme", examples=[1]),
]
ContentIndexPath = Annotated[
    int,
    Path(ge=0, description="Content item index (from `_content{N}` in unit ID)", examples=[0]),
]


@app.get("/", include_in_schema=False)
def root():
    """Redirect browsers to interactive Swagger docs."""
    return RedirectResponse(url="/docs")


@app.get(
    "/health",
    tags=["system"],
    summary="Health check",
    response_model=HealthResponse,
)
def health():
    """Liveness probe. Does not require authentication."""
    return HealthResponse(status="ok", table=TABLE_NAME, region=AWS_DEFAULT_REGION)


@app.get(
    "/topics",
    tags=["content"],
    summary="List topics",
    response_model=TopicListResponse,
    responses={403: {"model": ErrorResponse}},
)
def list_topics(
    class_name: ClassName = "SSS 1",
    theme_number: ThemeNumber = 1,
    subject: Subject = PIPELINE_SUBJECT,
    _key: str = Security(_verify_key),
):
    """Return topic metadata for a subject, class, and theme."""
    table = _get_table()
    pk = build_pk(subject, class_name, theme_number)

    def _query():
        return table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("TOPIC#"),
            FilterExpression="entity_type = :et",
            ExpressionAttributeValues={":et": "TOPIC"},
        )

    resp = _dynamo_call(_query)
    return TopicListResponse(topics=resp.get("Items", []))


@app.get(
    "/topics/{topic_number}",
    tags=["content"],
    summary="Get topic metadata",
    response_model=TopicItem,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_topic(
    topic_number: TopicNumberPath,
    class_name: ClassName = "SSS 1",
    theme_number: ThemeNumber = 1,
    subject: Subject = PIPELINE_SUBJECT,
    _key: str = Security(_verify_key),
):
    """Return metadata for a single topic."""
    table = _get_table()
    pk = build_pk(subject, class_name, theme_number)
    sk = f"TOPIC#{topic_number:02d}"

    def _get():
        return table.get_item(Key={"PK": pk, "SK": sk})

    resp = _dynamo_call(_get)
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Topic not found")
    return item


@app.get(
    "/topics/{topic_number}/subtopics",
    tags=["content"],
    summary="List subtopics (lessons)",
    response_model=SubtopicListResponse,
    responses={403: {"model": ErrorResponse}},
)
def list_subtopics(
    topic_number: TopicNumberPath,
    class_name: ClassName = "SSS 1",
    theme_number: ThemeNumber = 1,
    subject: Subject = PIPELINE_SUBJECT,
    _key: str = Security(_verify_key),
):
    """Return all lesson items (subtopics) for a topic."""
    table = _get_table()
    pk = build_pk(subject, class_name, theme_number)
    sk_prefix = f"TOPIC#{topic_number:02d}#CONTENT#"

    def _query():
        return table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix),
        )

    resp = _dynamo_call(_query)
    return SubtopicListResponse(subtopics=resp.get("Items", []))


@app.get(
    "/topics/{topic_number}/subtopics/summary",
    tags=["content"],
    summary="List subtopic catalog (lightweight)",
    response_model=SubtopicSummaryListResponse,
    responses={403: {"model": ErrorResponse}},
)
def list_subtopics_summary(
    topic_number: TopicNumberPath,
    class_name: ClassName = "SSS 1",
    theme_number: ThemeNumber = 1,
    subject: Subject = PIPELINE_SUBJECT,
    _key: str = Security(_verify_key),
):
    """
    Return a lightweight catalog of lessons for a topic: **subtopic**, **PK**, and **SK** only.

    Use this for navigation menus. Fetch full lesson content with
    `GET /topics/{topic_number}/subtopics/{content_index}` (parse `content_index`
    from the `SK` suffix, e.g. `TOPIC#01#CONTENT#2` → index `2`).
    """
    table = _get_table()
    pk = build_pk(subject, class_name, theme_number)
    sk_prefix = f"TOPIC#{topic_number:02d}#CONTENT#"

    def _query():
        return table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix),
            ProjectionExpression="PK, SK, subtopic",
        )

    resp = _dynamo_call(_query)
    items = [
        SubtopicSummaryItem(
            subtopic=item.get("subtopic", ""),
            PK=item["PK"],
            SK=item["SK"],
        )
        for item in resp.get("Items", [])
    ]
    return SubtopicSummaryListResponse(subtopics=items)


@app.get(
    "/topics/{topic_number}/subtopics/{content_index}",
    tags=["content"],
    summary="Get lesson content",
    response_model=SubtopicItem,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_subtopic(
    topic_number: TopicNumberPath,
    content_index: ContentIndexPath,
    class_name: ClassName = "SSS 1",
    theme_number: ThemeNumber = 1,
    subject: Subject = PIPELINE_SUBJECT,
    _key: str = Security(_verify_key),
):
    """
    Return the full lesson for a topic content item.

    This is the primary endpoint for the student app — use **`curated_content_md`**
    as the main body (Markdown).
    """
    table = _get_table()
    pk = build_pk(subject, class_name, theme_number)
    sk = f"TOPIC#{topic_number:02d}#CONTENT#{content_index}"

    def _get():
        return table.get_item(Key={"PK": pk, "SK": sk})

    resp = _dynamo_call(_get)
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Subtopic not found")
    return item
