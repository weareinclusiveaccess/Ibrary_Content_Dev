"""Native content pipeline orchestrator (subject-agnostic DAG).

Explicit step runner for: text curation → optional media/formula → assemble.
Media and formula agents run only when ``enrichment_plan`` says they are needed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

import structlog

from ibrary.pipeline.agents.base import AgentSkipped, PipelineSubAgent
from ibrary.pipeline.context import PipelineContext
from ibrary.pipeline.enrichment_plan import enrichment_agents_for
from ibrary.pipeline.subagents import (
    DEFAULT_SUBAGENTS,
    ModuleAssemblerAgent,
    RelevanceAgent,
    TextCuratorAgent,
    get_subagent,
)

logger = structlog.get_logger(__name__)


class PipelineOrchestrator:
    """Runs pipeline sub-agents for one or more curriculum units (any subject)."""

    def __init__(
        self,
        *,
        agents: dict[str, PipelineSubAgent] | None = None,
        parallel_media_formula: bool = True,
    ) -> None:
        self._agents = agents or dict(DEFAULT_SUBAGENTS)
        self._parallel_media_formula = parallel_media_formula

    def run_agent(self, name: str, ctx: PipelineContext) -> PipelineContext:
        agent = self._agents.get(name) or get_subagent(name, self._agents)
        logger.info("subagent_start", agent=name, unit_id=ctx.curriculum_unit_id)
        try:
            out = agent.run(ctx)
        except AgentSkipped as exc:
            logger.info("subagent_skipped", agent=name, reason=str(exc))
            out = ctx
        logger.info("subagent_done", agent=name, unit_id=ctx.curriculum_unit_id)
        return out

    def run_sequence(self, names: Sequence[str], ctx: PipelineContext) -> PipelineContext:
        for name in names:
            ctx = self.run_agent(name, ctx)
        return ctx

    def run_parallel(self, names: Sequence[str], ctx: PipelineContext) -> PipelineContext:
        if len(names) <= 1:
            return self.run_sequence(names, ctx)

        branches: dict[str, PipelineContext] = {}
        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            futures = {
                pool.submit(self.run_agent, name, _branch_context(ctx, name)): name
                for name in names
            }
            for fut in as_completed(futures):
                name = futures[fut]
                branches[name] = fut.result()

        return _merge_parallel_contexts(ctx, branches)

    def curate_unit(self, ctx: PipelineContext) -> PipelineContext:
        ctx = self.run_agent(TextCuratorAgent.name, ctx)

        enrich = enrichment_agents_for(ctx)
        if enrich:
            if len(enrich) == 1 or not self._parallel_media_formula:
                ctx = self.run_sequence(enrich, ctx)
            else:
                ctx = self.run_parallel(enrich, ctx)
        else:
            logger.info(
                "enrichment_stage_skipped",
                unit_id=ctx.curriculum_unit_id,
                reason="no_image_or_formula_placeholders",
            )

        ctx = self.run_agent(ModuleAssemblerAgent.name, ctx)
        return ctx

    def filter_relevance_unit(
        self,
        ctx: PipelineContext,
        *,
        alignment_matches: list[dict],
    ) -> PipelineContext:
        ctx.alignment_matches = alignment_matches
        return self.run_agent(RelevanceAgent.name, ctx)


def _branch_context(base: PipelineContext, branch: str) -> PipelineContext:
    return PipelineContext(
        curriculum_unit_id=base.curriculum_unit_id,
        unit=base.unit,
        alignment_matches=list(base.alignment_matches),
        relevance_results=list(base.relevance_results),
        excerpt_chunks=list(base.excerpt_chunks),
        curated_module=base.curated_module,
        content_blocks=list(base.content_blocks),
        image_placeholders=list(base.image_placeholders),
        formula_placeholders=list(base.formula_placeholders),
        assets=[],
        formulas=[],
        metadata={**base.metadata, "parallel_branch": branch},
    )


def _merge_parallel_contexts(
    base: PipelineContext,
    branches: dict[str, PipelineContext],
) -> PipelineContext:
    for branch_ctx in branches.values():
        base.assets.extend(branch_ctx.assets)
        base.formulas.extend(branch_ctx.formulas)
        base.media_resolution.extend(branch_ctx.media_resolution)
        base.formula_resolution.extend(branch_ctx.formula_resolution)
        base.errors.extend(branch_ctx.errors)
    return base


def create_orchestrator(**kwargs) -> PipelineOrchestrator:
    """Create the native Python DAG orchestrator."""
    return PipelineOrchestrator(**kwargs)
