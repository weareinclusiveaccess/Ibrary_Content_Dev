"""Enrichment-only schemas (no import from curation)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MediaAsset(BaseModel):
    asset_id: str
    source: str = "textbook"
    image_id: str
    chunk_id: str | None = None
    s3_url: str
    caption: str = ""
    alt_text: str = ""
    license: str = "CC BY 4.0 OpenStax"
    attribution_url: str | None = None


class ImagePlaceholder(BaseModel):
    placeholder_id: str
    intent: str
    search_hints: list[str] = Field(default_factory=list)
    after_heading: str | None = None
