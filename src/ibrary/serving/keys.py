"""DynamoDB partition/sort key helpers for the content read API."""

from __future__ import annotations

from ibrary.config import PIPELINE_SUBJECT

TABLE_NAME = "CuratedContent"


def build_pk(subject: str, class_name: str, theme_number: int) -> str:
    """Construct the DynamoDB partition key for a curated module.

    PK shape: SUBJECT#<Subject>#CLASS#<Class>#THEME#<N>
    """
    subj = (subject or PIPELINE_SUBJECT).strip() or PIPELINE_SUBJECT
    return f"SUBJECT#{subj}#CLASS#{class_name}#THEME#{theme_number}"
