"""Pipeline sub-agents — subject-agnostic; register per subject in orchestrator if needed."""

from __future__ import annotations

import os

import structlog

from ibrary.config import PIPELINE_VERSION
from ibrary.pipeline.agents.base import AgentSkipped, PipelineSubAgent
from ibrary.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)


class RelevanceAgent:
    """Top-k alignment matches → per-chunk relevance + excerpt."""

    name = "relevance"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.alignment_matches:
            ctx.add_error("relevance: no alignment_matches on context")
            return ctx
        logger.info("relevance_agent_stub", unit_id=ctx.curriculum_unit_id)
        ctx.metadata["relevance_status"] = "stub"
        return ctx


class TextCuratorAgent:
    """Excerpts → CuratedModule via curation_service."""

    name = "text_curator"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.unit:
            ctx.add_error("text_curator: missing unit on context")
            return ctx

        pipeline_v = int(os.getenv("PIPELINE_VERSION", str(PIPELINE_VERSION)))
        if pipeline_v >= 2 and not ctx.excerpt_chunks and not ctx.curriculum_only:
            raise AgentSkipped("text_curator: no excerpt_chunks (run filter_relevance)")

        from ibrary.curation.curation_service import curate_unit

        if ctx.curriculum_only:
            module = curate_unit(
                ctx.unit,
                [],
                alignment_matches=ctx.alignment_matches,
                curriculum_only=True,
            )
        elif ctx.excerpt_chunks:
            chunk_ids = [c["chunk_id"] for c in ctx.excerpt_chunks]
            module = curate_unit(
                ctx.unit,
                chunk_ids,
                alignment_matches=ctx.alignment_matches,
                excerpt_chunks=ctx.excerpt_chunks,
            )
        else:
            chunk_ids = [
                m["chunk_id"]
                for m in ctx.alignment_matches
                if not m.get("needs_review")
            ]
            if not chunk_ids:
                chunk_ids = [m["chunk_id"] for m in ctx.alignment_matches]
            module = curate_unit(
                ctx.unit,
                chunk_ids,
                alignment_matches=ctx.alignment_matches,
            )

        if module is None:
            ctx.add_error("text_curator: curate_unit returned None")
            return ctx

        ctx.curated_module = module
        ctx.image_placeholders = list(module.image_placeholders)
        ctx.formula_placeholders = list(module.formula_placeholders)
        ctx.metadata["text_curator_status"] = "ok"
        return ctx


class MediaLinkerAgent:
    """Image placeholders → textbook assets (optional)."""

    name = "media_linker"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.curated_module is None:
            raise AgentSkipped("media_linker: no curated_module")

        placeholders = ctx.image_placeholders or ctx.curated_module.image_placeholders
        if not placeholders:
            raise AgentSkipped("media_linker: no image_placeholders")

        from ibrary.enrichment.media_linker import link_media

        mod = ctx.curated_module
        chunk_ids = mod.textbook_chunk_refs or [c["chunk_id"] for c in ctx.excerpt_chunks]

        assets, resolution = link_media(
            curriculum_unit_id=mod.curriculum_unit_id,
            subtopic=mod.subtopic,
            title=mod.title,
            chunk_ids=chunk_ids,
            curated_content=mod.curated_content,
            placeholders=placeholders,
        )
        ctx.assets = [a.model_dump() for a in assets]
        ctx.media_resolution = resolution
        ctx.metadata["media_linker_status"] = "ok" if assets else "no_assets"
        return ctx


class FormulaAgent:
    """Extract LaTeX / chemistry formulas from lesson text (optional)."""

    name = "formula"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.curated_module is None:
            raise AgentSkipped("formula: no curated_module")

        placeholders = ctx.formula_placeholders or ctx.curated_module.formula_placeholders
        if not placeholders:
            from ibrary.config import ENRICHMENT_AUTO_FORMULAS

            if not ENRICHMENT_AUTO_FORMULAS:
                raise AgentSkipped("formula: no formula_placeholders")

        from ibrary.config import ENRICHMENT_AUTO_FORMULAS
        from ibrary.enrichment.formula_resolver import resolve_formulas

        mod = ctx.curated_module
        formulas, resolution = resolve_formulas(
            curriculum_unit_id=mod.curriculum_unit_id,
            subtopic=mod.subtopic,
            curated_content=mod.curated_content,
            placeholders=placeholders,
            allow_heuristic=bool(ENRICHMENT_AUTO_FORMULAS and not placeholders),
        )
        ctx.formulas = [f.model_dump() for f in formulas]
        ctx.formula_resolution = resolution
        ctx.metadata["formula_agent_status"] = "ok" if formulas else "no_formulas"
        return ctx


class ModuleAssemblerAgent:
    """Apply images/formulas to curated module (no content_blocks in export)."""

    name = "module_assembler"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.curated_module is None:
            ctx.add_error("module_assembler: no curated_module")
            return ctx

        from ibrary.curation.schemas import FormulaRef
        from ibrary.enrichment.module_assembler import finalize_curated_module
        from ibrary.enrichment.schemas import MediaAsset

        assets = [MediaAsset.model_validate(a) for a in ctx.assets]
        formulas = [FormulaRef.model_validate(f) for f in ctx.formulas]

        ctx.curated_module = finalize_curated_module(
            ctx.curated_module,
            assets=assets,
            formulas=formulas,
        )
        ctx.metadata["assembler_status"] = "ok"
        return ctx


DEFAULT_SUBAGENTS: dict[str, PipelineSubAgent] = {
    RelevanceAgent.name: RelevanceAgent(),
    TextCuratorAgent.name: TextCuratorAgent(),
    MediaLinkerAgent.name: MediaLinkerAgent(),
    FormulaAgent.name: FormulaAgent(),
    ModuleAssemblerAgent.name: ModuleAssemblerAgent(),
}


def get_subagent(name: str, registry: dict[str, PipelineSubAgent] | None = None) -> PipelineSubAgent:
    reg = registry or DEFAULT_SUBAGENTS
    try:
        return reg[name]
    except KeyError as exc:
        raise KeyError(f"Unknown pipeline sub-agent: {name!r}. Known: {list(reg)}") from exc
