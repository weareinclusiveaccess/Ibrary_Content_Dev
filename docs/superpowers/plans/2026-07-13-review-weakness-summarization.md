# Review Weakness Summarization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, resumable workflow that reads substantive human and UDL judge reviews from Neon, summarizes evidenced weaknesses per curated content unit with OpenAI, and writes a cross-content prompt-improvement rollup to JSON.

**Architecture:** A prompt module defines versioned structured-output instructions. A review weakness module handles SQLAlchemy loading, evidence selection and normalization, source hashing, validated OpenAI calls, atomic JSON persistence, and two-stage orchestration. A standalone script exposes filters and refresh controls without adding model calls to the reviewer portal.

**Tech Stack:** Python 3.11+, SQLAlchemy, Pydantic, OpenAI JSON completions, pytest, JSON files.

---

## File Structure

- Create `src/ibrary/prompt_improvement/review_weakness_prompts.py`: versioned per-content and rollup prompt builders.
- Create `src/ibrary/prompt_improvement/review_weaknesses.py`: schemas, review loading and normalization, hashing, model calls, artifact persistence, and orchestration.
- Create `scripts/summarize_review_weaknesses.py`: command-line entry point.
- Create `tests/prompt_improvement/test_review_weakness_prompts.py`: prompt contract and version tests.
- Create `tests/prompt_improvement/test_review_weaknesses.py`: selection, normalization, hashing, persistence, model validation, and orchestration tests.
- Create `tests/prompt_improvement/test_summarize_review_weaknesses_cli.py`: CLI argument wiring test.
- Modify `src/ibrary/config.py`: add the dedicated summarizer model setting.
- Modify `src/ibrary/prompt_improvement/__init__.py`: export the public orchestration API.
- Modify `.env.example`: document the optional model override.
- Modify `docs/PIPELINE_ORCHESTRATOR.md`: document how and when to run review weakness analysis.

### Task 1: Add Versioned Prompt Contracts

**Files:**
- Create: `tests/prompt_improvement/test_review_weakness_prompts.py`
- Create: `src/ibrary/prompt_improvement/review_weakness_prompts.py`

- [ ] **Step 1: Write the failing prompt contract tests**

```python
from ibrary.prompt_improvement.review_weakness_prompts import (
    build_content_summary_user_prompt,
    build_rollup_user_prompt,
    get_review_weakness_prompt_version,
)


def test_prompt_version_contains_tag_and_hash():
    version = get_review_weakness_prompt_version()
    tag, digest = version.split(":")
    assert tag == "review_weakness_v1"
    assert len(digest) == 8


def test_content_prompt_serializes_only_supplied_payload():
    prompt = build_content_summary_user_prompt(
        {
            "curriculum_unit_id": "bio_sss1_theme1_topic1_content0",
            "title": "Cells",
            "evidence": [{"source_id": "human:7", "notes": "Needs a clearer example."}],
        }
    )
    assert "bio_sss1_theme1_topic1_content0" in prompt
    assert "human:7" in prompt
    assert "reviewer@example.com" not in prompt


def test_rollup_prompt_contains_successful_summaries_and_failed_ids():
    prompt = build_rollup_user_prompt(
        [{"curriculum_unit_id": "unit-1", "weaknesses": []}],
        ["unit-2"],
    )
    assert "unit-1" in prompt
    assert "unit-2" in prompt
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/prompt_improvement/test_review_weakness_prompts.py -v`

Expected: collection fails with `ModuleNotFoundError: ibrary.prompt_improvement.review_weakness_prompts`.

- [ ] **Step 3: Implement the prompt module**

```python
"""Versioned prompts for extracting weaknesses from content reviews."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PROMPT_VERSION_TAG = "review_weakness_v1"

CONTENT_SUMMARY_SYSTEM_PROMPT = """
You analyze reviewer feedback about one curated learning content unit.
Report only weaknesses supported by the supplied evidence. Merge duplicate
observations, cite one or more source_id values for every weakness, and never
invent reviewer intent. Return one JSON object with a `weaknesses` array.
Each weakness must contain: category, summary, severity, occurrence_count,
evidence_source_ids, and prompt_instruction_suggestion. Category must be one of
correctness, clarity, pedagogy, udl_accessibility, engagement, structure, or
other. Severity must be low, medium, or high. If there is no evidenced weakness,
return an empty array.
""".strip()

ROLLUP_SYSTEM_PROMPT = """
You consolidate validated per-content weakness summaries for curation prompt
improvement. Return one JSON object with a `recurring_weaknesses` array and an
`instruction_themes` array. Every recurring weakness must contain: theme,
priority, affected_unit_ids, occurrence_count, evidence_source_ids, and
recommended_instruction. Priority must be low, medium, or high. Use only the
supplied summaries and preserve source IDs. Also return `excluded_failed_units`
exactly as supplied.
""".strip()


def get_review_weakness_prompt_version() -> str:
    content = Path(__file__).read_bytes()
    digest = hashlib.sha256(content).hexdigest()[:8]
    return f"{PROMPT_VERSION_TAG}:{digest}"


def build_content_summary_user_prompt(payload: dict[str, Any]) -> str:
    return "Analyze this content review evidence:\n" + json.dumps(
        payload, ensure_ascii=False, sort_keys=True
    )


def build_rollup_user_prompt(
    summaries: list[dict[str, Any]],
    failed_unit_ids: list[str],
) -> str:
    payload = {
        "per_content_summaries": summaries,
        "excluded_failed_units": sorted(failed_unit_ids),
    }
    return "Consolidate these weakness summaries:\n" + json.dumps(
        payload, ensure_ascii=False, sort_keys=True
    )
```

