"""Cognito ID token verification via JWKS.

Used by the reviewer API to authenticate every /review/* request. Caches
JWKS in process memory; Cognito JWKs are stable for the life of a user
pool, so no TTL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from ibrary.config import (
    COGNITO_APP_CLIENT_ID,
    COGNITO_GROUP_ADMIN,
    COGNITO_GROUP_REVIEWER,
    COGNITO_REGION,
    COGNITO_USER_POOL_ID,
)

logger = logging.getLogger(__name__)


class CognitoJwtError(Exception):
    """Raised when an incoming token cannot be verified."""


@dataclass(frozen=True)
class CognitoClaims:
    sub: str
    email: str
    groups: tuple[str, ...]
    raw: dict[str, Any]

    @property
    def role(self) -> str:
        if COGNITO_GROUP_ADMIN in self.groups:
            return "admin"
        if COGNITO_GROUP_REVIEWER in self.groups:
            return "reviewer"
        return ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def display_name(self) -> str:
        local = (self.email.split("@", 1)[0] if self.email else "").replace(".", " ").strip()
        return local.title() or self.email


_JWKS_CLIENT: PyJWKClient | None = None
_JWKS_LOCK = Lock()


def _issuer() -> str:
    return f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"


def _jwks_url() -> str:
    return f"{_issuer()}/.well-known/jwks.json"


def jwt_enabled() -> bool:
    return bool(COGNITO_USER_POOL_ID.strip() and COGNITO_APP_CLIENT_ID.strip())


def _get_jwks_client() -> PyJWKClient:
    global _JWKS_CLIENT
    if _JWKS_CLIENT is not None:
        return _JWKS_CLIENT
    with _JWKS_LOCK:
        if _JWKS_CLIENT is None:
            _JWKS_CLIENT = PyJWKClient(_jwks_url(), cache_keys=True)
    return _JWKS_CLIENT


def verify_id_token(token: str) -> CognitoClaims:
    """Verify a Cognito ID token. Raises CognitoJwtError on any failure."""
    if not jwt_enabled():
        raise CognitoJwtError("Cognito is not configured on the API")
    if not token:
        raise CognitoJwtError("Empty token")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError as exc:
        raise CognitoJwtError(f"Cannot fetch JWKS: {exc}") from exc
    except httpx.HTTPError as exc:
        raise CognitoJwtError(f"JWKS network error: {exc}") from exc
    except jwt.InvalidTokenError as exc:
        raise CognitoJwtError(f"Malformed token: {exc}") from exc

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=COGNITO_APP_CLIENT_ID,
            issuer=_issuer(),
            options={"require": ["exp", "iss", "aud", "token_use"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise CognitoJwtError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise CognitoJwtError(f"Invalid token: {exc}") from exc

    if claims.get("token_use") != "id":
        raise CognitoJwtError("Expected an ID token (token_use=id)")

    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):
        groups = [groups]

    return CognitoClaims(
        sub=str(claims.get("sub") or ""),
        email=str(claims.get("email") or ""),
        groups=tuple(groups),
        raw=claims,
    )
