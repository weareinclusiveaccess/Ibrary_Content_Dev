"""Persist curated modules to PostgreSQL ``curated_content`` (source of truth for drafts)."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ibrary.curation.schemas import CuratedModule, FormulaRef, ImageRef, module_for_json_export
from ibrary.db import get_session
from ibrary.models import CuratedContent

logger = structlog.get_logger(__name__)


def _json_field(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _module_to_row(m: CuratedModule) -> dict:
    return {
        "curriculum_unit_id": m.curriculum_unit_id,
        "subject": m.subject,
        "class_name": m.class_name,
        "theme": m.theme,
        "theme_number": m.theme_number,
        "topic_number": m.topic_number,
        "subtopic": m.subtopic,
        "title": m.title,
        "learning_objectives": json.dumps(m.learning_objectives),
        "curated_content_md": m.curated_content,
        "key_takeaways": json.dumps(m.key_takeaways),
        "glossary_terms": json.dumps(m.glossary_terms),
        "student_activities": json.dumps(m.student_activities),
        "teacher_activities": json.dumps(m.teacher_activities),
        "accessibility_checklist": json.dumps(m.accessibility_checklist),
        "textbook_chunk_refs": json.dumps(m.textbook_chunk_refs),
        "model_version": m.model_version,
        "prompt_version": m.prompt_version,
        "status": m.status,
        "images": _enrichment_images_payload(m),
    }


def _enrichment_images_payload(m: CuratedModule) -> dict | list | None:
    """Store enrichment in JSON column when present (export-shaped, no placeholders)."""
    exported = module_for_json_export(m)
    images = exported.get("images")
    formulas = exported.get("formulas")
    if not images and not formulas:
        return None
    payload: dict = {}
    if images:
        payload["images"] = images
    if formulas:
        payload["formulas"] = formulas
    return payload


def _row_to_module(row: CuratedContent) -> CuratedModule:
    enrichment = row.images if isinstance(row.images, dict) else {}
    image_dicts = enrichment.get("images") or []
    formula_dicts = enrichment.get("formulas") or []
    return CuratedModule(
        curriculum_unit_id=row.curriculum_unit_id,
        subject=row.subject or "",
        **{"class": row.class_name or ""},
        theme=row.theme or "",
        theme_number=row.theme_number or 0,
        topic_number=row.topic_number or 0,
        subtopic=row.subtopic or "",
        title=row.title or "",
        learning_objectives=_json_field(row.learning_objectives, []),
        curated_content=row.curated_content_md or "",
        key_takeaways=_json_field(row.key_takeaways, []),
        glossary_terms=_json_field(row.glossary_terms, {}),
        student_activities=_json_field(row.student_activities, []),
        teacher_activities=_json_field(row.teacher_activities, []),
        accessibility_checklist=_json_field(row.accessibility_checklist, []),
        textbook_chunk_refs=_json_field(row.textbook_chunk_refs, []),
        model_version=row.model_version or "",
        prompt_version=row.prompt_version or "",
        status=row.status or "draft",
        images=[ImageRef.model_validate(i) for i in image_dicts if isinstance(i, dict)],
        formulas=[FormulaRef.model_validate(f) for f in formula_dicts if isinstance(f, dict)],
    )


def count_curated_modules_postgres() -> int:
    session = get_session()
    try:
        return session.query(CuratedContent).count()
    finally:
        session.close()


def iter_curated_modules_from_postgres() -> Iterator[CuratedModule]:
    """Yield curated modules one row at a time (low memory)."""
    session = get_session()
    try:
        query = session.query(CuratedContent).order_by(CuratedContent.curriculum_unit_id)
        for row in query.yield_per(1):
            yield _row_to_module(row)
    finally:
        session.close()


def upsert_curated_payloads(payloads: list[dict]) -> int:
    """Upsert all modules from JSON payloads (same shape as ``curated_content.json``)."""
    if not payloads:
        return 0
    session = get_session()
    now = dt.datetime.utcnow()
    try:
        for raw in payloads:
            m = CuratedModule.model_validate(raw)
            row = _module_to_row(m)
            ins = pg_insert(CuratedContent).values(**row)
            stmt = ins.on_conflict_do_update(
                index_elements=["curriculum_unit_id"],
                set_={
                    "subject": ins.excluded.subject,
                    "class_name": ins.excluded.class_name,
                    "theme": ins.excluded.theme,
                    "theme_number": ins.excluded.theme_number,
                    "topic_number": ins.excluded.topic_number,
                    "subtopic": ins.excluded.subtopic,
                    "title": ins.excluded.title,
                    "learning_objectives": ins.excluded.learning_objectives,
                    "curated_content_md": ins.excluded.curated_content_md,
                    "key_takeaways": ins.excluded.key_takeaways,
                    "glossary_terms": ins.excluded.glossary_terms,
                    "student_activities": ins.excluded.student_activities,
                    "teacher_activities": ins.excluded.teacher_activities,
                    "accessibility_checklist": ins.excluded.accessibility_checklist,
                    "textbook_chunk_refs": ins.excluded.textbook_chunk_refs,
                    "model_version": ins.excluded.model_version,
                    "prompt_version": ins.excluded.prompt_version,
                    "status": ins.excluded.status,
                    "images": ins.excluded.images,
                    "updated_at": now,
                },
            )
            session.execute(stmt)
        session.commit()
        logger.info("curated_upserted_postgres", rows=len(payloads))
        return len(payloads)
    finally:
        session.close()
