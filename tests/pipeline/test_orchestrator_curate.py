"""Orchestrator curate DAG wiring tests."""

from unittest.mock import patch

from ibrary.curation.schemas import CuratedModule
from ibrary.curriculum.schemas import CurriculumUnit
from ibrary.pipeline.context import PipelineContext
from ibrary.pipeline.orchestrator import create_orchestrator


def _sample_unit() -> CurriculumUnit:
    return CurriculumUnit(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        topic="Topic",
        content_index=0,
        content_text="Subtopic",
        performance_objectives=["obj"],
        student_activities=[],
        teachers_activities=[],
    )


def test_orchestrator_curate_sets_curated_module():
    module = CuratedModule(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Subtopic",
        title="Title",
        curated_content="# Lesson\n\n## Review questions\n\nOne?",
    )
    ctx = PipelineContext(
        curriculum_unit_id=module.curriculum_unit_id,
        unit=_sample_unit(),
        alignment_matches=[{"chunk_id": "bio2e_ch1_sec1", "score": 0.5}],
        excerpt_chunks=[{"chunk_id": "bio2e_ch1_sec1", "title": "t", "content": "excerpt"}],
    )
    with patch("ibrary.curation.curation_service.curate_unit", return_value=module):
        out = create_orchestrator().curate_unit(ctx)
    assert out.curated_module is not None
    assert out.curated_module.curriculum_unit_id == module.curriculum_unit_id
