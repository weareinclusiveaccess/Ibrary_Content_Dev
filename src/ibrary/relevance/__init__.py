"""Filter textbook chunks by subtopic relevance after pgvector alignment."""

from ibrary.relevance.context import build_curation_excerpts
from ibrary.relevance.filter_runner import filter_relevance_for_units
from ibrary.relevance.schemas import ChunkRelevanceResult, UnitRelevanceReport
from ibrary.relevance.store import load_relevance_for_unit, save_relevance_json

__all__ = [
    "ChunkRelevanceResult",
    "UnitRelevanceReport",
    "build_curation_excerpts",
    "filter_relevance_for_units",
    "load_relevance_for_unit",
    "save_relevance_json",
]
