"""Backward-compatible imports. Prefer :mod:`ibrary.textbook.openstax_biology2e`."""

from ibrary.textbook.openstax_biology2e import (
    ExtractedImage,
    TextbookChunkRecord,
    extract_openstax_biology_2e,
    write_textbook_image_manifest,
)

extract_biology2e = extract_openstax_biology_2e

__all__ = [
    "ExtractedImage",
    "TextbookChunkRecord",
    "extract_biology2e",
    "extract_openstax_biology_2e",
    "write_textbook_image_manifest",
]
