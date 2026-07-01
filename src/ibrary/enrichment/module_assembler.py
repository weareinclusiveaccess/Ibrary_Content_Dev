"""Finalize curated modules after optional media/formula enrichment."""

from __future__ import annotations

import structlog

from ibrary.curation.schemas import CuratedModule, FormulaRef, ImageRef
from ibrary.enrichment.blocks import apply_latex_to_markdown
from ibrary.enrichment.schemas import MediaAsset

logger = structlog.get_logger(__name__)


def finalize_curated_module(
    module: CuratedModule,
    *,
    assets: list[MediaAsset],
    formulas: list[FormulaRef],
) -> CuratedModule:
    """Apply enrichment to the module; only set fields that have data.

    Does not build ``content_blocks`` (deferred until the app renderer needs it).
    """
    md = module.curated_content
    if formulas:
        md = apply_latex_to_markdown(md, formulas)

    updates: dict = {"curated_content": md}
    if assets:
        updates["images"] = [
            ImageRef(
                image_id=a.image_id,
                s3_url=a.s3_url,
                caption=a.caption,
                alt_text=a.alt_text,
            )
            for a in assets
        ]
    if formulas:
        updates["formulas"] = formulas

    out = module.model_copy(update=updates)
    logger.info(
        "module_finalized",
        unit_id=module.curriculum_unit_id,
        images=len(assets),
        formulas=len(formulas),
    )
    return out
