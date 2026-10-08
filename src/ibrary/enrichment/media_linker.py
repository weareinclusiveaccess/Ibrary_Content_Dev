"""Resolve image placeholders to textbook assets."""

from __future__ import annotations

import json

import structlog

from ibrary.config import (
    CURATION_MAX_IMAGES,
    MEDIA_TEXTBOOK_MIN_CONFIDENCE,
    OPENAI_ENRICHMENT_MODEL,
    PIPELINE_SUBJECT,
)
from ibrary.enrichment.image_candidates import load_image_candidates
from ibrary.enrichment.schemas import ImagePlaceholder, MediaAsset
from ibrary.llm.client import chat_completion_json

logger = structlog.get_logger(__name__)

SELECT_SYSTEM = """\
You select textbook figures for a student self-study lesson. Return JSON only.
Pick figures that directly support the subtopic. Prefer higher relevance to search hints.
"""

SELECT_USER = """\
**Subject:** {subject}
**Subtopic:** {subtopic}
**Lesson title:** {title}

**Figure requests (placeholders):**
{placeholders_json}

**Available textbook images (candidates):**
{candidates_json}

Return JSON:
{{
  "selections": [
    {{
      "placeholder_id": "ph1",
      "image_id": "bio2e_ch1_sec1_pg29_img0",
      "confidence": 0.85,
      "alt_text": "Screen-reader description for this figure"
    }}
  ]
}}

Rules:
- At most {max_images} selections total.
- Only use image_id values from the candidates list.
- confidence is 0-1; skip if below {min_confidence}.
- alt_text must describe the figure for visually impaired students.
"""


def link_media(
    *,
    curriculum_unit_id: str,
    subtopic: str,
    title: str,
    chunk_ids: list[str],
    curated_content: str,
    placeholders: list[dict] | None = None,
) -> tuple[list[MediaAsset], list[dict]]:
    """Return assets and resolution audit rows."""
    ph_models = [ImagePlaceholder.model_validate(p) for p in (placeholders or [])]
    if not ph_models:
        logger.info("media_linker_no_placeholders", unit_id=curriculum_unit_id)
        return [], []

    candidates = load_image_candidates(chunk_ids)
    if not candidates:
        logger.warning("media_linker_no_candidates", unit_id=curriculum_unit_id)
        return [], [
            {
                "placeholder_id": p.placeholder_id,
                "source": "text_fallback",
                "reason": "no_textbook_images",
            }
            for p in ph_models
        ]

    # Cap candidates sent to LLM
    candidates_trim = candidates[:40]
    raw = chat_completion_json(
        component="media_linker",
        model=OPENAI_ENRICHMENT_MODEL,
        system=SELECT_SYSTEM,
        user=SELECT_USER.format(
            subject=PIPELINE_SUBJECT,
            subtopic=subtopic,
            title=title,
            placeholders_json=json.dumps([p.model_dump() for p in ph_models], indent=2),
            candidates_json=json.dumps(candidates_trim, indent=2)[:12000],
            max_images=CURATION_MAX_IMAGES,
            min_confidence=MEDIA_TEXTBOOK_MIN_CONFIDENCE,
        ),
        metadata={"curriculum_unit_id": curriculum_unit_id},
    )

    by_image_id = {c["image_id"]: c for c in candidates}
    assets: list[MediaAsset] = []
    resolution: list[dict] = []

    for sel in raw.get("selections", [])[:CURATION_MAX_IMAGES]:
        conf = float(sel.get("confidence", 0))
        image_id = sel.get("image_id", "")
        ph_id = sel.get("placeholder_id", "")
        if conf < MEDIA_TEXTBOOK_MIN_CONFIDENCE or image_id not in by_image_id:
            resolution.append(
                {
                    "placeholder_id": ph_id,
                    "source": "text_fallback",
                    "reason": "low_confidence_or_unknown_image",
                }
            )
            continue
        cand = by_image_id[image_id]
        asset_id = f"asset_{len(assets) + 1:03d}"
        assets.append(
            MediaAsset(
                asset_id=asset_id,
                source="textbook",
                image_id=image_id,
                chunk_id=cand.get("chunk_id"),
                s3_url=cand.get("s3_url", ""),
                caption=(cand.get("caption") or "")[:500],
                alt_text=(sel.get("alt_text") or cand.get("alt_text") or caption_snippet(cand)),
                license="CC BY 4.0 OpenStax",
            )
        )
        resolution.append(
            {
                "placeholder_id": ph_id,
                "source": "textbook",
                "image_id": image_id,
                "confidence": conf,
                "asset_id": asset_id,
            }
        )

    logger.info(
        "media_linker_done",
        unit_id=curriculum_unit_id,
        assets=len(assets),
    )
    return assets, resolution


def caption_snippet(cand: dict) -> str:
    cap = (cand.get("caption") or "Textbook figure")[:240]
    return cap
