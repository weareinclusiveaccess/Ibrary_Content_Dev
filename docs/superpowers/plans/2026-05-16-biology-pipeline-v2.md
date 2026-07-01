# Biology Pipeline v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After pgvector top-10 retrieval per curriculum unit, run a relevance agent on each chunk, pass **excerpts only** into curation, and optionally add global chunk enrichment, prompt lab, and layered judges.

**Architecture:** Alignment stays in `ibrary.alignment` (cosine search only). New `ibrary.relevance` implements `filter_relevance`. Curation reads `chunk_relevance` excerpts—not full chunks from alignment IDs. Optional `ibrary.enrichment` for global repair/formulas/images. v1 remains default until `--pipeline-version 2`.

**Tech Stack:** Python 3.10+, SQLAlchemy, Alembic, pgvector, OpenAI API, pytest, boto3 (optional AWS).

**Spec:** `docs/superpowers/specs/2026-05-16-biology-pipeline-v2-design.md`

---

## Corrected flow (read this first)

```
extract → validate → align (top 10 pgvector)
       → filter_relevance (LLM × up to 10 chunks per unit)
       → curate (excerpts only)
       → judge_all → publish

Optional: enrich_global before validate (repair / formulas / images)
```

**Not in scope:** Pretending curriculum JSON “links” subtopics to textbook sections. The only retrieval link is embedding similarity.

---

## File map

| Path | Responsibility |
|------|----------------|
| `src/ibrary/relevance/__init__.py` | Package exports |
| `src/ibrary/relevance/schemas.py` | `ChunkRelevanceResult`, `UnitRelevanceReport` |
| `src/ibrary/relevance/scorer.py` | `score_chunk_relevance(unit, chunk_row, embedding_score)` |
| `src/ibrary/relevance/filter_runner.py` | `filter_relevance_for_units(units, alignment) -> dict` |
| `src/ibrary/relevance/store.py` | Postgres upsert + JSON file `chunk_relevance.json` |
| `src/ibrary/relevance/context.py` | `build_curation_excerpts(unit_id) -> list[dict]` for curation |
| `src/ibrary/curation/curation_service.py` | Branch on `pipeline_version >= 2` |
| `src/ibrary/config.py` | `ALIGNMENT_TOP_K=10`, `OPENAI_RELEVANCE_MODEL` |
| `alembic/versions/006_chunk_relevance.py` | `chunk_relevance` table |
| `scripts/run_pipeline.py` | `step_filter_relevance`, v2 step list |
| `src/ibrary/enrichment/*` | **Optional** Phase 5 only |
| `scripts/run_prompt_lab.py` | Golden 3 units |
| `tests/relevance/test_*.py` | Unit tests |

---

## Phase 0 — Foundation

**Estimated:** 0.5–1 day

### Task 0.1: Config and align default k=10

**Files:** `src/ibrary/config.py`, `.env.example`

- [ ] Change default: `ALIGNMENT_TOP_K: int = int(os.getenv("ALIGNMENT_TOP_K", "10"))`
- [ ] Add: `OPENAI_RELEVANCE_MODEL: str = os.getenv("OPENAI_RELEVANCE_MODEL", "gpt-4o-mini")`
- [ ] Add: `PIPELINE_VERSION: int = int(os.getenv("PIPELINE_VERSION", "1"))`
- [ ] Update `.env.example` with comments explaining top-10 + relevance model
- [ ] Commit: `chore: alignment top-10 and relevance model config`

### Task 0.2: `chunk_relevance` migration

**Files:** `alembic/versions/006_chunk_relevance.py`, `src/ibrary/models.py`

- [ ] Add model:

