"""Business logic for reviewer portal (Postgres curated + judge data)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import func, or_

from ibrary.models import ContentManualQualityCheck, ContentUdlScore, CuratedContent
from ibrary.review.db import get_review_session
from ibrary.review.s3_presign import presign_s3_url
from ibrary.review.schemas import (
    CheckpointScoreOut,
    ImageAsset,
    JudgeReportResponse,
    UnitDetailResponse,
    UnitListItem,
    UnitListResponse,
)

ALLOWED_STATUSES = frozenset({"draft", "draft_curriculum_only", "verified", "published"})


def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _images_from_row(row: CuratedContent) -> list[ImageAsset]:
    enrichment = row.images if isinstance(row.images, dict) else {}
    out: list[ImageAsset] = []
    for item in enrichment.get("images") or []:
        if not isinstance(item, dict):
            continue
        s3_url = item.get("s3_url") or ""
        out.append(
            ImageAsset(
                image_id=item.get("image_id") or "",
                caption=item.get("caption") or "",
                alt_text=item.get("alt_text") or "",
                s3_url=s3_url,
                display_url=presign_s3_url(s3_url) if s3_url else "",
            )
        )
    return out


def _judge_from_scores(scores: dict[str, Any] | None) -> tuple[float | None, bool | None]:
    if not scores:
        return None, None
    return scores.get("overall_score"), scores.get("passed")


def list_units(
    *,
    offset: int = 0,
    limit: int = 50,
    status: str | None = None,
    theme_number: int | None = None,
    topic_number: int | None = None,
    q: str | None = None,
) -> UnitListResponse:
    session = get_review_session()
    try:
        query = session.query(CuratedContent, ContentUdlScore).outerjoin(
            ContentUdlScore,
            CuratedContent.curriculum_unit_id == ContentUdlScore.curriculum_unit_id,
        )
        if status:
            query = query.filter(CuratedContent.status == status)
        if theme_number is not None:
            query = query.filter(CuratedContent.theme_number == theme_number)
        if topic_number is not None:
            query = query.filter(CuratedContent.topic_number == topic_number)
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                or_(
                    CuratedContent.curriculum_unit_id.ilike(pattern),
                    CuratedContent.title.ilike(pattern),
                    CuratedContent.subtopic.ilike(pattern),
                )
            )

        count_q = session.query(func.count(CuratedContent.curriculum_unit_id))
        if status:
            count_q = count_q.filter(CuratedContent.status == status)
        if theme_number is not None:
            count_q = count_q.filter(CuratedContent.theme_number == theme_number)
        if topic_number is not None:
            count_q = count_q.filter(CuratedContent.topic_number == topic_number)
        if q:
            pattern = f"%{q}%"
            count_q = count_q.filter(
                or_(
                    CuratedContent.curriculum_unit_id.ilike(pattern),
                    CuratedContent.title.ilike(pattern),
                    CuratedContent.subtopic.ilike(pattern),
                )
            )
        total = count_q.scalar() or 0
        rows = (
            query.order_by(
                CuratedContent.theme_number,
                CuratedContent.topic_number,
                CuratedContent.curriculum_unit_id,
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        items: list[UnitListItem] = []
        for curated, judge in rows:
            scores = judge.scores if judge and isinstance(judge.scores, dict) else {}
            overall = judge.overall_score if judge else scores.get("overall_score")
            passed = scores.get("passed") if scores else None
            items.append(
                UnitListItem(
                    curriculum_unit_id=curated.curriculum_unit_id,
                    title=curated.title,
                    subtopic=curated.subtopic,
                    class_name=curated.class_name,
                    theme_number=curated.theme_number,
                    topic_number=curated.topic_number,
                    status=curated.status or "draft",
                    overall_score=overall,
                    passed=passed,
                )
            )
        return UnitListResponse(items=items, total=total, offset=offset, limit=limit)
    finally:
        session.close()


def get_unit(curriculum_unit_id: str) -> UnitDetailResponse | None:
    session = get_review_session()
    try:
        row = (
            session.query(CuratedContent)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not row:
            return None
        return UnitDetailResponse(
            curriculum_unit_id=row.curriculum_unit_id,
            title=row.title,
            subtopic=row.subtopic,
            class_name=row.class_name,
            theme=row.theme,
            theme_number=row.theme_number,
            topic_number=row.topic_number,
            status=row.status or "draft",
            learning_objectives=_json_list(row.learning_objectives),
            curated_content_md=row.curated_content_md or "",
            key_takeaways=_json_list(row.key_takeaways),
            student_activities=_json_list(row.student_activities),
            teacher_activities=_json_list(row.teacher_activities),
            accessibility_checklist=_json_list(row.accessibility_checklist),
            images=_images_from_row(row),
            prompt_version=row.prompt_version,
            model_version=row.model_version,
        )
    finally:
        session.close()


def get_judge_report(curriculum_unit_id: str) -> JudgeReportResponse | None:
    session = get_review_session()
    try:
        judge = (
            session.query(ContentUdlScore)
            .filter(ContentUdlScore.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not judge:
            return JudgeReportResponse(curriculum_unit_id=curriculum_unit_id)

        scores = judge.scores if isinstance(judge.scores, dict) else {}
        checkpoints = []
        for cp in scores.get("checkpoint_scores") or []:
            if isinstance(cp, dict):
                checkpoints.append(
                    CheckpointScoreOut(
                        checkpoint_id=cp.get("checkpoint_id") or "",
                        principle=cp.get("principle") or "",
                        principle_display=cp.get("principle_display") or "",
                        score=float(cp.get("score") or 0),
                        notes=cp.get("notes") or "",
                    )
                )

        return JudgeReportResponse(
            curriculum_unit_id=curriculum_unit_id,
            overall_score=judge.overall_score,
            passed=scores.get("passed"),
            representation_score=scores.get("representation_score"),
            engagement_score=scores.get("engagement_score"),
            action_expression_score=scores.get("action_expression_score"),
            correctness_score=scores.get("correctness_score"),
            correctness_notes=scores.get("correctness_notes") or "",
            clarity_score=scores.get("clarity_score"),
            clarity_notes=scores.get("clarity_notes") or "",
            checkpoint_scores=checkpoints,
            recommendations=list(scores.get("recommendations") or []),
            judge_prompt_version=judge.judge_prompt_version,
            judge_model_version=judge.judge_model_version,
            error=scores.get("error"),
        )
    finally:
        session.close()


def update_status(curriculum_unit_id: str, status: str) -> bool:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}")

    session = get_review_session()
    try:
        row = (
            session.query(CuratedContent)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not row:
            return False
        row.status = status
        row.updated_at = dt.datetime.utcnow()
        session.commit()
        return True
    finally:
        session.close()


def add_manual_note(
    curriculum_unit_id: str,
    *,
    notes: str,
    overall_score: float | None = None,
    checked_by: str | None = None,
) -> bool:
    session = get_review_session()
    try:
        exists = (
            session.query(CuratedContent.curriculum_unit_id)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .scalar()
        )
        if not exists:
            return False
        session.add(
            ContentManualQualityCheck(
                curriculum_unit_id=curriculum_unit_id,
                notes=notes,
                overall_score=overall_score,
                checked_by=checked_by,
                checked_at=dt.datetime.utcnow(),
            )
        )
        session.commit()
        return True
    finally:
        session.close()
