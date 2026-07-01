"""Decide whether optional enrichment agents run for a curated unit."""

from __future__ import annotations

import os
import re

import structlog

from ibrary.config import (
    ENRICHMENT_AUTO_FORMULAS,
    ENRICHMENT_AUTO_IMAGES,
    ENRICHMENT_ENABLE_FORMULAS,
    ENRICHMENT_ENABLE_IMAGES,
)
from ibrary.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)

_CHEM_TOKEN = re.compile(
    r"\b(CO2|CO₂|H2O|H₂O|O2|O₂|NH3|CH4|ATP|DNA|RNA|C6H12O6)\b",
    re.IGNORECASE,
)


def _placeholders(ctx: PipelineContext, key: str) -> list[dict]:
    on_ctx = getattr(ctx, key, None) or []
    mod = ctx.curated_module
    on_mod = getattr(mod, key, None) if mod else None
    combined = list(on_ctx) + list(on_mod or [])
    return [p for p in combined if isinstance(p, dict)]


def should_run_media_linker(ctx: PipelineContext) -> bool:
    """Images are optional — run only when TextCurator requested figures."""
    if not ENRICHMENT_ENABLE_IMAGES:
        return False
    if ctx.curriculum_only:
        return False
    mod = ctx.curated_module
    if mod is not None and not mod.textbook_grounded:
        return False
    if _placeholders(ctx, "image_placeholders"):
        return True
    if ENRICHMENT_AUTO_IMAGES and ctx.curated_module:
        content = (ctx.curated_module.curated_content or "").lower()
        if any(w in content for w in ("figure", "diagram", "illustration", "image")):
            chunk_ids = ctx.curated_module.textbook_chunk_refs or [
                c.get("chunk_id") for c in ctx.excerpt_chunks if c.get("chunk_id")
            ]
            if chunk_ids:
                logger.info(
                    "enrichment_plan_auto_images",
                    unit_id=ctx.curriculum_unit_id,
                    reason="content_mentions_visual",
                )
                return True
    return False


def should_run_formula_agent(ctx: PipelineContext) -> bool:
    """Formulas are optional — run when placeholders exist or auto-detect is on."""
    if not ENRICHMENT_ENABLE_FORMULAS:
        return False
    if _placeholders(ctx, "formula_placeholders"):
        return True
    if ENRICHMENT_AUTO_FORMULAS and ctx.curated_module:
        content = ctx.curated_module.curated_content or ""
        if _CHEM_TOKEN.search(content):
            logger.info(
                "enrichment_plan_auto_formulas",
                unit_id=ctx.curriculum_unit_id,
                reason="chemistry_tokens_in_content",
            )
            return True
    return False


def enrichment_agents_for(ctx: PipelineContext) -> list[str]:
    """Ordered agent names for the optional enrichment stage (may be empty)."""
    from ibrary.pipeline.subagents import FormulaAgent, MediaLinkerAgent

    agents: list[str] = []
    if should_run_media_linker(ctx):
        agents.append(MediaLinkerAgent.name)
    if should_run_formula_agent(ctx):
        agents.append(FormulaAgent.name)
    logger.info(
        "enrichment_plan",
        unit_id=ctx.curriculum_unit_id,
        agents=agents or ["none"],
    )
    return agents
