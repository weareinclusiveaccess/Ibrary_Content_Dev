"""Curriculum-only curation when no relevant textbook excerpts."""

from unittest.mock import patch

import pytest

from ibrary.curation.curation_service import (
    STATUS_CURRICULUM_ONLY,
    curate_unit,
    resolve_curation_excerpts,
)
from ibrary.curation.schemas import CuratedModule, module_for_json_export
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


def test_resolve_curriculum_only_when_no_excerpts(monkeypatch):
    monkeypatch.setattr(
        "ibrary.curation.curation_service.CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS",
        True,
    )
    with patch(
        "ibrary.relevance.context.build_curation_excerpts",
        return_value=[],
    ):
        resolved = resolve_curation_excerpts("bio_sss1_theme1_topic1_content0")
    assert resolved == ([], True)


def test_resolve_skips_when_fallback_disabled(monkeypatch):
    monkeypatch.setattr(
        "ibrary.curation.curation_service.CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS",
        False,
    )
    with patch(
        "ibrary.relevance.context.build_curation_excerpts",
        return_value=[],
    ):
        assert resolve_curation_excerpts("bio_sss1_theme1_topic1_content0") is None


@patch("ibrary.curation.curation_service._call_llm")
def test_curate_unit_curriculum_only_flags(mock_llm):
    mock_llm.return_value = {
        "title": "Lesson",
        "curated_content": "## Intro\n\nBody.",
        "accessibility_checklist": ["Headings used"],
    }
    unit = _sample_unit()
    module = curate_unit(
        unit,
        [],
        alignment_matches=[{"chunk_id": "c1", "score": 0.9}],
        curriculum_only=True,
    )
    assert module is not None
    assert module.textbook_grounded is False
    assert module.status == STATUS_CURRICULUM_ONLY
    assert module.textbook_chunk_refs == []
    assert "curriculum-only" in module.accessibility_checklist[0].lower()
    mock_llm.assert_called_once()


def test_export_includes_curriculum_only_flags():
    m = CuratedModule(
        curriculum_unit_id="x",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Sub",
        title="Title",
        curated_content="text",
        textbook_grounded=False,
        status=STATUS_CURRICULUM_ONLY,
    )
    d = module_for_json_export(m)
    assert d["textbook_grounded"] is False
    assert d["status"] == STATUS_CURRICULUM_ONLY


def test_orchestrator_curriculum_only_calls_curate_unit():
    ctx = PipelineContext(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        unit=_sample_unit(),
        alignment_matches=[{"chunk_id": "c1", "score": 0.5}],
        excerpt_chunks=[],
        curriculum_only=True,
    )
    module = CuratedModule(
        curriculum_unit_id=ctx.curriculum_unit_id,
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Subtopic",
        title="Title",
        curated_content="# Lesson",
        textbook_grounded=False,
        status=STATUS_CURRICULUM_ONLY,
    )
    with patch("ibrary.curation.curation_service.curate_unit", return_value=module) as mock:
        out = create_orchestrator().curate_unit(ctx)
    mock.assert_called_once()
    assert mock.call_args.kwargs.get("curriculum_only") is True
    assert out.curated_module is not None
    assert out.curated_module.textbook_grounded is False
