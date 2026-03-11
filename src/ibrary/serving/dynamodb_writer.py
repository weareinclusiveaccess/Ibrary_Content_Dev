"""Write published (human-approved) curated content to DynamoDB."""

from __future__ import annotations

import json
import sys

import boto3
import structlog

from ibrary.config import AWS_DEFAULT_REGION, DYNAMODB_ENDPOINT_URL
from ibrary.curation.schemas import CuratedModule

logger = structlog.get_logger(__name__)

TABLE_NAME = "CuratedContent"
ITEM_SIZE_LIMIT = 400_000  # DynamoDB 400 KB limit


def _get_dynamo_resource():
    kwargs: dict = {"region_name": AWS_DEFAULT_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs)


def create_table() -> None:
    """Create the CuratedContent table in DynamoDB Local (idempotent)."""
    dynamo = _get_dynamo_resource()
    existing = [t.name for t in dynamo.tables.all()]
    if TABLE_NAME in existing:
        logger.info("table_exists", table=TABLE_NAME)
        return

    dynamo.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    logger.info("table_created", table=TABLE_NAME)


def _pk(module: CuratedModule) -> str:
    return f"SUBJECT#Biology#CLASS#{module.class_name}#THEME#{module.theme_number}"


def _topic_sk(module: CuratedModule) -> str:
    return f"TOPIC#{module.topic_number:02d}"


def _subtopic_sk(module: CuratedModule, content_index: int) -> str:
    return f"TOPIC#{module.topic_number:02d}#CONTENT#{content_index}"


def _check_size(item: dict) -> dict:
    """Truncate searchable_text if item exceeds DynamoDB size limit."""
    raw = json.dumps(item)
    if len(raw.encode()) > ITEM_SIZE_LIMIT:
        if "curated_content_md" in item:
            allowed = ITEM_SIZE_LIMIT - (len(raw.encode()) - len(item["curated_content_md"].encode()))
            item["curated_content_md"] = item["curated_content_md"][: max(0, allowed)] + "\n[truncated]"
        logger.warning("item_truncated", pk=item.get("PK"), sk=item.get("SK"))
    return item


def publish_module(module: CuratedModule, content_index: int = 0) -> None:
    """Write a single published module to DynamoDB as topic + subtopic items."""
    if module.status != "published":
        logger.warning("skip_unpublished", unit_id=module.curriculum_unit_id)
        return

    dynamo = _get_dynamo_resource()
    table = dynamo.Table(TABLE_NAME)
    pk = _pk(module)

    topic_item = _check_size({
        "PK": pk,
        "SK": _topic_sk(module),
        "entity_type": "TOPIC",
        "topic_number": module.topic_number,
        "topic": module.subtopic,
        "title": module.title,
        "learning_objectives": json.dumps(module.learning_objectives),
        "glossary_terms": json.dumps(module.glossary_terms),
    })
    table.put_item(Item=topic_item)

    subtopic_item = _check_size({
        "PK": pk,
        "SK": _subtopic_sk(module, content_index),
        "entity_type": "SUBTOPIC",
        "subtopic": module.subtopic,
        "curated_content_md": module.curated_content,
        "key_takeaways": json.dumps(module.key_takeaways),
        "glossary_terms": json.dumps(module.glossary_terms),
        "textbook_chunk_refs": json.dumps(module.textbook_chunk_refs),
        "model_version": module.model_version,
        "prompt_version": module.prompt_version,
        "curriculum_unit_id": module.curriculum_unit_id,
    })
    table.put_item(Item=subtopic_item)
    logger.info("published", unit_id=module.curriculum_unit_id)


def publish_curated_content(curated_json_path: str) -> int:
    """Load curated_content.json and publish all approved modules."""
    from pathlib import Path

    data = json.loads(Path(curated_json_path).read_text())
    count = 0
    for item in data:
        module = CuratedModule.model_validate(item)
        if module.status != "published":
            continue
        cindex = int(module.curriculum_unit_id.split("_content")[-1]) if "_content" in module.curriculum_unit_id else 0
        publish_module(module, content_index=cindex)
        count += 1
    logger.info("publish_complete", count=count)
    return count
