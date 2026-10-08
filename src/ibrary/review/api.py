"""FastAPI reviewer portal — list, read, judge, update status."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ibrary.config import PROJECT_ROOT
from ibrary.review import service
from ibrary.config import (
    COGNITO_GROUP_ADMIN,
    COGNITO_GROUP_REVIEWER,
    COGNITO_REGION,
    COGNITO_USER_POOL_ID,
    PORTAL_PUBLISH_ENABLED,
)
from ibrary.review import cognito_admin, cognito_auth
from ibrary.review.auth import current_user, require_admin
from ibrary.review.cognito_jwt import CognitoClaims
from ibrary.review.schemas import (
    CognitoStatusResponse,
    CreatePortalUserRequest,
    ReviewLoginRequest,
    ReviewLoginResponse,
    ReviewLoginTokens,
    ReviewLoginUser,
    ReviewRefreshRequest,
    ReviewRefreshResponse,
    JudgeReportResponse,
    NotesRequest,
    PortalConfigResponse,
    PortalUserOut,
    PublishToDynamoResponse,
    RejectRequest,
    ReviewerNoteOut,
    ReviewerRubricRequest,
    ReviewerScoreOut,
    StatusUpdateRequest,
    UnitDetailResponse,
    UnitListResponse,
)

_UI_DIST = PROJECT_ROOT / "review-ui" / "dist"

app = FastAPI(
    title="IBrary Review Portal",
    version="0.1.0",
    description="Human review of curated biology modules (Postgres + UDL judge)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _UI_DIST.is_dir():
    assets_dir = _UI_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="ui-assets")


@app.get("/health")
def health():
    return {"status": "ok"}


def _spa_index() -> FileResponse | None:
    index_file = _UI_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return None


@app.get("/")
def index():
    spa = _spa_index()
    if spa:
        return spa
    return {"message": "Review API running. Build review-ui: cd review-ui && npm install && npm run build"}


@app.get("/review/units", response_model=UnitListResponse)
def list_units(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = None,
    theme_number: int | None = None,
    topic_number: int | None = None,
    q: str | None = None,
    _user: CognitoClaims = Depends(current_user),
):
    return service.list_units(
        offset=offset,
        limit=limit,
        status=status,
        theme_number=theme_number,
        topic_number=topic_number,
        q=q,
    )


@app.get("/review/units/{curriculum_unit_id}", response_model=UnitDetailResponse)
def get_unit(curriculum_unit_id: str, _user: CognitoClaims = Depends(current_user)):
    unit = service.get_unit(curriculum_unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@app.get("/review/units/{curriculum_unit_id}/judge", response_model=JudgeReportResponse)
def get_judge(curriculum_unit_id: str, _user: CognitoClaims = Depends(current_user)):
    return service.get_judge_report(curriculum_unit_id)


@app.patch("/review/units/{curriculum_unit_id}/status")
def patch_status(
    curriculum_unit_id: str,
    body: StatusUpdateRequest,
    _user: CognitoClaims = Depends(current_user),
):
    try:
        ok = service.update_status(curriculum_unit_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"curriculum_unit_id": curriculum_unit_id, "status": body.status}


@app.get("/review/units/{curriculum_unit_id}/notes", response_model=list[ReviewerNoteOut])
def get_notes(curriculum_unit_id: str, _user: CognitoClaims = Depends(current_user)):
    return service.list_notes(curriculum_unit_id)


@app.get(
    "/review/units/{curriculum_unit_id}/reviewer-scores",
    response_model=list[ReviewerScoreOut],
)
def get_reviewer_scores(
    curriculum_unit_id: str, _user: CognitoClaims = Depends(current_user)
):
    return service.list_reviewer_scores(curriculum_unit_id)


@app.post("/review/units/{curriculum_unit_id}/reviewer-scores")
def post_reviewer_rubric(
    curriculum_unit_id: str,
    body: ReviewerRubricRequest,
    user: CognitoClaims = Depends(current_user),
):
    ok = service.submit_reviewer_rubric(
        curriculum_unit_id,
        representation=body.representation,
        engagement=body.engagement,
        action_expression=body.action_expression,
        notes=body.notes,
        checked_by=body.checked_by or user.email,
        mark_verified=body.mark_verified,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"saved": True}


@app.post("/review/auth/login", response_model=ReviewLoginResponse)
def review_login(body: ReviewLoginRequest):
    if not cognito_auth.login_enabled():
        raise HTTPException(
            status_code=503,
            detail="Cognito login not configured. Set COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID.",
        )
    try:
        outcome = cognito_auth.sign_in(
            body.email,
            body.password,
            new_password=body.new_password,
            challenge_session=body.challenge_session,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if isinstance(outcome, cognito_auth.CognitoPasswordChallenge):
        return ReviewLoginResponse(
            challenge="NEW_PASSWORD_REQUIRED",
            challenge_session=outcome.session,
        )

    tokens = None
    if outcome.tokens is not None:
        tokens = ReviewLoginTokens(
            id_token=outcome.tokens.id_token,
            access_token=outcome.tokens.access_token,
            refresh_token=outcome.tokens.refresh_token,
            expires_in=outcome.tokens.expires_in,
            token_type=outcome.tokens.token_type,
        )

    return ReviewLoginResponse(
        user=ReviewLoginUser(
            email=outcome.email,
            role=outcome.role,
            name=outcome.name,
        ),
        tokens=tokens,
    )


@app.post("/review/auth/refresh", response_model=ReviewRefreshResponse)
def review_refresh(body: ReviewRefreshRequest):
    """Exchange a Cognito refresh token for new id/access tokens. No legacy auth required."""
    if not cognito_auth.login_enabled():
        raise HTTPException(
            status_code=503,
            detail="Cognito login not configured. Set COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID.",
        )
    try:
        tokens = cognito_auth.refresh_tokens(body.refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return ReviewRefreshResponse(
        tokens=ReviewLoginTokens(
            id_token=tokens.id_token,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            token_type=tokens.token_type,
        )
    )


@app.get("/review/admin/cognito-status", response_model=CognitoStatusResponse)
def cognito_status(_user: CognitoClaims = Depends(current_user)):
    return CognitoStatusResponse(
        enabled=cognito_admin.cognito_enabled(),
        login_enabled=cognito_auth.login_enabled(),
        user_pool_id=COGNITO_USER_POOL_ID or None,
        region=COGNITO_REGION or None,
        groups=[COGNITO_GROUP_ADMIN, COGNITO_GROUP_REVIEWER],
    )


@app.get("/review/portal-config", response_model=PortalConfigResponse)
def portal_config(_user: CognitoClaims = Depends(current_user)):
    """UI hints loaded once on app start so the SPA can branch on feature flags."""
    return PortalConfigResponse(publish_enabled=PORTAL_PUBLISH_ENABLED)


@app.post("/review/units/{curriculum_unit_id}/reject")
def reject_unit(
    curriculum_unit_id: str,
    body: RejectRequest,
    user: CognitoClaims = Depends(current_user),
):
    """Mark a unit as rejected with a required reviewer note (any authed user)."""
    try:
        ok = service.reject_unit(
            curriculum_unit_id,
            note=body.note,
            checked_by=body.checked_by or user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"curriculum_unit_id": curriculum_unit_id, "status": "rejected"}


@app.post(
    "/review/units/{curriculum_unit_id}/publish-to-dynamodb",
    response_model=PublishToDynamoResponse,
)
def publish_to_dynamodb(
    curriculum_unit_id: str,
    user: CognitoClaims = Depends(require_admin),
):
    """Admin-only: write a verified unit to DynamoDB and mark it published.

    Gated by PORTAL_PUBLISH_ENABLED — returns 503 with a clear message when the
    flag is off so the UI can fall back to a Postgres-only status update.
    """
    if not PORTAL_PUBLISH_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Publishing to DynamoDB is disabled. Set PORTAL_PUBLISH_ENABLED=true to enable.",
        )
    try:
        new_status = service.publish_unit_to_dynamodb(
            curriculum_unit_id, checked_by=user.email
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if new_status is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    return PublishToDynamoResponse(
        curriculum_unit_id=curriculum_unit_id,
        status=new_status,
        published=True,
    )


@app.get("/review/admin/users", response_model=list[PortalUserOut])
def list_portal_users(_admin: CognitoClaims = Depends(require_admin)):
    if not cognito_admin.cognito_enabled():
        raise HTTPException(
            status_code=503,
            detail="Cognito not configured. Set COGNITO_USER_POOL_ID on the API (terraform output).",
        )
    return [
        PortalUserOut(
            username=u.username,
            email=u.email,
            status=u.status,
            enabled=u.enabled,
            groups=u.groups,
        )
        for u in cognito_admin.list_portal_users()
    ]


@app.post("/review/admin/users", response_model=PortalUserOut)
def create_portal_user(
    body: CreatePortalUserRequest,
    _admin: CognitoClaims = Depends(require_admin),
):
    if not cognito_admin.cognito_enabled():
        raise HTTPException(status_code=503, detail="Cognito not configured")
    if body.role not in ("admin", "reviewer"):
        raise HTTPException(status_code=400, detail="role must be admin or reviewer")
    try:
        user = cognito_admin.create_portal_user(
            email=body.email,
            role=body.role,  # type: ignore[arg-type]
            temporary_password=body.temporary_password,
            send_invite=body.send_invite,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PortalUserOut(
        username=user.username,
        email=user.email,
        status=user.status,
        enabled=user.enabled,
        groups=user.groups,
    )


@app.post("/review/units/{curriculum_unit_id}/notes")
def post_notes(
    curriculum_unit_id: str,
    body: NotesRequest,
    user: CognitoClaims = Depends(current_user),
):
    ok = service.add_manual_note(
        curriculum_unit_id,
        notes=body.notes,
        overall_score=body.overall_score,
        checked_by=body.checked_by or user.email,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"saved": True}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """SPA client routes (must be registered after /review/* API routes)."""
    if full_path.startswith("review/units"):
        raise HTTPException(status_code=404, detail="Not found")
    if (
        full_path in ("queue",)
        or full_path.startswith("unit/")
        or full_path.startswith("admin/")
    ):
        spa = _spa_index()
        if spa:
            return spa
    raise HTTPException(status_code=404, detail="Not found")
