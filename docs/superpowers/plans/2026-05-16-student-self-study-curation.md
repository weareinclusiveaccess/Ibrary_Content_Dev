# Student Self-Study Curation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Curated modules are engaging student self-study prose (VI-friendly), with practice split across inline checks, end review, and `student_activities`; minimal orchestrator wiring in v2 `curate`.

**Architecture:** Rewrite `curation/prompts.py` (v2.0-student-self-study). Implement `TextCuratorAgent` calling existing `curate_unit()`; `ModuleAssemblerAgent` copies result to context; MediaLinker/Formula remain no-op. `step_curate` uses `PipelineOrchestrator` when `PIPELINE_VERSION>=2` and `USE_CURATION_ORCHESTRATOR` (default true). Judge prompts gain self-study readability checks.

**Tech Stack:** Python 3.11+, structlog, Pydantic `CuratedModule`, existing `PipelineOrchestrator`, pytest.

**Spec:** [2026-05-16-student-self-study-curation-design.md](../specs/2026-05-16-student-self-study-curation-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `src/ibrary/curation/prompts.py` | Student self-study system + user templates |
| `src/ibrary/curation/curation_service.py` | `curate_unit_orchestrated()` helper; `curate_all` delegates |
| `src/ibrary/pipeline/context.py` | `curated_module: CuratedModule \| None` on context |
| `src/ibrary/pipeline/subagents.py` | Real TextCurator + Assembler; deferred media/formula |
| `src/ibrary/pipeline/orchestrator.py` | Unchanged DAG; optional export `curate_unit_module()` |
| `src/ibrary/config.py` | `USE_CURATION_ORCHESTRATOR` env flag |
| `scripts/run_pipeline.py` | v2 curate uses orchestrator path |
| `src/ibrary/judging/subtopic_judge.py` | Judge user prompt: self-study + list-density note |
| `tests/curation/test_prompts_self_study.py` | Prompt contract tests (no LLM) |
| `tests/pipeline/test_orchestrator_curate.py` | Orchestrator wiring with mocked `curate_unit` |
| `docs/REVIEW_PIPELINE_V2.md` | Spot-check steps for new prompt version |

---

### Task 1: Prompt templates — student self-study

**Files:**
- Modify: `src/ibrary/curation/prompts.py`

- [ ] **Step 1: Bump version tag**

Set:
```python
PROMPT_VERSION_TAG = "v2.0-student-self-study"
```

- [ ] **Step 2: Replace SYSTEM_PROMPT_TEMPLATE core audience block**

Change opening role from “teacher creating classroom content” to self-study author. Add explicit rules:

- Primary reader: **student studying alone** (screen readers included).
- **Prose-first**; lists only when essential (max ~6 items per list).
- **Forbidden in `curated_content`:** teacher setup, classroom logistics, “Teachers:”, group/outdoor/lab directions, long activity matrices, standalone `## Accessibility notes`.
- UDL still applies via clear language, figure descriptions, heading structure—not via classroom activity catalogs.

Keep existing curriculum-authority and textbook-excerpt rules (subtopic is source of truth; paraphrase excerpts).

- [ ] **Step 3: Replace CURATION_PROMPT_TEMPLATE JSON contract**

Update `curated_content` requirements:

1. Markdown with `##` / `###` focused on subtopic.
2. After each major `##` section: 1–2 **“Check yourself”** sentences (inline, not numbered lists).
3. Final section: **`## Review questions`** with 3–5 short prose questions.
4. Figure mentions: full text description in narrative.
5. **Do not** include `## Accessibility notes` in markdown.

Update JSON keys guidance:

- `student_activities`: 2–4 items for optional Practice tab; concrete, subtopic-scoped; no classroom logistics.
- `teacher_activities`: **0–3** bullets for reviewer reference only; **may be empty list**; must not appear in `curated_content`.
- `accessibility_checklist`: 4–6 strings for reviewers (not rendered as student section).

Remove lines that require teacher activities inside markdown or “include accessible options for every classroom activity.”

- [ ] **Step 4: Verify prompt version hash changes**

Run:
```bash
uv run python -c "from ibrary.curation.prompts import get_prompt_version; print(get_prompt_version())"
```
Expected: prefix `v2.0-student-self-study:`

---

### Task 2: Config flag for orchestrator rollback

**Files:**
- Modify: `src/ibrary/config.py`

- [ ] **Step 1: Add env flag**

After `PIPELINE_VERSION` block:
```python
USE_CURATION_ORCHESTRATOR: bool = os.getenv(
    "USE_CURATION_ORCHESTRATOR", "true"
).lower() in ("1", "true", "yes")
```

- [ ] **Step 2: Document in `.env.example`**

Add:
```env
# v2 curate: use PipelineOrchestrator (TextCurator → passthrough media/formula → assemble)
USE_CURATION_ORCHESTRATOR=true
```

---

### Task 3: Pipeline context holds `CuratedModule`

**Files:**
- Modify: `src/ibrary/pipeline/context.py`

- [ ] **Step 1: Add field**

```python
from ibrary.curation.schemas import CuratedModule

# inside PipelineContext dataclass:
curated_module: CuratedModule | None = None
```

Use `from __future__ import annotations` if needed to avoid circular import; alternatively use `CuratedModule | None = None` with TYPE_CHECKING import.

- [ ] **Step 2: Extend `_branch_context` in orchestrator.py**

In `src/ibrary/pipeline/orchestrator.py` `_branch_context`, copy `curated_module=base.curated_module` (parallel branches read-only until merge).

In `_merge_parallel_contexts`, do not overwrite `curated_module` from branches (only assets/formulas merge today).

---

### Task 4: Implement TextCuratorAgent

**Files:**
- Modify: `src/ibrary/pipeline/subagents.py`

- [ ] **Step 1: Implement `TextCuratorAgent.run`**

Replace stub with:

```python
def run(self, ctx: PipelineContext) -> PipelineContext:
    if not ctx.unit:
        ctx.add_error("text_curator: missing unit on context")
        return ctx
    if not ctx.excerpt_chunks and int(os.getenv("PIPELINE_VERSION", "1")) >= 2:
        raise AgentSkipped("text_curator: no excerpt_chunks (run filter_relevance)")

    from ibrary.curation.curation_service import curate_unit

    chunk_ids = [c["chunk_id"] for c in ctx.excerpt_chunks]
    module = curate_unit(
        ctx.unit,
        chunk_ids,
        alignment_matches=ctx.alignment_matches,
        excerpt_chunks=ctx.excerpt_chunks or None,
    )
    if module is None:
        ctx.add_error("text_curator: curate_unit returned None")
        return ctx
    ctx.curated_module = module
    ctx.metadata["text_curator_status"] = "ok"
    return ctx
```

For v1 path (no excerpts), `curate_all` may still call `curate_unit` directly when orchestrator disabled—do not require excerpts in TextCurator when `PIPELINE_VERSION<2`.

- [ ] **Step 2: Implement `ModuleAssemblerAgent.run`**

```python
def run(self, ctx: PipelineContext) -> PipelineContext:
    if ctx.curated_module is None:
        ctx.add_error("module_assembler: no curated_module")
        return ctx
    ctx.learning_module = ctx.curated_module.model_dump(by_alias=True)
    ctx.metadata["assembler_status"] = "passthrough"
    return ctx
```

- [ ] **Step 3: MediaLinker / FormulaAgent — explicit deferred status**

Keep skip when no placeholders; when placeholders exist later, log:
```python
ctx.metadata["media_linker_status"] = "deferred"
```
(same for formula). No errors on empty placeholders.

---

### Task 5: Orchestrated single-unit entrypoint

**Files:**
- Modify: `src/ibrary/curation/curation_service.py`

- [ ] **Step 1: Add helper**

```python
def curate_unit_via_orchestrator(
    unit: CurriculumUnit,
    alignment: dict,
    *,
    excerpt_chunks: list[dict] | None = None,
) -> CuratedModule | None:
    from ibrary.alignment.matches import alignment_matches
    from ibrary.pipeline.context import PipelineContext
    from ibrary.pipeline.orchestrator import create_orchestrator
    from ibrary.relevance.context import build_curation_excerpts

    matches = alignment_matches(alignment, unit.curriculum_unit_id)
    if not matches:
        logger.warning("no_alignment_skip", unit_id=unit.curriculum_unit_id)
        return None

    excerpts = excerpt_chunks
    if excerpts is None and int(os.getenv("PIPELINE_VERSION", str(PIPELINE_VERSION))) >= 2:
        excerpts = build_curation_excerpts(unit.curriculum_unit_id)
        if not excerpts:
            logger.warning("no_relevant_excerpts", unit_id=unit.curriculum_unit_id)
            return None

    ctx = PipelineContext(
        curriculum_unit_id=unit.curriculum_unit_id,
        unit=unit,
        alignment_matches=matches,
        excerpt_chunks=excerpts or [],
    )
    ctx = create_orchestrator().curate_unit(ctx)
    if ctx.errors:
        logger.warning("orchestrator_errors", unit_id=unit.curriculum_unit_id, errors=ctx.errors)
    return ctx.curated_module
```

- [ ] **Step 2: Update `curate_all` loop**

When `PIPELINE_VERSION>=2` and `USE_CURATION_ORCHESTRATOR`:
```python
module = curate_unit_via_orchestrator(unit, alignment)
```
Else keep existing `curate_unit` branch (v1 full chunks or v2 direct call).

Preserve `resume_from` skip logic unchanged.

---

### Task 6: Wire `step_curate` logging

**Files:**
- Modify: `scripts/run_pipeline.py`

- [ ] **Step 1: Log orchestrator mode at step start**

In `step_curate`, after logger.info:
```python
from ibrary.config import PIPELINE_VERSION, USE_CURATION_ORCHESTRATOR
logger.info(
    "curate_mode",
    pipeline_version=int(os.getenv("PIPELINE_VERSION", str(PIPELINE_VERSION))),
    use_orchestrator=USE_CURATION_ORCHESTRATOR,
)
```

No other change required if `curate_all` already delegates.

---

### Task 7: Judge prompt — self-study readability

**Files:**
- Modify: `src/ibrary/judging/subtopic_judge.py`

- [ ] **Step 1: Extend JUDGE_SYSTEM_PROMPT**

Add after clarity bullet:
```text
- **self_study**: student can learn the subtopic without a teacher present; no steps that require \
classroom setup, lab, or group work in the main content; excessive bullet lists reduce the score.
```

- [ ] **Step 2: Extend JUDGE_USER_TEMPLATE**

Add line before content block:
```text
Evaluate **curated_content** as the primary student-facing lesson. Ignore teacher_activities for \
student experience scoring unless they contradict the lesson.
```

Optional JSON output field (if judge schema extended):
`"self_study_score": <1-10>` — only if `SubtopicJudgeResult` model updated in `judging/schemas.py`; otherwise fold into `clarity_notes`.

---

### Task 8: Tests (no live LLM)

**Files:**
- Create: `tests/curation/test_prompts_self_study.py`
- Create: `tests/pipeline/test_orchestrator_curate.py`

- [ ] **Step 1: Prompt contract test**

```python
# tests/curation/test_prompts_self_study.py
from ibrary.curation.prompts import (
    CURATION_PROMPT_TEMPLATE,
    PROMPT_VERSION_TAG,
    SYSTEM_PROMPT_TEMPLATE,
    format_curation_prompt,
    format_system_prompt,
)


def test_prompt_version_tag():
    assert PROMPT_VERSION_TAG == "v2.0-student-self-study"


def test_system_prompt_forbids_teacher_classroom_in_body():
    s = format_system_prompt("Biology")
    lower = s.lower()
    assert "self-study" in lower or "studying alone" in lower or "study on their own" in lower
    assert "accessibility notes" in lower or "do not" in lower


def test_curation_prompt_requires_review_questions_and_check_yourself():
    user = format_curation_prompt(
        "Biology",
        class_name="SSS 1",
        theme="Life",
        theme_number="1",
        topic_number="1",
        topic="Topic",
        subtopic="Subtopic",
        objectives="- obj",
        curriculum_student_activities="(none)",
        curriculum_teacher_activities="(none)",
        alignment_scores="- x: 0.5",
        textbook_content="excerpt",
    )
    lower = user.lower()
    assert "review questions" in lower
    assert "check yourself" in lower
    assert "accessibility notes" not in lower or "do not" in lower


def test_curation_prompt_teacher_activities_optional_cap():
    assert "0–3" in CURATION_PROMPT_TEMPLATE or "0-3" in CURATION_PROMPT_TEMPLATE
```

- [ ] **Step 2: Run tests (expect fail before Task 1)**

```bash
uv run pytest tests/curation/test_prompts_self_study.py -v
```

- [ ] **Step 3: Orchestrator wiring test with mock**

```python
# tests/pipeline/test_orchestrator_curate.py
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
    with patch("ibrary.pipeline.subagents.curate_unit", return_value=module):
        out = create_orchestrator().curate_unit(ctx)
    assert out.curated_module is not None
    assert out.learning_module is not None
    assert out.learning_module["curriculum_unit_id"] == module.curriculum_unit_id
```

Note: patch path may need to be `ibrary.curation.curation_service.curate_unit` depending on import site inside `TextCuratorAgent`—adjust to where `curate_unit` is imported in `subagents.py`.

- [ ] **Step 4: Run pipeline tests**

```bash
uv run pytest tests/curation tests/pipeline -v
```

---

### Task 9: Manual verification

- [ ] **Step 1: Re-curate golden unit**

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps curate --curate-unit bio_sss1_theme1_topic1_content0 --replace-curated
```

(Or delete that unit from `curated_content.json` first, then curate without `--replace-curated`.)

- [ ] **Step 2: Spot-check `curated_content.json`**

Confirm:
- No `Teachers:` / `## Accessibility notes`
- Has `Check yourself` and `## Review questions`
- Mostly paragraphs; no Activity 1–5 block
- `teacher_activities` length ≤ 3
- `prompt_version` starts with `v2.0-student-self-study`

- [ ] **Step 3: Confirm orchestrator logs**

Log lines should include: `subagent_start` `text_curator` → `media_linker` skip → `formula` skip → `module_assembler`.

- [ ] **Step 4: Judge sample**

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps judge --curate-unit bio_sss1_theme1_topic1_content0
```

---

### Task 10: Docs touch-up

**Files:**
- Modify: `docs/REVIEW_PIPELINE_V2.md` (Step 12 spot-check bullets only)

- [ ] Add pass criteria for self-study prose and `v2.0-student-self-study` prompt version.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Prose-first, list caps | Task 1 |
| Inline Check yourself + Review questions | Task 1 |
| student_activities tab | Task 1 |
| teacher_activities 0–3, not in body | Task 1 |
| No Accessibility notes in body | Task 1, 8 |
| Orchestrator minimal wire | Tasks 3–6 |
| Media/formula deferred | Task 4 |
| Judge self-study | Task 7 |
| Re-curate / prompt version | Tasks 1, 9 |

## Out of scope (Phase 2 — separate plan)

- MediaLinker S3 / OpenStax
- FormulaAgent LaTeX
- `content_blocks` / DynamoDB assets publish

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-05-16-student-self-study-curation.md`.

**Two execution options:**

1. **Subagent-driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline execution** — implement tasks in this session with checkpoints  

Which approach do you want?
