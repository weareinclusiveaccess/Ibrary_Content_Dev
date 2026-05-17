"""FastAPI reviewer portal — list, read, judge, update status."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ibrary.review import service
from ibrary.review.auth import verify_review_key
from ibrary.review.schemas import (
    JudgeReportResponse,
    NotesRequest,
    StatusUpdateRequest,
    UnitDetailResponse,
    UnitListResponse,
)

_STATIC = Path(__file__).resolve().parent / "static"

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

if _STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    index_file = _STATIC / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"message": "Review API running. Add static/index.html or use /docs."}


@app.get("/review/units", response_model=UnitListResponse)
def list_units(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = None,
    theme_number: int | None = None,
    topic_number: int | None = None,
    q: str | None = None,
    _key: str = Depends(verify_review_key),
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
def get_unit(curriculum_unit_id: str, _key: str = Depends(verify_review_key)):
    unit = service.get_unit(curriculum_unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@app.get("/review/units/{curriculum_unit_id}/judge", response_model=JudgeReportResponse)
def get_judge(curriculum_unit_id: str, _key: str = Depends(verify_review_key)):
    return service.get_judge_report(curriculum_unit_id)


@app.patch("/review/units/{curriculum_unit_id}/status")
def patch_status(
    curriculum_unit_id: str,
    body: StatusUpdateRequest,
    _key: str = Depends(verify_review_key),
):
    try:
        ok = service.update_status(curriculum_unit_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"curriculum_unit_id": curriculum_unit_id, "status": body.status}


@app.post("/review/units/{curriculum_unit_id}/notes")
def post_notes(
    curriculum_unit_id: str,
    body: NotesRequest,
    _key: str = Depends(verify_review_key),
):
    ok = service.add_manual_note(
        curriculum_unit_id,
        notes=body.notes,
        overall_score=body.overall_score,
        checked_by=body.checked_by,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"saved": True}
