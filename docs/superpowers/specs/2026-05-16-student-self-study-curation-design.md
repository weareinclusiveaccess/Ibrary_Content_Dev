# Student self-study curation — Design Spec

**Status:** Approved (2026-05-16)  
**Relates to:** [2026-05-16-biology-pipeline-v2-design.md](./2026-05-16-biology-pipeline-v2-design.md)  
**Goal:** Curated modules read as engaging **student self-study** (including screen-reader users), with reviewers validating the same artifact—while keeping a **minimal orchestrator hook** for future images/formulas.

---

## 1. Problem

Current curation prompts (UDL v1.3–v1.4) produce:

- Long bullet lists and numbered classroom activities inside `curated_content`
- Explicit teacher setup (“Teachers: Please adapt…”, lab/outdoor logistics)
- A standalone `## Accessibility notes` section in the student body
- Empty `images: []` — figures described only in prose

Students (including visually impaired learners) need a **single, clear narrative** they can read alone. Reviewers need the **same** `curated_content` to judge quality, plus small JSON fields for curriculum alignment checks.

---

## 2. Reader model (approved: option C)

| Field | Audience | Rules |
|-------|----------|--------|
| `curated_content` | **Students** (+ reviewers read same text) | Self-study prose; minimal lists; no teacher classroom directions |
| `student_activities` | **Students** (optional **Practice** tab in app) | 2–4 short activities; not duplicated as long lists in body |
| `teacher_activities` | **Reviewers / teachers only** | **0–3** brief bullets max; **may be empty**; never copied into `curated_content` |
| `learning_objectives`, `key_takeaways`, `glossary_terms` | App chrome + review | Unchanged role |
| `accessibility_checklist` | **Reviewers only** | JSON metadata; **not** rendered as a student lesson section |

---

## 3. Content style rules (`curated_content`)

### 3.1 Narrative

- **Prose-first:** short paragraphs (2–4 sentences); use `##` / `###` for structure.
- **Engaging tone:** concrete examples (everyday/local where appropriate); avoid worksheet voice.
- **Subtopic-scoped:** curriculum subtopic is authoritative (existing rule retained).

### 3.2 Lists and distraction

- Avoid nested bullets and multi-level outlines.
- Use a list only when essential (e.g. mnemonic, 3–5 characteristics); **cap ~6 items** per list.
- **Forbidden in body:** “Activity 1…5”, group-work logistics, “your teacher will…”, outdoor/lab setup, long accessibility-variant matrices.

### 3.3 Practice (approved: A + B + C)

| Layer | Location | Format |
|-------|----------|--------|
| **A — Inline** | After each major `##` section | 1–2 **“Check yourself”** prompts as **1–2 prose sentences** (not numbered drills) |
| **B — End** | Final section `## Review questions` | **3–5** short questions; prose or brief Q&A; no multi-part exams |
| **C — Tab** | `student_activities` JSON array | 2–4 optional practice items; app shows separately |

### 3.4 Accessibility (VI students + reviewers)

- Every figure reference includes a **full text description** in the narrative (until real assets exist).
- Proper heading hierarchy (`##`, `###`); no meaning conveyed by layout/color alone.
- **No** standalone `## Accessibility notes` in `curated_content` (approved).
- Reviewer-facing accessibility evidence lives in `accessibility_checklist` (4–6 short strings max).

### 3.5 Teacher content

- `teacher_activities`: optional, max 3 bullets, reviewer reference only.
- Curriculum official teacher activities from validated JSON inform reviewer field only—not pasted into student body.

---

## 4. Images and formulas (phased)

| Capability | Phase 1 (this spec) | Phase 2 (follow-up) |
|------------|-------------------|---------------------|
| Images | Text descriptions in prose; `images: []` | MediaLinkerAgent resolves placeholders → `assets[]` |
| Chemical/math notation | Plain Unicode/text in prose | FormulaAgent → `formulas[]` with LaTeX `\ce{}` |
| Output shape | Existing `CuratedModule` + `curated_content` markdown | Optional `LearningModule` v1 `content_blocks` |

Phase 1 does **not** block on S3 image wiring or LaTeX pipeline.

---

## 5. Orchestrator integration (minimal impact — approved)

