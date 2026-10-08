"""Build curation context from relevance excerpts."""

from __future__ import annotations

from ibrary.relevance.store import load_relevance_for_unit


def build_curation_excerpts(unit_id: str) -> list[dict]:
    """Chunks for curation: excerpt text only where relevant=true."""
    rows = load_relevance_for_unit(unit_id)
    out: list[dict] = []
    for r in rows:
        if not r.excerpt:
            continue
        out.append({
            "chunk_id": r.chunk_id,
            "title": r.chunk_id,
            "content": r.excerpt,
            "alignment_score": r.embedding_score,
        })
    return out
