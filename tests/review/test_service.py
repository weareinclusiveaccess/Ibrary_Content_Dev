"""Unit tests for review service helpers."""

from __future__ import annotations

import pytest

from ibrary.review.service import (
    ALLOWED_STATUSES,
    _content_index_from_unit_id,
    _row_to_curated_module,
    reject_unit,
    update_status,
)


def test_allowed_statuses_include_verified():
    assert "verified" in ALLOWED_STATUSES
    assert "draft" in ALLOWED_STATUSES


def test_allowed_statuses_include_rejected():
    """Phase 1 step 6: reviewers can mark units as rejected with a reason."""
    assert "rejected" in ALLOWED_STATUSES


def test_update_status_rejects_invalid():
    with pytest.raises(ValueError, match="status must be one of"):
        update_status("bio_sss1_theme1_topic1_content0", "invalid_status")


def test_reject_unit_requires_non_empty_note():
    """Empty rejections are forbidden — every rejection must carry a reason."""
    with pytest.raises(ValueError, match="Reject note is required"):
        reject_unit("bio_sss1_theme1_topic1_content0", note="")
    with pytest.raises(ValueError, match="Reject note is required"):
        reject_unit("bio_sss1_theme1_topic1_content0", note="   ")


def test_content_index_from_unit_id_handles_known_shape():
    assert _content_index_from_unit_id("bio_sss1_theme1_topic1_content0") == 0
    assert _content_index_from_unit_id("bio_sss1_theme2_topic3_content7") == 7


def test_content_index_from_unit_id_defaults_to_zero_when_unknown_shape():
    """Garbage unit ids (or missing _content suffix) must not crash the publish path."""
    assert _content_index_from_unit_id("freeform-id-with-no-content-suffix") == 0
    assert _content_index_from_unit_id("bio_sss1_theme1_topic1_contentXYZ") == 0


def test_row_to_curated_module_handles_json_fields():
    """JSON-encoded TEXT columns must round-trip into list/dict CuratedModule fields."""
    import json
    from types import SimpleNamespace

    row = SimpleNamespace(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        subject="Biology",
        class_name="SSS 1",
        theme="Living things",
        theme_number=1,
        topic_number=1,
        subtopic="Cells",
        title="Cell structure",
        learning_objectives=json.dumps(["Identify cell parts"]),
        curated_content_md="# Cells\n\nCells are...",
        key_takeaways=json.dumps(["Cells are the unit of life"]),
        glossary_terms=json.dumps({"organelle": "subcellular component"}),
        student_activities=json.dumps(["Label a diagram"]),
        teacher_activities=json.dumps(["Microscope demo"]),
        accessibility_checklist=json.dumps(["Alt text provided"]),
        textbook_chunk_refs=json.dumps(["chunk-1", "chunk-2"]),
        model_version="gpt-5.1",
        prompt_version="curation_v3",
        status="verified",
    )
    module = _row_to_curated_module(row)
    assert module.curriculum_unit_id == "bio_sss1_theme1_topic1_content0"
    assert module.class_name == "SSS 1"
    assert module.learning_objectives == ["Identify cell parts"]
    assert module.glossary_terms == {"organelle": "subcellular component"}
    assert module.textbook_chunk_refs == ["chunk-1", "chunk-2"]
    assert module.status == "verified"


def test_row_to_curated_module_tolerates_null_text_columns():
    """Curriculum-only drafts have empty JSON fields; we must not crash."""
    from types import SimpleNamespace

    row = SimpleNamespace(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        subject="Biology",
        class_name="SSS 1",
        theme="Living things",
        theme_number=1,
        topic_number=1,
        subtopic="Cells",
        title="Cell structure",
        learning_objectives=None,
        curated_content_md=None,
        key_takeaways=None,
        glossary_terms=None,
        student_activities=None,
        teacher_activities=None,
        accessibility_checklist=None,
        textbook_chunk_refs=None,
        model_version=None,
        prompt_version=None,
        status="draft_curriculum_only",
    )
    module = _row_to_curated_module(row)
    assert module.learning_objectives == []
    assert module.glossary_terms == {}
    assert module.curated_content == ""
    assert module.model_version == ""


def _make_publish_row(unit_id: str, status: str):
    from types import SimpleNamespace

    return SimpleNamespace(
        curriculum_unit_id=unit_id,
        subject="Biology",
        class_name="SSS 1",
        theme="Living things",
        theme_number=1,
        topic_number=1,
        subtopic="Cells",
        title="Cell structure",
        learning_objectives="[]",
        curated_content_md="# Cells",
        key_takeaways="[]",
        glossary_terms="{}",
        student_activities="[]",
        teacher_activities="[]",
        accessibility_checklist="[]",
        textbook_chunk_refs="[]",
        model_version="gpt-5.1",
        prompt_version="curation_v3",
        status=status,
    )


def test_publish_all_units_to_dynamodb_writes_published_rows(monkeypatch):
    from unittest.mock import MagicMock

    from ibrary.review import service as review_service

    row = _make_publish_row("bio_sss1_theme1_topic1_content0", "published")
    session = MagicMock()
    query = session.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    ordered.all.return_value = [row]
    monkeypatch.setattr(review_service, "get_review_session", lambda: session)

    publish_calls: list[tuple] = []

    def fake_publish(module, content_index=0):
        publish_calls.append((module.curriculum_unit_id, content_index))

    monkeypatch.setattr(
        "ibrary.serving.dynamodb_writer.publish_module",
        fake_publish,
    )

    result = review_service.publish_all_units_to_dynamodb()
    assert result == ["bio_sss1_theme1_topic1_content0"]
    assert publish_calls == [("bio_sss1_theme1_topic1_content0", 0)]


def test_publish_all_units_to_dynamodb_dry_run_skips_dynamodb(monkeypatch):
    from unittest.mock import MagicMock

    from ibrary.review import service as review_service

    row = _make_publish_row("bio_sss1_theme1_topic1_content0", "verified")
    session = MagicMock()
    query = session.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    ordered.all.return_value = [row]
    monkeypatch.setattr(review_service, "get_review_session", lambda: session)

    def fail_publish(*_args, **_kwargs):
        raise AssertionError("publish_module should not run in dry_run")

    monkeypatch.setattr(
        "ibrary.serving.dynamodb_writer.publish_module",
        fail_publish,
    )

    result = review_service.publish_all_units_to_dynamodb(dry_run=True)
    assert result == ["bio_sss1_theme1_topic1_content0"]


def test_publish_all_units_to_dynamodb_raises_when_unit_missing(monkeypatch):
    from unittest.mock import MagicMock

    from ibrary.review import service as review_service

    session = MagicMock()
    query = session.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    ordered.all.return_value = []
    monkeypatch.setattr(review_service, "get_review_session", lambda: session)

    with pytest.raises(ValueError, match="not found in Postgres"):
        review_service.publish_all_units_to_dynamodb(unit_ids=["missing_unit"])