### 5.1 Principle

Wire `PipelineOrchestrator` into batch `curate` so the DAG is the **single entry point**, but Phase 1 only implements **real work** in `TextCuratorAgent`. Other agents remain **no-op passthrough** until Phase 2.

### 5.2 DAG (unchanged structure)

```text
TextCuratorAgent
    → MediaLinkerAgent  ∥  FormulaAgent   (no-op if no placeholders)
    → ModuleAssemblerAgent                 (passthrough → CuratedModule)
```

`filter_relevance` and `judge` **do not** use the orchestrator.

### 5.3 Agent responsibilities (Phase 1)

| Agent | Phase 1 behavior |
|-------|------------------|
| **TextCuratorAgent** | Build `PipelineContext` (unit, excerpts, alignment_matches); call `curation_service.curate_unit()` with new prompts; store `CuratedModule` on context |
| **MediaLinkerAgent** | Skip if no `image_placeholders`; else no-op (log `deferred`) |
| **FormulaAgent** | Skip if no `formula_placeholders`; else no-op (log `deferred`) |
| **ModuleAssemblerAgent** | Copy `CuratedModule` to `ctx.learning_module` (or return module unchanged); no `content_blocks` yet |
| **RelevanceAgent** | Not used in `curate` step (relevance already in DB) |

### 5.4 `step_curate` change

- Replace direct `curate_all` loop body with: for each unit → build context → `orchestrator.curate_unit(ctx)` → collect `CuratedModule`.
- `curate_all` may delegate to orchestrator internally to avoid duplication.
- Feature flag: `USE_CURATION_ORCHESTRATOR=true` (default **true** when `PIPELINE_VERSION>=2`) for safe rollback to direct `curate_unit` if needed.

### 5.5 Files touched (implementation plan scope)

- `src/ibrary/pipeline/subagents.py` — implement `TextCuratorAgent`; passthrough assembler
- `src/ibrary/curation/curation_service.py` — optional thin wrapper used by TextCurator
- `src/ibrary/curation/prompts.py` — student self-study templates (`PROMPT_VERSION_TAG` bump)
- `scripts/run_pipeline.py` — wire orchestrator in `step_curate` for v2
- `src/ibrary/judging/` — rubric hints for self-study readability (list density, no teacher-dependent steps)

---

## 6. Prompt versioning

- Tag: `v2.0-student-self-study` (or similar) in `PROMPT_VERSION_TAG`.
- Hash-based `prompt_version` on each module for A/B vs legacy.
- Re-curate units after deploy; judge scores not comparable across prompt versions.

---

## 7. Re-curation and resume

- Existing `curated_content.json` resume behavior unchanged.
- To refresh style: `--curate-unit <id>` after removing that unit from JSON, or `--replace-curated` for full replace.
- No delete of `chunk_relevance` required.

---

## 8. Success criteria

1. Sample unit `bio_sss1_theme1_topic1_content0` has **no** teacher-setup sections in `curated_content`.
2. Body is mostly prose; no section with >6 consecutive bullet items except allowed mnemonics.
3. Inline “Check yourself” + final `## Review questions` present.
4. `student_activities` has 2–4 items; `teacher_activities` has ≤3 or empty.
5. No `## Accessibility notes` in `curated_content`; checklist remains in JSON.
6. `step_curate --pipeline-version 2` logs orchestrator stages (`text_curator` → `media_linker`/`formula` skip → `module_assembler`).
7. Judge pass/fail still runs; add readability checks without breaking existing API.

---

## 9. Out of scope (Phase 2)

- MediaLinker S3 / OpenStax resolution
- FormulaAgent LaTeX catalog
- `content_blocks` / DynamoDB `assets` publish
- OpenAI Agents SDK manager path (experimental; not batch default)

---

## 10. Decisions log

| Decision | Choice |
|----------|--------|
| Primary reader | Students; reviewers use same `curated_content` |
| Practice | Inline checks + end review + `student_activities` tab |
| Teacher field | Minimal JSON for reviewers; may be empty |
| Accessibility notes in body | **Removed** |
| Orchestrator | **Wire now** with TextCurator real; media/formula deferred |
| Implementation order | Prompts + orchestrator wiring first; assets later |
