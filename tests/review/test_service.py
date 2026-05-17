"""Unit tests for review service helpers."""

from __future__ import annotations

import pytest

from ibrary.review.service import ALLOWED_STATUSES, update_status


def test_allowed_statuses_include_verified():
    assert "verified" in ALLOWED_STATUSES
    assert "draft" in ALLOWED_STATUSES


def test_update_status_rejects_invalid():
    with pytest.raises(ValueError, match="status must be one of"):
        update_status("bio_sss1_theme1_topic1_content0", "invalid_status")
