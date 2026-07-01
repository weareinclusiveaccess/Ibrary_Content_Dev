"""Cognito username/password sign-in for the reviewer portal."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from ibrary.config import (
    COGNITO_APP_CLIENT_ID,
    COGNITO_GROUP_ADMIN,
    COGNITO_GROUP_REVIEWER,
    COGNITO_REGION,
    COGNITO_USER_POOL_ID,
)
from ibrary.review.cognito_admin import UserRole, cognito_enabled


@dataclass
class CognitoTokens:
    id_token: str
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str = "Bearer"


@dataclass
class CognitoSignInResult:
    email: str
    role: UserRole
    name: str
    tokens: CognitoTokens | None = None


@dataclass
class CognitoPasswordChallenge:
    session: str
    email: str


def login_enabled() -> bool:
    return cognito_enabled() and bool(COGNITO_APP_CLIENT_ID.strip())


def _client():
    import boto3

    return boto3.client("cognito-idp", region_name=COGNITO_REGION)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def _role_from_id_token(id_token: str) -> UserRole:
    claims = _decode_jwt_payload(id_token)
    groups = claims.get("cognito:groups") or []
    if COGNITO_GROUP_ADMIN in groups:
        return "admin"
    if COGNITO_GROUP_REVIEWER in groups:
        return "reviewer"
    raise ValueError("User is not in admin or reviewer Cognito group")


def _tokens_from_auth(auth_result: dict[str, Any]) -> CognitoTokens:
    id_token = auth_result.get("IdToken") or ""
    access_token = auth_result.get("AccessToken") or ""
    refresh_token = auth_result.get("RefreshToken") or None
    expires_in = int(auth_result.get("ExpiresIn") or 0)
    token_type = auth_result.get("TokenType") or "Bearer"
    return CognitoTokens(
        id_token=id_token,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type=token_type,
    )


def _result_from_auth(email: str, auth_result: dict[str, Any]) -> CognitoSignInResult:
    id_token = auth_result.get("IdToken")
    if not id_token:
        raise ValueError("Sign-in did not return an ID token")
    role = _role_from_id_token(id_token)
    local = email.split("@")[0].replace(".", " ").title()
    return CognitoSignInResult(
        email=email,
        role=role,
        name=local or email,
        tokens=_tokens_from_auth(auth_result),
    )


def refresh_tokens(refresh_token: str) -> CognitoTokens:
    """Exchange a refresh token for fresh id/access tokens.

    Cognito does not issue a new refresh token from REFRESH_TOKEN_AUTH; the
    caller keeps the same refresh token until it expires.
    """
    if not login_enabled():
        raise RuntimeError("Cognito login is not configured on the API")
    if not refresh_token:
        raise ValueError("refresh_token is required")

    client = _client()
    resp = client.initiate_auth(
        ClientId=COGNITO_APP_CLIENT_ID,
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": refresh_token},
    )
    auth = resp.get("AuthenticationResult")
    if not auth:
        raise ValueError("Refresh did not return tokens")
    tokens = _tokens_from_auth(auth)
    if tokens.refresh_token is None:
        tokens = CognitoTokens(
            id_token=tokens.id_token,
            access_token=tokens.access_token,
            refresh_token=refresh_token,
            expires_in=tokens.expires_in,
            token_type=tokens.token_type,
        )
    return tokens


def sign_in(
    email: str,
    password: str,
    *,
    new_password: str | None = None,
    challenge_session: str | None = None,
) -> CognitoSignInResult | CognitoPasswordChallenge:
    if not login_enabled():
        raise RuntimeError("Cognito login is not configured on the API")

    email = email.strip().lower()
    client = _client()

    if challenge_session and new_password:
        resp = client.respond_to_auth_challenge(
            ClientId=COGNITO_APP_CLIENT_ID,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=challenge_session,
            ChallengeResponses={
                "USERNAME": email,
                "NEW_PASSWORD": new_password,
            },
        )
        if resp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
            return CognitoPasswordChallenge(
                session=resp["Session"],
                email=email,
            )
        auth = resp.get("AuthenticationResult")
        if not auth:
            raise ValueError("Password change did not complete")
        return _result_from_auth(email, auth)

    resp = client.initiate_auth(
        ClientId=COGNITO_APP_CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )

    if resp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
        return CognitoPasswordChallenge(session=resp["Session"], email=email)

    auth = resp.get("AuthenticationResult")
    if not auth:
        raise ValueError("Sign-in failed")
    return _result_from_auth(email, auth)
