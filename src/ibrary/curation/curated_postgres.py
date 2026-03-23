"""Persist curated modules to PostgreSQL ``curated_content`` (source of truth for drafts)."""

from __future__ import annotations

import datetime as dt
import json

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ibrary.curation.schemas import CuratedModule
from ibrary.db import get_session
from ibrary.models import CuratedContent

logger = structlog.get_logger(__name__)


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
        "images": [img.model_dump() for img in m.images] if m.images else None,
    }


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
