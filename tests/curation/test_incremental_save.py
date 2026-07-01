"""Incremental curated_content.json persistence."""

import json
from pathlib import Path

from ibrary.curation.curation_service import (
    append_curated_module,
    curate_all,
    load_curated_json_array,
    load_curated_unit_ids,
)
from ibrary.curation.schemas import CuratedModule
from ibrary.curriculum.schemas import CurriculumUnit


def _module(unit_id: str, body: str) -> CuratedModule:
    return CuratedModule(
        curriculum_unit_id=unit_id,
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Sub",
        title=f"Title {unit_id}",
        curated_content=body,
    )


def test_append_curated_module_writes_incrementally(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ibrary.curation.curation_service.upsert_curated_payloads",
        lambda payloads: len(payloads),
    )
    path = tmp_path / "curated_content.json"
    append_curated_module(_module("unit_a", "content a"), tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))[0]["curriculum_unit_id"] == "unit_a"

    append_curated_module(_module("unit_b", "content b"), tmp_path)
    data = load_curated_json_array(path)
    assert [m["curriculum_unit_id"] for m in data] == ["unit_a", "unit_b"]


def test_load_curated_unit_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ibrary.curation.curation_service.upsert_curated_payloads",
        lambda payloads: len(payloads),
    )
    append_curated_module(_module("unit_a", "a"), tmp_path)
    assert load_curated_unit_ids(tmp_path / "curated_content.json") == {"unit_a"}


def test_curate_all_persists_per_unit_without_batch_list(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ibrary.curation.curation_service.upsert_curated_payloads",
        lambda payloads: len(payloads),
    )
    units = [
        CurriculumUnit(
            curriculum_unit_id="u1",
            class_name="SSS 1",
            theme="T",
            theme_number=1,
            topic_number=1,
            topic="Topic",
            content_index=0,
            content_text="S1",
            performance_objectives=[],
            student_activities=[],
            teachers_activities=[],
        ),
        CurriculumUnit(
            curriculum_unit_id="u2",
            class_name="SSS 1",
            theme="T",
            theme_number=1,
            topic_number=1,
            topic="Topic",
            content_index=1,
            content_text="S2",
            performance_objectives=[],
            student_activities=[],
            teachers_activities=[],
        ),
    ]

    def fake_curate(unit, alignment):
        return _module(unit.curriculum_unit_id, f"body {unit.curriculum_unit_id}")

    monkeypatch.setattr(
        "ibrary.curation.curation_service._curate_one_unit",
        fake_curate,
    )
    saved = curate_all(units, {}, output_dir=tmp_path, merge_existing=True)
    assert saved == 2
    data = load_curated_json_array(tmp_path / "curated_content.json")
    assert len(data) == 2
