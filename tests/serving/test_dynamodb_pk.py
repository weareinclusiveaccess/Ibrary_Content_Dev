"""Subject is part of the DynamoDB partition key — guard against regression to a hardcoded subject."""

from __future__ import annotations

from ibrary.serving.dynamodb_writer import build_pk


def test_pk_includes_subject():
    pk = build_pk(subject="Biology", class_name="SSS 1", theme_number=1)
    assert pk == "SUBJECT#Biology#CLASS#SSS 1#THEME#1"


def test_pk_uses_provided_subject_not_default():
    pk = build_pk(subject="Chemistry", class_name="SSS 1", theme_number=2)
    assert pk.startswith("SUBJECT#Chemistry#")


def test_pk_falls_back_to_pipeline_subject_when_blank():
    from ibrary.config import PIPELINE_SUBJECT

    pk = build_pk(subject="", class_name="SSS 1", theme_number=1)
    assert pk == f"SUBJECT#{PIPELINE_SUBJECT}#CLASS#SSS 1#THEME#1"
