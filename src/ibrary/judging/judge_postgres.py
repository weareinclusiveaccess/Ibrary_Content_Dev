"""Persist UDL judge results to PostgreSQL ``content_udl_scores``."""

from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ibrary.config import OPENAI_MODEL
from ibrary.db import get_session
from ibrary.judging.schemas import SubtopicJudgeResult
from ibrary.judging.prompts import get_judge_prompt_version
from ibrary.models import ContentUdlScore

logger = structlog.get_logger(__name__)


def _result_to_scores_payload(result: SubtopicJudgeResult) -> dict:
    return {
        "checkpoint_scores": [c.model_dump() for c in result.checkpoint_scores],
        "representation_score": result.representation_score,
        "action_expression_score": result.action_expression_score,
        "engagement_score": result.engagement_score,
        "correctness_score": result.correctness_score,
        "correctness_notes": result.correctness_notes,
        "clarity_score": result.clarity_score,
        "clarity_notes": result.clarity_notes,
        "passed": result.passed,
        "recommendations": result.recommendations,
        "error": result.error,
        "subject": result.subject,
        "subtopic": result.subtopic,
        "prompt_version": result.prompt_version,
        "model_version": result.model_version,
        "judge_prompt_version": result.judge_prompt_version,
        "judge_model_version": result.judge_model_version,
    }


def upsert_judge_result(result: SubtopicJudgeResult) -> None:
    """Upsert one judge result row (requires matching ``curated_content`` row)."""
    if not result.curriculum_unit_id:
        logger.warning("judge_upsert_skipped", reason="missing_curriculum_unit_id")
        return

    session = get_session()
    now = dt.datetime.utcnow()
    try:
        row = {
            "curriculum_unit_id": result.curriculum_unit_id,
            "overall_score": result.overall_score,
            "scores": _result_to_scores_payload(result),
            "judge_model_version": result.judge_model_version or OPENAI_MODEL,
            "judge_prompt_version": result.judge_prompt_version or get_judge_prompt_version(),
        }
        ins = pg_insert(ContentUdlScore).values(**row)
        stmt = ins.on_conflict_do_update(
            index_elements=["curriculum_unit_id"],
            set_={
                "overall_score": ins.excluded.overall_score,
                "scores": ins.excluded.scores,
                "judge_model_version": ins.excluded.judge_model_version,
                "judge_prompt_version": ins.excluded.judge_prompt_version,
                "updated_at": now,
            },
        )
        session.execute(stmt)
        session.commit()
        logger.info("judge_upserted_postgres", unit_id=result.curriculum_unit_id)
    finally:
        session.close()
