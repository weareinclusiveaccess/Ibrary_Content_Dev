"""Tests for optional enrichment agent scheduling."""

from ibrary.curation.schemas import CuratedModule
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.pipeline.context import PipelineContext
from ibrary.pipeline.enrichment_plan import (
    enrichment_agents_for,
    should_run_formula_agent,
    should_run_media_linker,
)


def _unit() -> CurriculumUnit:
    return CurriculumUnit(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        topic="Topic",
        content_index=0,
        content_text="Subtopic",
        performance_objectives=[],
        student_activities=[],
        teachers_activities=[],
    )


def _module(**kwargs) -> CuratedModule:
    base = dict(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Subtopic",
        title="Title",
        curated_content="Plain prose only.",
    )
    base.update(kwargs)
    return CuratedModule(**base)


def test_skips_both_when_empty_placeholders():
    ctx = PipelineContext(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        curated_module=_module(
            image_placeholders=[],
            formula_placeholders=[],
        ),
    )
    assert should_run_media_linker(ctx) is False
    assert should_run_formula_agent(ctx) is False
    assert enrichment_agents_for(ctx) == []


def test_runs_media_when_image_placeholders():
    ctx = PipelineContext(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        curated_module=_module(),
        image_placeholders=[
            {"placeholder_id": "ph1", "intent": "cell diagram", "search_hints": ["cell"]}
        ],
    )
    assert should_run_media_linker(ctx) is True
    agents = enrichment_agents_for(ctx)
    assert "media_linker" in agents


def test_runs_formula_when_formula_placeholders():
    ctx = PipelineContext(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        curated_module=_module(),
        formula_placeholders=[
            {"placeholder_id": "fp1", "plain_text": "CO2", "kind": "chemistry"}
        ],
    )
    assert should_run_formula_agent(ctx) is True
    agents = enrichment_agents_for(ctx)
    assert "formula" in agents
