"""Reviewer API authentication via Cognito JWT.

Every /review/* route except /review/auth/login and /review/auth/refresh
expects `Authorization: Bearer <Cognito ID token>`. Admin-only routes
additionally check that the user belongs to the Cognito `admin` group.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ibrary.review.cognito_jwt import (
    CognitoClaims,
    CognitoJwtError,
    jwt_enabled,
    verify_id_token,
)

BEARER_SCHEME = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(BEARER_SCHEME),
) -> CognitoClaims:
    """Validate `Authorization: Bearer <Cognito ID token>` and return claims."""
    if not jwt_enabled():
        raise HTTPException(
            status_code=503,
            detail="Cognito JWT not configured. Set COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID.",
        )
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    try:
        return verify_id_token(credentials.credentials)
    except CognitoJwtError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_admin(claims: CognitoClaims = Depends(current_user)) -> CognitoClaims:
    if not claims.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return claims