```python
class ChunkRelevance(Base):
    __tablename__ = "chunk_relevance"
    __table_args__ = (
        UniqueConstraint("curriculum_unit_id", "chunk_id", name="uq_unit_chunk_relevance"),
        _SCHEMA,
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    curriculum_unit_id = Column(String, nullable=False, index=True)
    chunk_id = Column(String, ForeignKey(f"{POSTGRES_SCHEMA}.textbook_chunks.chunk_id"), nullable=False)
    relevant = Column(Boolean, nullable=False)
    excerpt = Column(Text, nullable=True)
    embedding_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    rationale = Column(Text, nullable=True)
    agent_version = Column(String, nullable=True)
    content_hash = Column(String(64), nullable=True)  # chunk content hash at scoring time
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
```

- [ ] Run: `uv run alembic upgrade head`
- [ ] Commit: `feat(db): chunk_relevance table`

### Task 0.3: pytest bootstrap

**Files:** `tests/conftest.py`, `tests/relevance/__init__.py`

- [ ] Add fixtures: `sample_unit`, `sample_chunk_row`, `mock_openai`
- [ ] Commit: `test: bootstrap relevance tests`

---

## Phase 1 — `filter_relevance` (core)

**Estimated:** 2–3 days | **Priority:** highest

### Task 1.1: Relevance schemas

**Files:** `src/ibrary/relevance/schemas.py`

- [ ] Define:

```python
class ChunkRelevanceResult(BaseModel):
    chunk_id: str
    relevant: bool
    excerpt: str | None = None
    rationale: str = ""
    confidence: float | None = None
    embedding_score: float | None = None

class UnitRelevanceReport(BaseModel):
    curriculum_unit_id: str
    results: list[ChunkRelevanceResult]
```

- [ ] Commit: `feat(relevance): schemas`

### Task 1.2: RelevanceScorer LLM

**Files:** `src/ibrary/relevance/scorer.py`, `tests/relevance/test_scorer.py`

- [ ] **Test (failing):** relevant chunk returns `relevant=True` and non-empty `excerpt`

- [ ] Implement `score_chunk_relevance(unit: CurriculumUnit, chunk: dict, embedding_score: float) -> ChunkRelevanceResult`:

  - System prompt: you are filtering textbook excerpts for a **specific subtopic**; do not invent facts; if not relevant return `relevant: false` with empty excerpt.
  - User prompt includes: subtopic (`content_text`), topic title, objectives, chunk title, **full content** (or `repaired_content` if key present), embedding score as hint only.
  - JSON response keys: `relevant`, `excerpt`, `rationale`, `confidence`
  - Use `OPENAI_RELEVANCE_MODEL`, 3 retries (copy pattern from `curation_service._call_llm`)

- [ ] Run: `uv run pytest tests/relevance/test_scorer.py -v` — PASS

- [ ] Commit: `feat(relevance): RelevanceScorer agent`

### Task 1.3: Filter runner (per unit × top-10)

**Files:** `src/ibrary/relevance/filter_runner.py`, `tests/relevance/test_filter_runner.py`

- [ ] Implement `filter_relevance_for_units(units, alignment: dict, *, max_chunks: int | None = None) -> dict[str, UnitRelevanceReport]`:

```python
for unit in units:
    matches = alignment_matches(alignment, unit.curriculum_unit_id)  # reuse from curation
    chunk_ids = [m["chunk_id"] for m in matches[: max_chunks or ALIGNMENT_TOP_K]]
    for cid in chunk_ids:
        row = fetch_chunk_from_postgres(cid)  # content, title, content_hash, repaired_content
        score = match_score_for(cid, matches)
        result = score_chunk_relevance(unit, row, score)
        upsert_chunk_relevance(unit.curriculum_unit_id, result, row["content_hash"])
```

- [ ] **Do not skip** `needs_review` matches — agent decides relevance

- [ ] Test with mocked scorer: 10 chunk IDs in, only 3 `relevant=True` out

- [ ] Commit: `feat(relevance): filter_runner for top-k chunks`

### Task 1.4: Persist + JSON export

**Files:** `src/ibrary/relevance/store.py`

