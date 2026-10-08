"""Business logic for reviewer portal (Postgres curated + judge data)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import func, or_

from ibrary.curation.schemas import CuratedModule
from ibrary.models import ContentManualQualityCheck, ContentUdlScore, CuratedContent
from ibrary.review.db import get_review_session
from ibrary.review.s3_presign import presign_s3_url
from ibrary.review.schemas import (
    CheckpointScoreOut,
    ImageAsset,
    JudgeReportResponse,
    ReviewerNoteOut,
    ReviewerScoreOut,
    UnitDetailResponse,
    UnitListItem,
    UnitListResponse,
)

ALLOWED_STATUSES = frozenset(
    {"draft", "draft_curriculum_only", "verified", "rejected", "published"}
)
# Postgres statuses eligible for bulk DynamoDB backfill (see publish_all_units_to_dynamodb).
DYNAMODB_BACKFILL_STATUSES = frozenset({"published", "verified"})
RUBRIC_SCORE_KEYS = ("representation", "engagement", "action_expression")


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


def _iso_dt(value: dt.datetime | None) -> str | None:
    if not value:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"


def _rubric_scores(raw: dict | None) -> dict[str, float] | None:
    if not raw:
        return None
    if raw.get("kind") == "rubric" or any(k in raw for k in RUBRIC_SCORE_KEYS):
        return {
            "representation": float(raw.get("representation") or 0),
            "engagement": float(raw.get("engagement") or 0),
            "action_expression": float(raw.get("action_expression") or 0),
        }
    return None


def _row_to_reviewer_score(row: ContentManualQualityCheck) -> ReviewerScoreOut | None:
    rubric = _rubric_scores(row.scores if isinstance(row.scores, dict) else None)
    if not rubric:
        return None
    overall = row.overall_score
    if overall is None:
        overall = round(
            (rubric["representation"] + rubric["engagement"] + rubric["action_expression"]) / 3,
            2,
        )
    return ReviewerScoreOut(
        id=row.id,
        reviewer=row.checked_by,
        date=_iso_dt(row.created_at),
        representation=rubric["representation"],
        engagement=rubric["engagement"],
        action_expression=rubric["action_expression"],
        overall_score=overall,
        notes=row.notes or "",
    )


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
                    theme=curated.theme,
                    theme_number=curated.theme_number,
                    topic_number=curated.topic_number,
                    status=curated.status or "draft",
                    overall_score=overall,
                    passed=passed,
                    updated_at=_iso_dt(curated.updated_at),
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
            updated_at=_iso_dt(row.updated_at),
        )
    finally:
        session.close()


def list_notes(curriculum_unit_id: str) -> list[ReviewerNoteOut]:
    session = get_review_session()
    try:
        rows = (
            session.query(ContentManualQualityCheck)
            .filter(ContentManualQualityCheck.curriculum_unit_id == curriculum_unit_id)
            .order_by(ContentManualQualityCheck.created_at.desc())
            .all()
        )
        out: list[ReviewerNoteOut] = []
        for row in rows:
            if not row.notes or not row.notes.strip():
                continue
            out.append(
                ReviewerNoteOut(
                    author=row.checked_by,
                    date=_iso_dt(row.created_at),
                    text=row.notes or "",
                )
            )
        return out
    finally:
        session.close()


def list_reviewer_scores(curriculum_unit_id: str) -> list[ReviewerScoreOut]:
    session = get_review_session()
    try:
        rows = (
            session.query(ContentManualQualityCheck)
            .filter(ContentManualQualityCheck.curriculum_unit_id == curriculum_unit_id)
            .order_by(ContentManualQualityCheck.created_at.desc())
            .all()
        )
        out: list[ReviewerScoreOut] = []
        for row in rows:
            score = _row_to_reviewer_score(row)
            if score:
                out.append(score)
        return out
    finally:
        session.close()


def submit_reviewer_rubric(
    curriculum_unit_id: str,
    *,
    representation: float,
    engagement: float,
    action_expression: float,
    notes: str = "",
    checked_by: str | None = None,
    mark_verified: bool = True,
) -> bool:
    session = get_review_session()
    try:
        row = (
            session.query(CuratedContent)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not row:
            return False
        overall = round((representation + engagement + action_expression) / 3, 2)
        session.add(
            ContentManualQualityCheck(
                curriculum_unit_id=curriculum_unit_id,
                notes=notes.strip() or None,
                overall_score=overall,
                checked_by=checked_by,
                scores={
                    "kind": "rubric",
                    "representation": representation,
                    "engagement": engagement,
                    "action_expression": action_expression,
                },
            )
        )
        if mark_verified:
            row.status = "verified"
            row.updated_at = dt.datetime.utcnow()
        session.commit()
        return True
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
            )
        )
        session.commit()
        return True
    finally:
        session.close()


def reject_unit(
    curriculum_unit_id: str,
    *,
    note: str,
    checked_by: str | None = None,
) -> bool:
    """Atomically mark a unit as rejected and record the reviewer's reason.

    Writes a `content_manual_quality_check` row holding the rejection note (so the
    audit trail captures who rejected it and why) and flips `curated_content.status`
    to `rejected`. A non-empty note is required — rejection without a reason is
    explicitly disallowed at the API layer too.

    Returns False if the unit doesn't exist; raises ValueError on empty note.
    """
    if not note or not note.strip():
        raise ValueError("Reject note is required")

    session = get_review_session()
    try:
        row = (
            session.query(CuratedContent)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not row:
            return False
        session.add(
            ContentManualQualityCheck(
                curriculum_unit_id=curriculum_unit_id,
                notes=note.strip(),
                checked_by=checked_by,
                scores={"kind": "rejection"},
            )
        )
        row.status = "rejected"
        row.updated_at = dt.datetime.utcnow()
        session.commit()
        return True
    finally:
        session.close()


def _content_index_from_unit_id(curriculum_unit_id: str) -> int:
    """Extract trailing _contentN suffix (default 0). Mirrors dynamodb_writer logic."""
    if "_content" in curriculum_unit_id:
        suffix = curriculum_unit_id.rsplit("_content", 1)[-1]
        try:
            return int(suffix)
        except ValueError:
            return 0
    return 0


def _row_to_curated_module(row: CuratedContent) -> CuratedModule:
    """Project a Postgres CuratedContent row into the DynamoDB-publishable shape.

    Only fills fields that `dynamodb_writer.publish_module` actually reads. Optional
    enrichment (images, formulas, content_blocks, assets) is intentionally left
    empty: the DynamoDB topic + subtopic items don't store them, and pulling
    images here would unnecessarily reach S3 from a publish path.
    """
    return CuratedModule(
        curriculum_unit_id=row.curriculum_unit_id,
        subject=row.subject,
        # Pydantic alias: CuratedModule field is `class_name`, alias is "class".
        # `populate_by_name=True` on the model lets us pass class_name directly.
        class_name=row.class_name,
        theme=row.theme or "",
        theme_number=int(row.theme_number or 0),
        topic_number=int(row.topic_number or 0),
        subtopic=row.subtopic or "",
        title=row.title or "",
        learning_objectives=_json_list(row.learning_objectives),
        curated_content=row.curated_content_md or "",
        key_takeaways=_json_list(row.key_takeaways),
        glossary_terms=_json_dict(row.glossary_terms),
        student_activities=_json_list(row.student_activities),
        teacher_activities=_json_list(row.teacher_activities),
        accessibility_checklist=_json_list(row.accessibility_checklist),
        textbook_chunk_refs=_json_list(row.textbook_chunk_refs),
        model_version=row.model_version or "",
        prompt_version=row.prompt_version or "",
        status=row.status or "draft",
    )


def publish_unit_to_dynamodb(
    curriculum_unit_id: str,
    *,
    checked_by: str | None = None,
) -> str | None:
    """Publish a single verified unit to DynamoDB and mark Postgres as published.

    Flow:
      1. Load curated row (review session)
      2. Refuse unless status == "verified"  (already-published is a no-op success)
      3. Build CuratedModule, call dynamodb_writer.publish_module
      4. On success, flip Postgres status to "published" and record an audit note

    Returns the new status string on success ("published"), None if the unit
    doesn't exist. Raises ValueError if the unit is in a non-publishable status.

    Imported lazily so the review module doesn't pull boto3 at import time —
    keeps the no-DynamoDB local dev path snappy.
    """
    from ibrary.serving import dynamodb_writer  # local import — avoid boto3 at module load

    session = get_review_session()
    try:
        row = (
            session.query(CuratedContent)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not row:
            return None
        if row.status == "published":
            # Idempotent: re-publishing an already-published unit is a successful no-op.
            return "published"
        if row.status != "verified":
            raise ValueError(
                f"Cannot publish from status '{row.status}'; unit must be 'verified' first"
            )

        module = _row_to_curated_module(row)
        cindex = _content_index_from_unit_id(curriculum_unit_id)
        # publish_module raises on any boto3 error — we deliberately let it
        # propagate so the caller (API route) returns 500 with the AWS detail.
        dynamodb_writer.publish_module(module, content_index=cindex)

        # Audit trail: who published the unit, when, and from which version.
        session.add(
            ContentManualQualityCheck(
                curriculum_unit_id=curriculum_unit_id,
                notes=f"Published to DynamoDB (prompt={row.prompt_version}, model={row.model_version})",
                checked_by=checked_by,
                scores={"kind": "publish"},
            )
        )
        row.status = "published"
        row.updated_at = dt.datetime.utcnow()
        session.commit()
        return "published"
    finally:
        session.close()


def publish_all_units_to_dynamodb(
    *,
    statuses: frozenset[str] | None = None,
    unit_ids: list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Push curated rows from Postgres to DynamoDB (bulk backfill / re-publish).

    Unlike ``publish_unit_to_dynamodb`` (portal path), this writes units that are
    already ``published`` in Postgres — for backfill when DynamoDB was empty but
    the portal marked Postgres published with ``PORTAL_PUBLISH_ENABLED=false``.

    Each unit becomes two DynamoDB items (TOPIC + SUBTOPIC). Re-publishing the
    same unit overwrites those items; it does not create duplicate keys.

    Returns curriculum_unit_ids written (or that would be written when dry_run).
    """
    from ibrary.serving import dynamodb_writer  # local import — avoid boto3 at module load

    allowed = statuses if statuses is not None else DYNAMODB_BACKFILL_STATUSES
    unknown = allowed - ALLOWED_STATUSES
    if unknown:
        raise ValueError(f"Unknown status filter(s): {', '.join(sorted(unknown))}")

    session = get_review_session()
    try:
        query = session.query(CuratedContent)
        if unit_ids:
            query = query.filter(CuratedContent.curriculum_unit_id.in_(unit_ids))
        if allowed:
            query = query.filter(CuratedContent.status.in_(sorted(allowed)))
        rows = query.order_by(CuratedContent.curriculum_unit_id).all()

        if unit_ids:
            found = {row.curriculum_unit_id for row in rows}
            missing = [uid for uid in unit_ids if uid not in found]
            if missing:
                raise ValueError(f"Unit(s) not found in Postgres: {', '.join(missing)}")

        published_ids: list[str] = []
        for row in rows:
            if dry_run:
                published_ids.append(row.curriculum_unit_id)
                continue
            module = _row_to_curated_module(row)
            cindex = _content_index_from_unit_id(row.curriculum_unit_id)
            dynamodb_writer.publish_module(module, content_index=cindex)
            published_ids.append(row.curriculum_unit_id)
        return published_ids
    finally:
        session.close()
