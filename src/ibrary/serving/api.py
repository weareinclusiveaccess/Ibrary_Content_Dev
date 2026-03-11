"""Internal read API over DynamoDB curated content."""

from __future__ import annotations

import json

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader

from ibrary.config import AWS_DEFAULT_REGION, DYNAMODB_ENDPOINT_URL

app = FastAPI(title="IBrary Content API (Internal)", version="0.1.0")

TABLE_NAME = "CuratedContent"
API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

# Set this via env or config for production
VALID_API_KEYS = {"dev-key-change-me"}


def _get_table():
    kwargs: dict = {"region_name": AWS_DEFAULT_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(TABLE_NAME)


def _verify_key(key: str = Security(API_KEY_HEADER)):
    if key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key


@app.get("/topics")
def list_topics(
    class_name: str = "SSS 1",
    theme_number: int = 1,
    _key: str = Security(_verify_key),
):
    """List all topics for a class and theme."""
    table = _get_table()
    pk = f"SUBJECT#Biology#CLASS#{class_name}#THEME#{theme_number}"
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("TOPIC#"),
        FilterExpression="entity_type = :et",
        ExpressionAttributeValues={":et": "TOPIC"},
    )
    return {"topics": resp.get("Items", [])}


@app.get("/topics/{topic_number}")
def get_topic(
    topic_number: int,
    class_name: str = "SSS 1",
    theme_number: int = 1,
    _key: str = Security(_verify_key),
):
    """Get a single topic."""
    table = _get_table()
    pk = f"SUBJECT#Biology#CLASS#{class_name}#THEME#{theme_number}"
    sk = f"TOPIC#{topic_number:02d}"
    resp = table.get_item(Key={"PK": pk, "SK": sk})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Topic not found")
    return item


@app.get("/topics/{topic_number}/subtopics")
def list_subtopics(
    topic_number: int,
    class_name: str = "SSS 1",
    theme_number: int = 1,
    _key: str = Security(_verify_key),
):
    """List subtopics (content items) for a topic."""
    table = _get_table()
    pk = f"SUBJECT#Biology#CLASS#{class_name}#THEME#{theme_number}"
    sk_prefix = f"TOPIC#{topic_number:02d}#CONTENT#"
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix),
    )
    return {"subtopics": resp.get("Items", [])}


@app.get("/topics/{topic_number}/subtopics/{content_index}")
def get_subtopic(
    topic_number: int,
    content_index: int,
    class_name: str = "SSS 1",
    theme_number: int = 1,
    _key: str = Security(_verify_key),
):
    """Get a single subtopic content item."""
    table = _get_table()
    pk = f"SUBJECT#Biology#CLASS#{class_name}#THEME#{theme_number}"
    sk = f"TOPIC#{topic_number:02d}#CONTENT#{content_index}"
    resp = table.get_item(Key={"PK": pk, "SK": sk})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Subtopic not found")
    return item