- [ ] `upsert_chunk_relevance(unit_id, result, content_hash)` — Postgres upsert on `(unit_id, chunk_id)`
- [ ] `save_relevance_json(reports, output_dir)` → `chunk_relevance.json`
- [ ] `load_relevance_for_unit(unit_id) -> list[ChunkRelevanceResult]`
- [ ] Commit: `feat(relevance): store layer`

---

## Phase 2 — Wire curation to excerpts

**Estimated:** 1–2 days

### Task 2.1: Context builder

**Files:** `src/ibrary/relevance/context.py`, `tests/relevance/test_context.py`

- [ ] Implement `build_curation_excerpts(unit_id: str) -> list[dict]`:

```python
# Returns list of:
# {"chunk_id", "title", "content": excerpt, "alignment_score": embedding_score}
# Only rows where relevant=True and excerpt stripped non-empty
```

- [ ] Test: unit with 0 relevant → empty list

- [ ] Commit: `feat(relevance): curation excerpt builder`

### Task 2.2: Integrate `curation_service`

**Files:** `src/ibrary/curation/curation_service.py`

- [ ] Add `pipeline_version: int = 1` to `curate_unit` / `curate_all`

- [ ] When `pipeline_version >= 2`:

```python
excerpt_chunks = build_curation_excerpts(unit.curriculum_unit_id)
if not excerpt_chunks:
    logger.warning("no_relevant_excerpts", unit_id=unit.curriculum_unit_id)
    return None  # or Needs Review stub — pick one and document
context = _truncate_context(excerpt_chunks, MAX_CONTEXT_TOKENS)
```

- [ ] Remove v2 path that passes all aligned `chunk_ids` with full body text

- [ ] `textbook_chunk_refs` = chunk_ids from excerpt list only

- [ ] Commit: `feat(curation): use relevance excerpts in v2`

---

## Phase 2b — Curation: TextCurator + MediaLinker (image source **B**)

**Estimated:** 3–4 days | **Depends on:** Phase 2 | **Spec:** §6

### Task 2b.1: `LearningModule` schemas

**Files:** `src/ibrary/curation/module_schema.py`

- [ ] Pydantic models: `ContentBlock`, `MediaAsset`, `LearningModule` (`format_version`, `metadata`, `assets`, `content_blocks`)
- [ ] `source` enum: `textbook` | `openstax_web`
- [ ] Commit: `feat(curation): LearningModule v1 schemas`

### Task 2b.2: TextCurator prompts + service

**Files:** `src/ibrary/curation/text_curator.py`, `src/ibrary/curation/prompts.py`

- [ ] New prompt returns `content_blocks` + `image_placeholders` (no binaries)
- [ ] `curate_text(unit, excerpt_chunks) -> TextCurationDraft`
- [ ] Commit: `feat(curation): TextCurator agent`

### Task 2b.3: OpenStax web fetcher

**Files:** `src/ibrary/curation/openstax_fetcher.py`, `tests/curation/test_openstax_fetcher.py`

- [ ] `fetch_page_html(url) -> str` with timeout + S3/ disk cache
- [ ] `extract_figure_candidates(html) -> list[{src, caption, alt}]`
- [ ] `pick_and_download(url, hints) -> bytes` — match caption/alt to `search_hints`
- [ ] `upload_curated_asset(unit_id, asset_id, bytes, ext) -> s3_url`
- [ ] Test with cached HTML fixture (no network in CI)
- [ ] Commit: `feat(curation): OpenStax web image fetcher`

### Task 2b.4: MediaLinker (textbook → OpenStax → fallback)

**Files:** `src/ibrary/curation/media_linker.py`, `tests/curation/test_media_linker.py`

- [ ] `link_media(unit, draft, chunk_ids, openstax_urls) -> LearningModule`:

```python
for placeholder in draft.image_placeholders:
    asset = try_textbook_match(placeholder, chunk_ids)  # S3 copy
    if asset is None:
        asset = try_openstax_web(placeholder, openstax_urls)  # fetcher
    if asset is None:
        patch_block_to_paragraph(placeholder)
    else:
        patch_block_to_image(placeholder, asset.asset_id)
```

