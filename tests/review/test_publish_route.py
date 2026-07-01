"""Route-level smoke tests for the publish-to-DynamoDB workflow.

We don't spin up DynamoDB or a real Postgres here — those are integration
concerns. The goal of this file is to exercise the *contract* of the two
new routes (`/reject` and `/publish-to-dynamodb`):

  - PORTAL_PUBLISH_ENABLED gates the publish route at 503
  - Reject route enforces a non-empty note (400) before touching the DB
  - Routes are wired up and reachable in the FastAPI app
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ibrary.review import api as review_api
from ibrary.review.auth import current_user, require_admin
from ibrary.review.cognito_jwt import CognitoClaims


@pytest.fixture
def admin_client():
    """FastAPI test client with admin auth dependency overridden — no JWT needed."""
    fake_admin = CognitoClaims(
        sub="test-admin",
        email="admin@example.com",
        groups=("admin",),
        raw={},
    )
    review_api.app.dependency_overrides[current_user] = lambda: fake_admin
    review_api.app.dependency_overrides[require_admin] = lambda: fake_admin
    try:
        yield TestClient(review_api.app)
    finally:
        review_api.app.dependency_overrides.clear()


def test_publish_route_returns_503_when_flag_off(admin_client):
    """When PORTAL_PUBLISH_ENABLED=false the route must refuse before touching DB."""
    with patch.object(review_api, "PORTAL_PUBLISH_ENABLED", False):
        resp = admin_client.post(
            "/review/units/bio_sss1_theme1_topic1_content0/publish-to-dynamodb"
        )
    assert resp.status_code == 503
    assert "PORTAL_PUBLISH_ENABLED" in resp.json()["detail"]


def test_publish_route_calls_service_when_flag_on(admin_client):
    """Flag on → route delegates to service.publish_unit_to_dynamodb."""
    with (
        patch.object(review_api, "PORTAL_PUBLISH_ENABLED", True),
        patch.object(
            review_api.service,
            "publish_unit_to_dynamodb",
            return_value="published",
        ) as mock_publish,
    ):
        resp = admin_client.post(
            "/review/units/bio_sss1_theme1_topic1_content0/publish-to-dynamodb"
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "curriculum_unit_id": "bio_sss1_theme1_topic1_content0",
        "status": "published",
        "published": True,
    }
    mock_publish.assert_called_once()
    _, kwargs = mock_publish.call_args
    assert kwargs.get("checked_by") == "admin@example.com"


def test_publish_route_returns_404_when_unit_missing(admin_client):
    with (
        patch.object(review_api, "PORTAL_PUBLISH_ENABLED", True),
        patch.object(
            review_api.service, "publish_unit_to_dynamodb", return_value=None
        ),
    ):
        resp = admin_client.post("/review/units/does_not_exist/publish-to-dynamodb")
    assert resp.status_code == 404


def test_publish_route_returns_400_on_wrong_status(admin_client):
    with (
        patch.object(review_api, "PORTAL_PUBLISH_ENABLED", True),
        patch.object(
            review_api.service,
            "publish_unit_to_dynamodb",
            side_effect=ValueError("Cannot publish from status 'draft'; unit must be 'verified' first"),
        ),
    ):
        resp = admin_client.post(
            "/review/units/bio_sss1_theme1_topic1_content0/publish-to-dynamodb"
        )
    assert resp.status_code == 400
    assert "verified" in resp.json()["detail"]


def test_reject_route_requires_note(admin_client):
    """Empty / whitespace-only notes must be rejected by pydantic min_length."""
    resp = admin_client.post(
        "/review/units/bio_sss1_theme1_topic1_content0/reject",
        json={"note": ""},
    )
    # pydantic returns 422 for body validation errors; this is the contract
    # the SPA's reject button relies on.
    assert resp.status_code == 422


def test_reject_route_returns_404_when_unit_missing(admin_client):
    with patch.object(review_api.service, "reject_unit", return_value=False) as mock_reject:
        resp = admin_client.post(
            "/review/units/does_not_exist/reject",
            json={"note": "Outdated content"},
        )
    assert resp.status_code == 404
    mock_reject.assert_called_once()


def test_reject_route_succeeds_with_note(admin_client):
    with patch.object(review_api.service, "reject_unit", return_value=True) as mock_reject:
        resp = admin_client.post(
            "/review/units/bio_sss1_theme1_topic1_content0/reject",
            json={"note": "Glossary terms are inconsistent with the textbook"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "curriculum_unit_id": "bio_sss1_theme1_topic1_content0",
        "status": "rejected",
    }
    _, kwargs = mock_reject.call_args
    assert kwargs["note"] == "Glossary terms are inconsistent with the textbook"
    # checked_by falls back to the authenticated admin's email when client omits it
    assert kwargs["checked_by"] == "admin@example.com"


def test_portal_config_returns_publish_flag(admin_client):
    with patch.object(review_api, "PORTAL_PUBLISH_ENABLED", True):
        resp = admin_client.get("/review/portal-config")
    assert resp.status_code == 200
    assert resp.json() == {"publish_enabled": True}

    with patch.object(review_api, "PORTAL_PUBLISH_ENABLED", False):
        resp = admin_client.get("/review/portal-config")
    assert resp.status_code == 200
    assert resp.json() == {"publish_enabled": False}
