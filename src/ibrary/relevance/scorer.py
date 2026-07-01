"""LLM agent: is this textbook chunk relevant for this subtopic? Extract excerpt if yes."""

from __future__ import annotations

from ibrary.config import OPENAI_RELEVANCE_MODEL
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.llm.client import chat_completion_json
from ibrary.prompts.context import format_prompt, resolve_subject
from ibrary.relevance.schemas import ChunkRelevanceResult

MAX_RETRIES = 3
RETRY_BACKOFF = 2
AGENT_VERSION = "relevance-v1"

SYSTEM_PROMPT_TEMPLATE = """\
You are a curriculum designer for **{subject}** at senior secondary school / high school level.
Your task is to decide whether a textbook chunk supports a specific curriculum **subtopic**.
Return JSON only.

Rules:
- ``relevant``: true only if some part of the chunk teaches this subtopic.
- ``excerpt``: when relevant, copy the exact sentences/paragraphs that teach the subtopic \
(not the whole chunk if only part applies). Empty string if not relevant.
- ``confidence``: 1-10 how well the excerpt matches the subtopic.
- ``rationale``: one short sentence.
- Do not invent facts not in the chunk.
"""

USER_TEMPLATE = """\
**Subject:** {subject}
**Subtopic:** {subtopic}
**Topic:** {topic}
**Performance objectives:** {objectives}

**Chunk title:** {chunk_title}
**Embedding similarity score (hint only):** {embedding_score}

**Chunk text:**
{chunk_content}
"""


def score_chunk_relevance(
    unit: CurriculumUnit,
    *,
    chunk_id: str,
    chunk_title: str,
    chunk_content: str,
    embedding_score: float,
    subject: str | None = None,
) -> ChunkRelevanceResult:
    """Score one (unit, chunk) pair."""
    subj = resolve_subject(subject)
    objectives = "\n".join(unit.performance_objectives) or "(none)"
    user = format_prompt(
        USER_TEMPLATE,
        subject=subj,
        subtopic=unit.content_text,
        topic=unit.topic,
        objectives=objectives,
        chunk_title=chunk_title,
        embedding_score=str(embedding_score),
        chunk_content=chunk_content[:12000],
    )
    system = format_prompt(SYSTEM_PROMPT_TEMPLATE, subject=subj)
    raw = chat_completion_json(
        component="relevance",
        model=OPENAI_RELEVANCE_MODEL,
        system=system,
        user=user,
        max_retries=MAX_RETRIES,
        retry_backoff=RETRY_BACKOFF,
        extra_create_kwargs={"temperature": 0.1},
        metadata={
            "curriculum_unit_id": unit.curriculum_unit_id,
            "chunk_id": chunk_id,
            "agent_version": AGENT_VERSION,
        },
    )
    relevant = bool(raw.get("relevant", False))
    excerpt = (raw.get("excerpt") or "").strip() or None
    if not relevant:
        excerpt = None
    return ChunkRelevanceResult(
        chunk_id=chunk_id,
        relevant=relevant,
        excerpt=excerpt,
        embedding_score=embedding_score,
        confidence=raw.get("confidence"),
        rationale=str(raw.get("rationale") or ""),
    )
