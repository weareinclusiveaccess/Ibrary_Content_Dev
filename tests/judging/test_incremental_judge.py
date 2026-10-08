"""Incremental judge persistence."""

import json
from unittest.mock import patch

from ibrary.curation.schemas import CuratedModule
from ibrary.judging.schemas import SubtopicJudgeResult
from ibrary.judging.subtopic_judge import (
    append_evaluation_result,
    evaluate_all_curated,
    load_evaluation_unit_ids,
)


def _result(unit_id: str, score: float = 8.0) -> SubtopicJudgeResult:
    return SubtopicJudgeResult(
        curriculum_unit_id=unit_id,
        overall_score=score,
        passed=score >= 7.0,
        judge_prompt_version="v1.0-udl-v3:test",
        judge_model_version="gpt-4o-mini",
    )


def test_append_evaluation_result_merges_json(tmp_path, monkeypatch):
    monkeypatch.setattr("ibrary.judging.judge_postgres.upsert_judge_result", lambda r: None)
    path = tmp_path / "udl_subtopic_evaluation.json"
    append_evaluation_result(_result("unit_a"), tmp_path)
    append_evaluation_result(_result("unit_b", 5.0), tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [r["curriculum_unit_id"] for r in data] == ["unit_a", "unit_b"]
    assert data[1]["passed"] is False


def test_load_evaluation_unit_ids(tmp_path, monkeypatch):
    monkeypatch.setattr("ibrary.judging.judge_postgres.upsert_judge_result", lambda r: None)
    append_evaluation_result(_result("unit_a"), tmp_path)
    assert load_evaluation_unit_ids(tmp_path / "udl_subtopic_evaluation.json") == {"unit_a"}


def test_evaluate_all_curated_streams_modules(tmp_path, monkeypatch):
    monkeypatch.setattr("ibrary.judging.judge_postgres.upsert_judge_result", lambda r: None)
    modules = [
        CuratedModule(
            curriculum_unit_id="u1",
            class_name="SSS 1",
            theme="T",
            theme_number=1,
            topic_number=1,
            subtopic="S",
            title="T",
            curated_content="lesson one",
        ),
        CuratedModule(
            curriculum_unit_id="u2",
            class_name="SSS 1",
            theme="T",
            theme_number=1,
            topic_number=1,
            subtopic="S",
            title="T",
            curated_content="lesson two",
        ),
    ]

    def fake_iter(_output_dir, **kwargs):
        yield from modules

    def fake_eval(module, *, threshold=7.0):
        return _result(module.curriculum_unit_id, 8.0)

    monkeypatch.setattr(
        "ibrary.judging.subtopic_judge.iter_modules_for_judge",
        fake_iter,
    )
    monkeypatch.setattr(
        "ibrary.judging.subtopic_judge.evaluate_subtopic",
        fake_eval,
    )
    judged, flagged = evaluate_all_curated(tmp_path)
    assert judged == 2
    assert flagged == 0
    data = json.loads((tmp_path / "udl_subtopic_evaluation.json").read_text(encoding="utf-8"))
    assert len(data) == 2
