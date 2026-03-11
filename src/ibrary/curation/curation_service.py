"""UDL content curation service — RAG flow with OpenAI LLM."""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog
from sqlalchemy import text as sa_text

from ibrary.config import MAX_CONTEXT_TOKENS, OPENAI_API_KEY, OPENAI_MODEL
from ibrary.curation.prompts import (
    CURATION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    get_prompt_version,
)
from ibrary.curation.schemas import CuratedModule
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.db import get_session

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2


def _fetch_chunk_content(chunk_ids: list[str]) -> list[dict]:
    """Fetch full chunk content from PostgreSQL by chunk_id."""
    if not chunk_ids:
        return []
    session = get_session()
    try:
        placeholders = ", ".join(f":id{i}" for i in range(len(chunk_ids)))
        params = {f"id{i}": cid for i, cid in enumerate(chunk_ids)}
        rows = session.execute(
            sa_text(
                f"SELECT chunk_id, title, content FROM textbook_chunks "
                f"WHERE chunk_id IN ({placeholders})"
            ),
            params,
        ).fetchall()
        return [{"chunk_id": r.chunk_id, "title": r.title, "content": r.content} for r in rows]
    finally:
        session.close()


def _truncate_context(chunks: list[dict], max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    """Concatenate chunk content, truncating to stay within token budget.

    Rough estimate: 1 token ≈ 4 characters.
    """
    max_chars = max_tokens * 4
    parts: list[str] = []
    total = 0
    for chunk in chunks:
        header = f"### {chunk['title']}\n"
        content = chunk["content"]
        available = max_chars - total - len(header)
        if available <= 0:
            break
        if len(content) > available:
            content = content[:available] + "\n[... truncated]"
        parts.append(header + content)
        total += len(header) + len(content)
    return "\n\n".join(parts)


def _call_llm(system: str, user: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as exc:
            logger.warning("llm_retry", attempt=attempt, error=str(exc))
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF**attempt)
    return {}


def curate_unit(
    unit: CurriculumUnit,
    aligned_chunk_ids: list[str],
) -> CuratedModule | None:
    """Generate UDL-curated content for one curriculum unit via RAG."""
    if not aligned_chunk_ids:
        logger.warning("skipped_no_chunks", unit_id=unit.curriculum_unit_id)
        return None

    chunks = _fetch_chunk_content(aligned_chunk_ids)
    if not chunks:
        logger.warning("skipped_empty_chunks", unit_id=unit.curriculum_unit_id)
        return None

    textbook_context = _truncate_context(chunks)
    objectives = "\n".join(f"- {o}" for o in unit.performance_objectives) or "- (none specified)"

    user_prompt = CURATION_PROMPT_TEMPLATE.format(
        class_name=unit.class_name,
        theme=unit.theme,
        theme_number=unit.theme_number,
        topic_number=unit.topic_number,
        topic=unit.topic,
        subtopic=unit.content_text,
        objectives=objectives,
        textbook_content=textbook_context,
    )

    try:
        result = _call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.error("curation_failed", unit_id=unit.curriculum_unit_id, error=str(exc))
        return None

    return CuratedModule(
        curriculum_unit_id=unit.curriculum_unit_id,
        subject="Biology",
        **{"class": unit.class_name},
        theme=unit.theme,
        theme_number=unit.theme_number,
        topic_number=unit.topic_number,
        subtopic=unit.content_text,
        title=result.get("title", unit.content_text),
        learning_objectives=result.get("learning_objectives", unit.performance_objectives),
        curated_content=result.get("curated_content", ""),
        key_takeaways=result.get("key_takeaways", []),
        glossary_terms=result.get("glossary_terms", {}),
        textbook_chunk_refs=aligned_chunk_ids,
        model_version=OPENAI_MODEL,
        prompt_version=get_prompt_version(),
    )


def curate_all(
    units: list[CurriculumUnit],
    alignment: dict[str, list[dict]],
    *,
    resume_from: set[str] | None = None,
) -> list[CuratedModule]:
    """Run curation for all units.  Supports --resume by skipping already-curated."""
    modules: list[CuratedModule] = []
    for unit in units:
        if resume_from and unit.curriculum_unit_id in resume_from:
            continue

        matches = alignment.get(unit.curriculum_unit_id, [])
        if not matches:
            logger.warning("no_alignment_skip", unit_id=unit.curriculum_unit_id)
            continue

        chunk_ids = [m["chunk_id"] for m in matches if not m.get("needs_review")]
        if not chunk_ids:
            chunk_ids = [m["chunk_id"] for m in matches]

        module = curate_unit(unit, chunk_ids)
        if module:
            modules.append(module)
    return modules


def save_curated(modules: list[CuratedModule], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "curated_content.json"
    data = [m.model_dump(by_alias=True) for m in modules]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("curated_saved", count=len(modules), path=str(path))
    return path
