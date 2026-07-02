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


def test_swagger_docs(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()


def test_openapi_json(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "IBrary Content API"
    assert "/topics/{topic_number}/subtopics/{content_index}" in spec["paths"]


def test_root_redirects_to_docs(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/docs"


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
def test_list_subtopics_summary(mock_get_table, client):
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {
                "subtopic": "Characteristics of living things",
                "PK": "SUBJECT#Biology#CLASS#SSS 1#THEME#1",
                "SK": "TOPIC#01#CONTENT#0",
            }
        ]
    }
    mock_get_table.return_value = table

    resp = client.get(
        "/topics/1/subtopics/summary",
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["subtopics"] == [
        {
            "subtopic": "Characteristics of living things",
            "PK": "SUBJECT#Biology#CLASS#SSS 1#THEME#1",
            "SK": "TOPIC#01#CONTENT#0",
        }
    ]
    assert table.query.call_args.kwargs["ProjectionExpression"] == "PK, SK, subtopic"


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