- [ ] **Step 4: Run the prompt tests**

Run: `uv run pytest tests/prompt_improvement/test_review_weakness_prompts.py -v`

Expected: 3 tests pass.

- [ ] **Step 5: Commit this checkpoint only if the user explicitly authorized commits**

```bash
git add src/ibrary/prompt_improvement/review_weakness_prompts.py tests/prompt_improvement/test_review_weakness_prompts.py
git commit -m "feat: define review weakness prompt contracts"
```

### Task 2: Add Review Selection, Normalization, and Stable Hashing

**Files:**
- Create: `tests/prompt_improvement/test_review_weaknesses.py`
- Create: `src/ibrary/prompt_improvement/review_weaknesses.py`

- [ ] **Step 1: Write failing tests for human review selection and normalization**

```python
import datetime as dt
from types import SimpleNamespace

from ibrary.prompt_improvement.review_weaknesses import (
    build_unit_evidence,
    compute_source_hash,
    select_latest_substantive_reviews,
)


def _human(row_id, reviewer, created_at, *, kind=None, notes=""):
    return SimpleNamespace(
        id=row_id,
        checked_by=reviewer,
        created_at=created_at,
        updated_at=created_at,
        notes=notes,
        overall_score=4.0,
        scores={"kind": kind} if kind else None,
    )


def test_selects_latest_substantive_review_per_named_reviewer():
    old = _human(1, "reviewer-a", dt.datetime(2026, 1, 1), notes="Old")
    latest = _human(2, "reviewer-a", dt.datetime(2026, 1, 2), notes="Latest")
    publish = _human(3, "reviewer-b", dt.datetime(2026, 1, 3), kind="publish", notes="Published")

    selected = select_latest_substantive_reviews([old, latest, publish])

    assert [row.id for row in selected] == [2]


def test_keeps_distinct_anonymous_substantive_rows():
    first = _human(4, None, dt.datetime(2026, 1, 1), notes="First")
    second = _human(5, None, dt.datetime(2026, 1, 2), kind="rejection", notes="Second")

    selected = select_latest_substantive_reviews([first, second])

    assert [row.id for row in selected] == [4, 5]


def test_build_unit_evidence_excludes_identity_and_normalizes_judge():
    curated = SimpleNamespace(
        curriculum_unit_id="unit-1",
        title="Cells",
        subtopic="Cell structure",
        prompt_version="curation:v1",
        curated_content_md="# Cells",
    )
    human = [_human(7, "reviewer@example.com", dt.datetime(2026, 1, 1), notes="Unclear")]
    judge = SimpleNamespace(
        id=9,
        updated_at=dt.datetime(2026, 1, 2),
        overall_score=5.0,
        judge_prompt_version="judge:v1",
        judge_model_version="gpt-test",
        scores={
            "passed": False,
            "recommendations": ["Add examples"],
            "correctness_notes": "Definition is incomplete",
            "clarity_notes": "Dense wording",
            "checkpoint_scores": [
                {"checkpoint_id": "3.1", "score": 3, "notes": "No alternative representation"}
            ],
        },
    )

    payload = build_unit_evidence(curated, human, judge)

    assert payload["evidence"][0]["source_id"] == "human:7"
    assert "checked_by" not in str(payload)
    assert "reviewer@example.com" not in str(payload)
    assert payload["evidence"][1]["source_id"] == "judge:9"
    assert payload["curated_content"] == "# Cells"


def test_source_hash_is_order_stable():
    left = {"b": [2, 1], "a": "x"}
    right = {"a": "x", "b": [2, 1]}
    assert compute_source_hash(left) == compute_source_hash(right)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: collection fails because the new module does not exist.

- [ ] **Step 3: Implement selection, normalization, and hashing**

```python
"""Fetch, summarize, and persist review-derived content weaknesses."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field, ValidationError, field_validator


SUBSTANTIVE_KINDS = {None, "rubric", "rejection"}
ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_PATH = Path(
    "data/docs/extracted_source_content/biology/review_weakness_summaries.json"
)


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"


def _kind(row: Any) -> str | None:
    scores = row.scores if isinstance(row.scores, dict) else {}
    return scores.get("kind")


def _is_substantive(row: Any) -> bool:
    kind = _kind(row)
    has_notes = bool((row.notes or "").strip())
    has_scores = bool(row.scores) or row.overall_score is not None
    return kind in SUBSTANTIVE_KINDS and (has_notes or has_scores)


def select_latest_substantive_reviews(rows: Iterable[Any]) -> list[Any]:
    latest: dict[str, Any] = {}
    anonymous: list[Any] = []
    for row in rows:
        if not _is_substantive(row):
            continue
        if not row.checked_by:
            anonymous.append(row)
            continue
        current = latest.get(row.checked_by)
        row_time = row.updated_at or row.created_at or dt.datetime.min
        current_time = (
            (current.updated_at or current.created_at or dt.datetime.min)
            if current is not None
            else dt.datetime.min
        )
        if current is None or (row_time, row.id) > (current_time, current.id):
            latest[row.checked_by] = row
    selected = [*latest.values(), *anonymous]
    return sorted(selected, key=lambda row: (row.created_at or dt.datetime.min, row.id))


def _human_evidence(row: Any) -> dict[str, Any]:
    return {
        "source_id": f"human:{row.id}",
        "source_type": _kind(row) or "note",
        "created_at": _iso(row.created_at),
        "overall_score": row.overall_score,
        "scores": row.scores if isinstance(row.scores, dict) else {},
        "notes": (row.notes or "").strip(),
    }


def _judge_evidence(row: Any) -> dict[str, Any]:
    scores = row.scores if isinstance(row.scores, dict) else {}
    return {
        "source_id": f"judge:{row.id}",
        "source_type": "udl_judge",
        "updated_at": _iso(row.updated_at),
        "overall_score": row.overall_score,
        "passed": scores.get("passed"),
        "recommendations": list(scores.get("recommendations") or []),
        "correctness_notes": scores.get("correctness_notes") or "",
        "clarity_notes": scores.get("clarity_notes") or "",
        "checkpoint_scores": list(scores.get("checkpoint_scores") or []),
        "judge_prompt_version": row.judge_prompt_version,
        "judge_model_version": row.judge_model_version,
    }


def build_unit_evidence(curated: Any, human_rows: Iterable[Any], judge_row: Any | None) -> dict:
    evidence = [_human_evidence(row) for row in select_latest_substantive_reviews(human_rows)]
    if judge_row is not None:
        evidence.append(_judge_evidence(judge_row))
    return {
        "curriculum_unit_id": curated.curriculum_unit_id,
        "title": curated.title or "",
        "subtopic": curated.subtopic or "",
        "curation_prompt_version": curated.prompt_version or "",
        "curated_content": curated.curated_content_md or "",
        "evidence": evidence,
    }


def compute_source_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run the selection and normalization tests**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: 4 tests pass.

- [ ] **Step 5: Commit this checkpoint only if commits are authorized**

```bash
git add src/ibrary/prompt_improvement/review_weaknesses.py tests/prompt_improvement/test_review_weaknesses.py
git commit -m "feat: normalize substantive content reviews"
```

### Task 3: Add Validated Model Calls

**Files:**
- Modify: `tests/prompt_improvement/test_review_weaknesses.py`
- Modify: `src/ibrary/prompt_improvement/review_weaknesses.py`
- Modify: `src/ibrary/config.py`

- [ ] **Step 1: Add failing validation and model-call tests**

```python
import pytest

from ibrary.prompt_improvement import review_weaknesses as rw


def test_summarize_unit_validates_and_forwards_source_ids(monkeypatch):
    monkeypatch.setattr(
        rw,
        "chat_completion_json",
        lambda **kwargs: {
            "weaknesses": [
                {
                    "category": "clarity",
                    "summary": "The explanation is dense.",
                    "severity": "medium",
                    "occurrence_count": 1,
                    "evidence_source_ids": ["human:7"],
                    "prompt_instruction_suggestion": "Use shorter sentences.",
                }
            ]
        },
    )
    result = rw.summarize_unit(
        {"curriculum_unit_id": "unit-1", "evidence": [{"source_id": "human:7"}]},
        model="gpt-test",
    )
    assert result.weaknesses[0].evidence_source_ids == ["human:7"]


def test_summarize_unit_rejects_unknown_source_reference(monkeypatch):
    monkeypatch.setattr(rw.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        rw,
        "chat_completion_json",
        lambda **kwargs: {
            "weaknesses": [
                {
                    "category": "clarity",
                    "summary": "Dense",
                    "severity": "medium",
                    "occurrence_count": 1,
                    "evidence_source_ids": ["human:999"],
                    "prompt_instruction_suggestion": "Simplify wording.",
                }
            ]
        },
    )
    with pytest.raises(ValueError, match="unknown evidence source"):
        rw.summarize_unit(
            {"curriculum_unit_id": "unit-1", "evidence": [{"source_id": "human:7"}]},
            model="gpt-test",
        )


def test_summarize_rollup_preserves_failed_units(monkeypatch):
    monkeypatch.setattr(
        rw,
        "chat_completion_json",
        lambda **kwargs: {
            "recurring_weaknesses": [],
            "instruction_themes": ["Require a concrete example."],
            "excluded_failed_units": ["unit-2"],
        },
    )
    result = rw.summarize_rollup(
        [{"curriculum_unit_id": "unit-1", "weaknesses": []}],
        ["unit-2"],
        model="gpt-test",
    )
    assert result.excluded_failed_units == ["unit-2"]
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: import errors for the model schemas and summarization functions.

- [ ] **Step 3: Add the model configuration**

Add after `OPENAI_MODEL` in `src/ibrary/config.py`:

```python
OPENAI_REVIEW_SUMMARY_MODEL: str = os.getenv("OPENAI_REVIEW_SUMMARY_MODEL") or OPENAI_MODEL
```

- [ ] **Step 4: Implement Pydantic schemas and model calls**

Add imports to `review_weaknesses.py`:

```python
from ibrary.llm.client import chat_completion_json
from ibrary.prompt_improvement.review_weakness_prompts import (
    CONTENT_SUMMARY_SYSTEM_PROMPT,
    ROLLUP_SYSTEM_PROMPT,
    build_content_summary_user_prompt,
    build_rollup_user_prompt,
)
```

Add schemas and functions:

```python
class Weakness(BaseModel):
    category: str
    summary: str = Field(min_length=1)
    severity: str
    occurrence_count: int = Field(ge=1)
    evidence_source_ids: list[str] = Field(min_length=1)
    prompt_instruction_suggestion: str = Field(min_length=1)

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        allowed = {
            "correctness", "clarity", "pedagogy", "udl_accessibility",
            "engagement", "structure", "other",
        }
        if value not in allowed:
            raise ValueError(f"category must be one of {sorted(allowed)}")
        return value

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, value: str) -> str:
        if value not in {"low", "medium", "high"}:
            raise ValueError("severity must be low, medium, or high")
        return value


class ContentWeaknessSummary(BaseModel):
    weaknesses: list[Weakness] = Field(default_factory=list)


class RecurringWeakness(BaseModel):
    theme: str = Field(min_length=1)
    priority: str
    affected_unit_ids: list[str] = Field(min_length=1)
    occurrence_count: int = Field(ge=1)
    evidence_source_ids: list[str] = Field(min_length=1)
    recommended_instruction: str = Field(min_length=1)

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value: str) -> str:
        if value not in {"low", "medium", "high"}:
            raise ValueError("priority must be low, medium, or high")
        return value


class WeaknessRollup(BaseModel):
    recurring_weaknesses: list[RecurringWeakness] = Field(default_factory=list)
    instruction_themes: list[str] = Field(default_factory=list)
    excluded_failed_units: list[str] = Field(default_factory=list)


def summarize_unit(payload: dict[str, Any], *, model: str) -> ContentWeaknessSummary:
    known_sources = {item["source_id"] for item in payload["evidence"]}
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            raw = chat_completion_json(
                component="review_weakness_content",
                model=model,
                system=CONTENT_SUMMARY_SYSTEM_PROMPT,
                user=build_content_summary_user_prompt(payload),
                metadata={"curriculum_unit_id": payload["curriculum_unit_id"]},
            )
            result = ContentWeaknessSummary.model_validate(raw)
            referenced = {
                source_id
                for weakness in result.weaknesses
                for source_id in weakness.evidence_source_ids
            }
            unknown = sorted(referenced - known_sources)
            if unknown:
                raise ValueError(f"unknown evidence source(s): {', '.join(unknown)}")
            return result
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def summarize_rollup(
    summaries: list[dict[str, Any]],
    failed_unit_ids: list[str],
    *,
    model: str,
) -> WeaknessRollup:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            raw = chat_completion_json(
                component="review_weakness_rollup",
                model=model,
                system=ROLLUP_SYSTEM_PROMPT,
                user=build_rollup_user_prompt(summaries, failed_unit_ids),
                metadata={"unit_count": len(summaries)},
            )
            result = WeaknessRollup.model_validate(raw)
            if sorted(result.excluded_failed_units) != sorted(failed_unit_ids):
                raise ValueError("rollup changed excluded_failed_units")
            return result
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error
```

- [ ] **Step 5: Run the model-call tests**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: 7 tests pass.

- [ ] **Step 6: Commit this checkpoint only if commits are authorized**

```bash
git add src/ibrary/config.py src/ibrary/prompt_improvement/review_weaknesses.py tests/prompt_improvement/test_review_weaknesses.py
git commit -m "feat: validate review weakness model outputs"
```

### Task 4: Add Atomic Artifact Persistence and Resume Logic

**Files:**
- Modify: `tests/prompt_improvement/test_review_weaknesses.py`
- Modify: `src/ibrary/prompt_improvement/review_weaknesses.py`

- [ ] **Step 1: Add failing persistence tests**

```python
import json


def test_load_artifact_rejects_invalid_json(tmp_path):
    path = tmp_path / "summaries.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid weakness artifact"):
        rw.load_artifact(path)


def test_write_artifact_round_trips_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "summaries.json"
    artifact = rw.new_artifact(model="gpt-test", prompt_version="review:v1")
    artifact["per_content"]["unit-1"] = {"status": "complete"}

    rw.write_artifact(path, artifact)

    assert json.loads(path.read_text(encoding="utf-8"))["per_content"]["unit-1"] == {
        "status": "complete"
    }
    assert not path.with_suffix(".json.tmp").exists()


def test_should_skip_requires_matching_hash_prompt_and_complete_status():
    entry = {
        "status": "complete",
        "source_hash": "source-1",
        "summarizer_prompt_version": "review:v1",
    }
    assert rw.should_skip(entry, "source-1", "review:v1", force=False)
    assert not rw.should_skip(entry, "source-2", "review:v1", force=False)
    assert not rw.should_skip(entry, "source-1", "review:v2", force=False)
    assert not rw.should_skip(entry, "source-1", "review:v1", force=True)
```

- [ ] **Step 2: Run the persistence tests and verify they fail**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: failures because artifact functions are undefined.

- [ ] **Step 3: Implement artifact loading, atomic writing, and skip checks**

```python
def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def new_artifact(*, model: str, prompt_version: str) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "model": model,
        "summarizer_prompt_version": prompt_version,
        "per_content": {},
        "rollup": None,
    }


def load_artifact(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid weakness artifact at {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ValueError(f"Invalid weakness artifact schema at {path}")
    if not isinstance(data.get("per_content"), dict):
        raise ValueError(f"Invalid per_content object at {path}")
    return data


def write_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact["updated_at"] = _utc_now()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def should_skip(
    entry: dict[str, Any] | None,
    source_hash: str,
    prompt_version: str,
    *,
    force: bool,
) -> bool:
    return bool(
        not force
        and entry
        and entry.get("status") == "complete"
        and entry.get("source_hash") == source_hash
        and entry.get("summarizer_prompt_version") == prompt_version
    )
```

- [ ] **Step 4: Run the persistence tests**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: 10 tests pass.

- [ ] **Step 5: Commit this checkpoint only if commits are authorized**

```bash
git add src/ibrary/prompt_improvement/review_weaknesses.py tests/prompt_improvement/test_review_weaknesses.py
git commit -m "feat: persist resumable weakness artifacts"
```

### Task 5: Add Neon Loading and Two-Stage Orchestration

**Files:**
- Modify: `tests/prompt_improvement/test_review_weaknesses.py`
- Modify: `src/ibrary/prompt_improvement/review_weaknesses.py`
- Modify: `src/ibrary/prompt_improvement/__init__.py`

- [ ] **Step 1: Add failing orchestration tests**

```python
def test_run_analysis_skips_unchanged_units_and_rolls_up_successes(tmp_path, monkeypatch):
    curated = SimpleNamespace(
        curriculum_unit_id="unit-1",
        title="Cells",
        subtopic="Cells",
        prompt_version="curation:v1",
        curated_content_md="# Cells",
        manual_quality_checks=[
            _human(7, "reviewer-a", dt.datetime(2026, 1, 1), notes="Unclear")
        ],
        udl_score_row=None,
    )
    monkeypatch.setattr(rw, "load_review_units", lambda unit_ids=None, limit=None: [curated])
    monkeypatch.setattr(rw, "get_review_weakness_prompt_version", lambda: "review:v1")
    content_calls = []

    def fake_content(payload, *, model):
        content_calls.append(payload["curriculum_unit_id"])
        return rw.ContentWeaknessSummary(weaknesses=[])

    monkeypatch.setattr(rw, "summarize_unit", fake_content)
    monkeypatch.setattr(
        rw,
        "summarize_rollup",
        lambda summaries, failed_unit_ids, *, model: rw.WeaknessRollup(
            recurring_weaknesses=[],
            instruction_themes=[],
            excluded_failed_units=failed_unit_ids,
        ),
    )
    output = tmp_path / "weaknesses.json"

    first = rw.run_review_weakness_analysis(output_path=output, model="gpt-test")
    second = rw.run_review_weakness_analysis(output_path=output, model="gpt-test")

    assert content_calls == ["unit-1"]
    assert first["per_content"]["unit-1"]["status"] == "complete"
    assert second["rollup"]["excluded_failed_units"] == []


def test_run_analysis_persists_needs_review_after_model_failure(tmp_path, monkeypatch):
    curated = SimpleNamespace(
        curriculum_unit_id="unit-1",
        title="Cells",
        subtopic="Cells",
        prompt_version="curation:v1",
        curated_content_md="# Cells",
        manual_quality_checks=[
            _human(7, "reviewer-a", dt.datetime(2026, 1, 1), notes="Unclear")
        ],
        udl_score_row=None,
    )
    monkeypatch.setattr(rw, "load_review_units", lambda unit_ids=None, limit=None: [curated])
    monkeypatch.setattr(rw, "get_review_weakness_prompt_version", lambda: "review:v1")
    monkeypatch.setattr(
        rw, "summarize_unit", lambda payload, *, model: (_ for _ in ()).throw(ValueError("bad"))
    )
    monkeypatch.setattr(
        rw,
        "summarize_rollup",
        lambda summaries, failed_unit_ids, *, model: rw.WeaknessRollup(
            recurring_weaknesses=[],
            instruction_themes=[],
            excluded_failed_units=failed_unit_ids,
        ),
    )

    result = rw.run_review_weakness_analysis(
        output_path=tmp_path / "weaknesses.json",
        model="gpt-test",
    )

    assert result["per_content"]["unit-1"]["status"] == "[Needs Review]"
    assert result["rollup"]["excluded_failed_units"] == ["unit-1"]
```

- [ ] **Step 2: Run the orchestration tests and verify they fail**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: failures because loading and orchestration functions are undefined.

- [ ] **Step 3: Add SQLAlchemy loading**

Add imports:

```python
from sqlalchemy.orm import joinedload

from ibrary.config import OPENAI_REVIEW_SUMMARY_MODEL
from ibrary.models import CuratedContent
from ibrary.review.db import get_review_session
from ibrary.prompt_improvement.review_weakness_prompts import (
    get_review_weakness_prompt_version,
)
```

Add:

```python
def load_review_units(
    *,
    unit_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[CuratedContent]:
    session = get_review_session()
    try:
        query = session.query(CuratedContent).options(
            joinedload(CuratedContent.manual_quality_checks),
            joinedload(CuratedContent.udl_score_row),
        )
        if unit_ids:
            query = query.filter(CuratedContent.curriculum_unit_id.in_(unit_ids))
        query = query.order_by(CuratedContent.curriculum_unit_id)
        if limit is not None:
            query = query.limit(limit)
        rows = query.all()
        return [
            row
            for row in rows
            if select_latest_substantive_reviews(row.manual_quality_checks)
            or row.udl_score_row is not None
        ]
    finally:
        session.close()
```

- [ ] **Step 4: Add two-stage orchestration**

```python
def run_review_weakness_analysis(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    unit_ids: list[str] | None = None,
    limit: int | None = None,
    force: bool = False,
    model: str = OPENAI_REVIEW_SUMMARY_MODEL,
) -> dict[str, Any]:
    prompt_version = get_review_weakness_prompt_version()
    artifact = load_artifact(output_path) or new_artifact(
        model=model,
        prompt_version=prompt_version,
    )
    artifact["model"] = model
    artifact["summarizer_prompt_version"] = prompt_version

    for curated in load_review_units(unit_ids=unit_ids, limit=limit):
        payload = build_unit_evidence(
            curated,
            curated.manual_quality_checks,
            curated.udl_score_row,
        )
        source_hash = compute_source_hash(payload)
        unit_id = curated.curriculum_unit_id
        existing = artifact["per_content"].get(unit_id)
        if should_skip(existing, source_hash, prompt_version, force=force):
            continue
        source_ids = [item["source_id"] for item in payload["evidence"]]
        try:
            summary = summarize_unit(payload, model=model)
            artifact["per_content"][unit_id] = {
                "status": "complete",
                "curriculum_unit_id": unit_id,
                "title": curated.title or "",
                "subtopic": curated.subtopic or "",
                "curation_prompt_version": curated.prompt_version or "",
                "summarizer_prompt_version": prompt_version,
                "model": model,
                "source_hash": source_hash,
                "source_evidence_ids": source_ids,
                "summary": summary.model_dump(mode="json"),
                "error": None,
                "updated_at": _utc_now(),
            }
        except Exception as exc:
            artifact["per_content"][unit_id] = {
                "status": "[Needs Review]",
                "curriculum_unit_id": unit_id,
                "title": curated.title or "",
                "subtopic": curated.subtopic or "",
                "curation_prompt_version": curated.prompt_version or "",
                "summarizer_prompt_version": prompt_version,
                "model": model,
                "source_hash": source_hash,
                "source_evidence_ids": source_ids,
                "summary": None,
                "error": f"{type(exc).__name__}: {exc}",
                "updated_at": _utc_now(),
            }
        write_artifact(output_path, artifact)

    successful = [
        {
            "curriculum_unit_id": unit_id,
            **entry["summary"],
        }
        for unit_id, entry in sorted(artifact["per_content"].items())
        if entry.get("status") == "complete" and entry.get("summary") is not None
    ]
    failed = sorted(
        unit_id
        for unit_id, entry in artifact["per_content"].items()
        if entry.get("status") != "complete"
    )
    rollup_input_hash = compute_source_hash(
        {"summaries": successful, "failed_unit_ids": failed}
    )
    existing_rollup = artifact.get("rollup") or {}
    if (
        force
        or existing_rollup.get("input_summary_hash") != rollup_input_hash
        or existing_rollup.get("summarizer_prompt_version") != prompt_version
    ):
        rollup = summarize_rollup(successful, failed, model=model)
        artifact["rollup"] = {
            **rollup.model_dump(mode="json"),
            "input_summary_hash": rollup_input_hash,
            "summarizer_prompt_version": prompt_version,
            "model": model,
            "updated_at": _utc_now(),
        }
        write_artifact(output_path, artifact)
    return artifact
```

- [ ] **Step 5: Export the public API**

Add to `src/ibrary/prompt_improvement/__init__.py`:

```python
from ibrary.prompt_improvement.review_weaknesses import run_review_weakness_analysis
```

Add `"run_review_weakness_analysis"` to `__all__`.

- [ ] **Step 6: Run all review weakness tests**

Run: `uv run pytest tests/prompt_improvement/test_review_weaknesses.py -v`

Expected: 12 tests pass.

- [ ] **Step 7: Commit this checkpoint only if commits are authorized**

```bash
git add src/ibrary/prompt_improvement/__init__.py src/ibrary/prompt_improvement/review_weaknesses.py tests/prompt_improvement/test_review_weaknesses.py
git commit -m "feat: orchestrate review weakness analysis"
```

### Task 6: Add the Standalone CLI

**Files:**
- Create: `scripts/summarize_review_weaknesses.py`
- Create: `tests/prompt_improvement/test_summarize_review_weaknesses_cli.py`

- [ ] **Step 1: Write the failing CLI test**

```python
import runpy
import sys
from pathlib import Path


def test_cli_forwards_filters_and_force(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        "ibrary.prompt_improvement.review_weaknesses.run_review_weakness_analysis",
        lambda **kwargs: calls.append(kwargs) or {"per_content": {}, "rollup": {}},
    )
    output = tmp_path / "summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_review_weaknesses.py",
            "--output",
            str(output),
            "--units",
            "unit-1",
            "unit-2",
            "--limit",
            "2",
            "--force",
        ],
    )

    runpy.run_path("scripts/summarize_review_weaknesses.py", run_name="__main__")

    assert calls == [
        {
            "output_path": output,
            "unit_ids": ["unit-1", "unit-2"],
            "limit": 2,
            "force": True,
        }
    ]
```

- [ ] **Step 2: Run the CLI test and verify it fails**

Run: `uv run pytest tests/prompt_improvement/test_summarize_review_weaknesses_cli.py -v`

Expected: failure because the script does not exist.

- [ ] **Step 3: Implement the CLI**

```python
#!/usr/bin/env python3
"""Summarize Neon review weaknesses for prompt improvement."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ibrary.prompt_improvement.review_weaknesses import (  # noqa: E402
    DEFAULT_OUTPUT_PATH,
    run_review_weakness_analysis,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize human and UDL judge weaknesses from Neon reviews."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--units", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    artifact = run_review_weakness_analysis(
        output_path=args.output,
        unit_ids=args.units,
        limit=args.limit,
        force=args.force,
    )
    complete = sum(
        entry.get("status") == "complete"
        for entry in artifact["per_content"].values()
    )
    needs_review = sum(
        entry.get("status") != "complete"
        for entry in artifact["per_content"].values()
    )
    print(f"Wrote {args.output}: complete={complete}, needs_review={needs_review}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the CLI test**

Run: `uv run pytest tests/prompt_improvement/test_summarize_review_weaknesses_cli.py -v`

Expected: 1 test passes.

- [ ] **Step 5: Verify CLI help without Neon or OpenAI access**

Run: `uv run python scripts/summarize_review_weaknesses.py --help`

Expected: help lists `--output`, `--units`, `--limit`, and `--force`.

- [ ] **Step 6: Commit this checkpoint only if commits are authorized**

```bash
git add scripts/summarize_review_weaknesses.py tests/prompt_improvement/test_summarize_review_weaknesses_cli.py
git commit -m "feat: add review weakness analysis CLI"
```

### Task 7: Document Configuration and Usage

**Files:**
- Modify: `.env.example`
- Modify: `docs/PIPELINE_ORCHESTRATOR.md`

- [ ] **Step 1: Add the optional model setting to `.env.example`**

Place beside the existing OpenAI model settings:

```dotenv
# Optional model for offline human/judge review weakness summarization.
# Falls back to OPENAI_MODEL when unset.
OPENAI_REVIEW_SUMMARY_MODEL=
```

- [ ] **Step 2: Document the post-review workflow**

Add this section to `docs/PIPELINE_ORCHESTRATOR.md`:

````markdown
## Review weakness summarization

After reviewers have submitted feedback in Neon, generate per-content weakness
summaries and a cross-content prompt-improvement rollup:

```bash
uv run python scripts/summarize_review_weaknesses.py
```

The command reads `DATABASE_URL_REVIEW`, uses
`OPENAI_REVIEW_SUMMARY_MODEL` (falling back to `OPENAI_MODEL`), and writes:

`data/docs/extracted_source_content/biology/review_weakness_summaries.json`

Reruns skip content whose normalized review evidence and summarizer prompt
version are unchanged. Use `--force` to regenerate all selected units, or
`--units <unit-id> ...` for a targeted run. Entries marked `[Needs Review]`
retain their error details and are excluded from the global rollup.
````

- [ ] **Step 3: Check documentation references**

Run: `rg "OPENAI_REVIEW_SUMMARY_MODEL|summarize_review_weaknesses" .env.example docs/PIPELINE_ORCHESTRATOR.md`

Expected: both files reference the new model setting and the documentation references the script.

- [ ] **Step 4: Commit this checkpoint only if commits are authorized**

```bash
git add .env.example docs/PIPELINE_ORCHESTRATOR.md
git commit -m "docs: explain review weakness summarization"
```

### Task 8: Run Full Verification

**Files:**
- Verify all files changed in Tasks 1-7.

- [ ] **Step 1: Run the focused test suite**

Run:

```bash
uv run pytest \
  tests/prompt_improvement/test_review_weakness_prompts.py \
  tests/prompt_improvement/test_review_weaknesses.py \
  tests/prompt_improvement/test_summarize_review_weaknesses_cli.py \
  -v
```

Expected: all focused tests pass.

- [ ] **Step 2: Run related regression tests**

Run:

```bash
uv run pytest \
  tests/review/test_service.py \
  tests/judging/test_incremental_judge.py \
  -v
```

Expected: all related tests pass.

- [ ] **Step 3: Run lint checks using the repository's configured command**

Run: `uv run ruff check src/ibrary/prompt_improvement scripts/summarize_review_weaknesses.py tests/prompt_improvement`

Expected: `All checks passed!`

- [ ] **Step 4: Perform a one-unit live smoke test only when Neon and OpenAI credentials are configured**

Run:

```bash
uv run python scripts/summarize_review_weaknesses.py \
  --units bio_sss1_theme1_topic1_content0 \
  --output /tmp/ibrary-review-weakness-smoke.json
```

Expected: the command reports one complete unit or one visible `[Needs Review]` entry, writes valid JSON, and does not expose reviewer identity.

- [ ] **Step 5: Inspect the smoke artifact for privacy and traceability**

Run:

```bash
uv run python -c 'import json, pathlib; p=pathlib.Path("/tmp/ibrary-review-weakness-smoke.json"); d=json.loads(p.read_text()); print(d["schema_version"], sorted(d["per_content"]), bool(d["rollup"]))'
```

Expected: prints schema version `1`, the selected unit ID, and `True`. Manually confirm the artifact contains `human:<id>` or `judge:<id>` source references but no reviewer names, emails, or user IDs.

- [ ] **Step 6: Review repository state**

Run: `git status --short && git diff --check`

Expected: only planned source, test, documentation, and generated design/plan files are changed; `.env.content-api` remains untracked and must not be staged.

- [ ] **Step 7: Create a final commit only if the user explicitly requested commits**

```bash
git add \
  .env.example \
  docs/PIPELINE_ORCHESTRATOR.md \
  scripts/summarize_review_weaknesses.py \
  src/ibrary/config.py \
  src/ibrary/prompt_improvement/__init__.py \
  src/ibrary/prompt_improvement/review_weakness_prompts.py \
  src/ibrary/prompt_improvement/review_weaknesses.py \
  tests/prompt_improvement/test_review_weakness_prompts.py \
  tests/prompt_improvement/test_review_weaknesses.py \
  tests/prompt_improvement/test_summarize_review_weaknesses_cli.py
git commit -m "feat: summarize review weaknesses for prompt improvement"
```
