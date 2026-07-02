"""Tests for the DynamoDB content read API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ibrary.serving import api as content_api


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(content_api, "CONTENT_API_KEYS", frozenset({"test-key"}))
    return TestClient(content_api.app)


def test_health_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["table"] == "CuratedContent"


def test_topics_requires_api_key(client):
    resp = client.get("/topics")
    assert resp.status_code == 403


@patch.object(content_api, "_get_table")
def test_list_topics_with_valid_key(mock_get_table, client):
    table = MagicMock()
    table.query.return_value = {"Items": [{"entity_type": "TOPIC", "topic_number": 1}]}
    mock_get_table.return_value = table

    resp = client.get("/topics", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    assert resp.json()["topics"][0]["topic_number"] == 1
    table.query.assert_called_once()


@patch.object(content_api, "_get_table")
def test_get_subtopic_not_found(mock_get_table, client):
    table = MagicMock()
    table.get_item.return_value = {}
    mock_get_table.return_value = table

    resp = client.get(
        "/topics/1/subtopics/99",
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 404