- [ ] Write `media_resolution.json` per unit
- [ ] Commit: `feat(curation): MediaLinker with OpenStax fallback (B)`

### Task 2b.5: ModuleAssembler + DB + publish

**Files:** `src/ibrary/curation/assembler.py`, `src/ibrary/models.py`, `src/ibrary/serving/dynamodb_writer.py`

- [ ] Migration: `curated_content.content_json` JSONB
- [ ] `assemble_module(draft, assets, blocks) -> LearningModule`; generate `curated_content_md` from blocks
- [ ] `publish_module`: add `content_blocks`, `assets` JSON strings to DynamoDB item
- [ ] Wire `curate_unit` v2: excerpts → TextCurator → MediaLinker → Assembler
- [ ] Commit: `feat(curation): assemble and publish LearningModule with images`

---

## Phase 2c — FormulaAgent + PipelineOrchestrator

**Estimated:** 2–3 days | **Depends on:** Phase 2b (schemas) | **Spec:** §6 formulas, §7

### Task 2c.1: Formula schemas + block types

**Files:** `src/ibrary/curation/module_schema.py`

- [ ] Add `FormulaAsset` (`formula_id`, `kind`, `latex`, `plain_text`, `spoken_text`, `source`, …)
- [ ] Add `formula` / `formula_placeholder` content block types
- [ ] Commit: `feat(curation): formula blocks in LearningModule`

### Task 2c.2: FormulaAgent

**Files:** `src/ibrary/curation/formula_agent.py`, `tests/curation/test_formula_agent.py`

- [ ] Implement resolution order: catalog → text LLM → vision → generate → plain fallback
- [ ] Chemistry: wrap with `\ce{...}`; math: validate with KaTeX parser
- [ ] `run(ctx) -> ctx` with `formulas[]` + block patches + `formula_resolution.json`
- [ ] Commit: `feat(curation): FormulaAgent`

### Task 2c.3: PipelineOrchestrator

**Files:** `src/ibrary/pipeline/orchestrator.py`, `src/ibrary/pipeline/context.py`

- [ ] `PipelineContext` dataclass: unit, excerpts, draft blocks, assets, formulas
- [ ] Register sub-agents; `curate_unit_v2(ctx)` runs Text → parallel(Media, Formula) → Assembler
- [ ] Replace monolithic `curate_unit` v2 path with orchestrator call
- [ ] Commit: `feat(pipeline): PipelineOrchestrator and sub-agents`

### Task 2c.4: Optional FormulaCatalogAgent (`enrich_global`)

**Files:** `src/ibrary/enrichment/formula_catalog.py`

- [ ] Chunk-level scan; populate `formulas` table (defer if MVP uses FormulaAgent-only at curate)
- [ ] Commit: `feat(enrichment): FormulaCatalogAgent` (optional)

---

## Phase 3 — Pipeline wiring

**Estimated:** 1 day

### Task 3.1: `run_pipeline.py`

**Files:** `scripts/run_pipeline.py`, `Makefile`

- [ ] Add steps:

```python
V2_SETUP_STEPS = ["extract", "validate", "align", "filter_relevance"]
V2_ALL_STEPS = V2_SETUP_STEPS + ["curate", "judge", "publish"]  # judge → judge_all later
```

- [ ] `step_filter_relevance(validated, alignment)`:

```python
from ibrary.relevance.filter_runner import filter_relevance_for_units
from ibrary.relevance.store import save_relevance_json
reports = filter_relevance_for_units(validated.units, alignment)
save_relevance_json(reports, OUTPUT_DIR)
```

- [ ] Pass `pipeline_version=args.pipeline_version` into `step_curate` / `curate_all`

- [ ] CLI: `--pipeline-version {1,2}`

- [ ] Makefile: `pipeline-v2`, `pipeline-v2-full`

- [ ] Commit: `feat(pipeline): filter_relevance step`

### Task 3.2: Manual smoke test

