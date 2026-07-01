"""Build symmetric embedding strings for textbook chunks and curriculum units."""

from __future__ import annotations

from ibrary.config import EMBEDDING_BODY_MAX_CHARS, OPENAI_EMBEDDING_MODEL
from ibrary.curriculum.schemas import CurriculumUnit


def resolve_embedding_storage_version() -> str:
    """DB ``model_version`` key; suffix when body text is included in chunk vectors."""
    if EMBEDDING_BODY_MAX_CHARS > 0:
        return f"{OPENAI_EMBEDDING_MODEL}:body{EMBEDDING_BODY_MAX_CHARS}"
    return OPENAI_EMBEDDING_MODEL


def build_chunk_embedding_text(
    *,
    title: str,
    learning_objectives: str = "",
    summary: str = "",
    content: str = "",
) -> str:
    """Text embedded for each textbook chunk (metadata + optional body snippet)."""
    parts: list[str] = []
    if title and title.strip():
        parts.append(title.strip())
    if learning_objectives and learning_objectives.strip():
        parts.append(learning_objectives.strip())
    if summary and summary.strip():
        parts.append(summary.strip())
    if EMBEDDING_BODY_MAX_CHARS > 0 and content and content.strip():
        snippet = content.strip()[:EMBEDDING_BODY_MAX_CHARS]
        if snippet:
            parts.append("---")
            parts.append(snippet)
    return "\n".join(parts) if parts else title or content[:500] or ""


def build_unit_query_text(unit: CurriculumUnit) -> str:
    """Text embedded for each curriculum unit (symmetric structure to chunk text)."""
    parts: list[str] = []
    if unit.theme:
        parts.append(f"Theme: {unit.theme}")
    parts.append(f"Topic: {unit.topic}")
    parts.append(f"Subtopic: {unit.content_text}")
    if unit.performance_objectives:
        parts.append("Performance objectives:")
        parts.extend(f"- {o}" for o in unit.performance_objectives if str(o).strip())
    return "\n".join(parts)