- [ ] `uv run python scripts/run_pipeline.py --pipeline-version 2 --steps align,filter_relevance --curate-unit bio_sss1_theme1_topic1_content0` (after extract/validate once)
- [ ] Inspect `chunk_relevance.json` — expect up to 10 rows per unit, some `relevant: false`
- [ ] Inspect curated module — textbook context should be short excerpts only

---

## Phase 4 — Judges + prompt lab

**Estimated:** 2–3 days

### Task 4.1: Relevance judge (audit)

**Files:** `src/ibrary/evaluation/relevance_judge.py`

- [ ] Sample N relevance rows; LLM scores whether excerpt actually supports subtopic
- [ ] Flag unit if audit score &lt; threshold

### Task 4.2: UDL judge (existing)

- [ ] Wire `judge` step unchanged for v2; later rename to `judge_all` when extraction judge added

### Task 4.3: Prompt lab

**Files:** `data/prompt_lab/golden_units.json`, `scripts/run_prompt_lab.py`

- [ ] Golden units: `content0`, `content1`, `content2` (theme 1 topic 1)
- [ ] Script runs: `align` → `filter_relevance` → `curate` (v2, golden only) → UDL judge → write `data/prompt_lab/eval/{prompt_version}/results.json`

- [ ] Commit: `feat: prompt lab on golden units`

---

## Phase 5 — Optional `enrich_global`

**Estimated:** 2–3 days | **Only after Phase 1–3 work**

### Task 5.1: Global enrichment (optional flag)

**Files:** `src/ibrary/enrichment/` (as in prior plan, trimmed)

- [ ] `ContentRepair` → `textbook_chunks.repaired_content`
- [ ] `ImageCatalog`, `FormulaExtractor` → S3 + tables
- [ ] CLI: `--enrich-global` or step only when `--pipeline-version 2 --steps enrich_global,…`
- [ ] Relevance scorer prefers `repaired_content` over `content` when loading chunk row

- [ ] Commit: `feat(enrichment): optional global enrich`

**Skip entirely if prioritizing relevance + curation only.**

---

## Phase 6 — Documentation

- [ ] Update `README.md`, `SETUP.md`, `.cursor/rules/project-setup.mdc` with corrected flow diagram
- [ ] Note: alignment embeds title/summary only; link to §2.1 future work
- [ ] Commit: `docs: pipeline v2 relevance-first flow`

---

## Dependency graph

```
Phase 0 → Phase 1 → Phase 2 → Phase 2b → Phase 3 → Phase 4
                              ↘
                        Phase 5 (optional)
Phase 3 → Phase 6
```

**Start here:** Phase 0 + Phase 1 (relevance). Phase 2b adds images (textbook + OpenStax web per decision **B**).

---

## Estimated effort (revised)

| Phase | Days |
|-------|------|
| 0 Foundation | 0.5–1 |
| 1 filter_relevance | 2–3 |
| 2 Curation wire (excerpts) | 1–2 |
| 2b TextCurator + MediaLinker + OpenStax (B) | 3–4 |
| 3 Pipeline | 1 |
| 4 Judges + prompt lab | 2–3 |
| 5 enrich_global (optional) | 2–3 |
| 6 Docs | 0.5 |
| **Total (without Phase 5)** | **~10–14 days** |

---

## Spec coverage

| Spec § | Phase |
|--------|-------|
| §2 Alignment reality | Phase 0.1 |
| §5 filter_relevance | Phase 1 |
| §5.6 Curation input | Phase 2 |
| §6 Curation + MediaLinker (B) | Phase 2b |
| §8 Prompt lab | Phase 4.3 |
| §9 Judges | Phase 4 |
| §6 enrich_global | Phase 5 (optional) |

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-05-16-biology-pipeline-v2.md`

**Recommended start:** Phase 0 + Task 1.2 (RelevanceScorer) — unblocks everything else.

**Options:**

1. **Subagent-driven** — one task per subagent with review between  
2. **Inline** — implement Phase 0–3 in this session  

Which approach do you want?
