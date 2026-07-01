# Pipeline v2 — implementation checklist

**Spec:** [2026-05-16-biology-pipeline-v2-design.md](../specs/2026-05-16-biology-pipeline-v2-design.md)  
**Manual setup:** [MANUAL_SETUP_V2.md](../../MANUAL_SETUP_V2.md)  
**Review checklist:** [REVIEW_PIPELINE_V2.md](../../REVIEW_PIPELINE_V2.md)

## Target DAG

```
extract → validate → align (top_k=10)
       → filter_relevance   [LLM per unit×chunk]
       → curate             [excerpts → module; orchestrator stubs for media/formulas]
       → judge              [ibrary.judging]
       → publish
```

---

## Phase 0 — Config & schema ✅

- [x] `config.py`: `PIPELINE_VERSION`, `ALIGNMENT_TOP_K=10`, `OPENAI_RELEVANCE_MODEL`, judge thresholds
- [x] `.env.example` v2 variables
- [x] Alembic `006_add_chunk_relevance.py`
- [x] ORM `ChunkRelevance` in `models.py`
- [x] `docs/MANUAL_SETUP_V2.md`

## Phase 1 — Relevance filter ✅

- [x] `src/ibrary/relevance/` (`scorer`, `filter_runner`, `store`, `context`)
- [x] `run_pipeline.py`: `filter_relevance` step, `--pipeline-version 2`
- [x] `curation_service.curate_all`: excerpt path when v2
- [ ] Unit tests for scorer JSON parsing (optional)

## Phase 2 — Curation v2 (partial)

- [x] Native DAG orchestrator (`src/ibrary/pipeline/`)
- [ ] **TextCuratorAgent**: real prompts + `content_blocks` (replace stub)
- [ ] **MediaLinkerAgent**: textbook S3 → OpenStax web fallback
- [ ] **FormulaAgent**: LaTeX / `\ce{}` → `formulas[]`
- [ ] **ModuleAssemblerAgent**: `LearningModule` v1 JSON schema
- [ ] Wire `PipelineOrchestrator` into `step_curate` for v2

## Phase 3 — Judging ✅ (module exists)

- [x] `ibrary.judging` with UDL v3 checkpoints, correctness + clarity
- [x] `run_pipeline.py` uses `evaluate_subtopics`
- [ ] Persist judge scores to Postgres (optional)

## Phase 4 — Prompt improvement (partial)

- [x] `ibrary.prompt_improvement.compare`
- [ ] `scripts/run_prompt_lab.py` CLI
- [ ] Golden set: `bio_sss1_theme1_topic1_content0/1/2`

## Phase 5 — Branch hygiene

- [x] Remove duplicate `docs/BIOLOGY_PIPELINE_ORCHESTRATOR.md` (use `docs/PIPELINE_ORCHESTRATOR.md`)
- [ ] Keep `src/sourceContentProcessor/` as legacy (tracked); **no new code there**
- [ ] Add CI job for `filter_relevance` dry-run on 1 unit (optional)

---

## Commands by milestone

| Milestone | Command |
|-----------|---------|
| Migrate DB | `alembic upgrade head` |
| v2 setup | `python scripts/run_pipeline.py --pipeline-version 2` |
| v2 full | `python scripts/run_pipeline.py --full --pipeline-version 2` |
| Relevance only | `python scripts/run_pipeline.py --pipeline-version 2 --steps filter_relevance` |
| Curate one unit | `python scripts/run_pipeline.py --pipeline-version 2 --steps curate --curate-unit bio_sss1_theme1_topic1_content0` |

---

## Implementation order (remaining work)

1. **TextCuratorAgent** — port `curation_service` prompt to block-based output; emit image/formula placeholders.
2. **MediaLinkerAgent** — resolve placeholders via `textbook_image_manifest.json` + OpenStax CDN.
3. **FormulaAgent** — extract/normalize LaTeX from placeholders.
4. **ModuleAssemblerAgent** — merge into `LearningModule` v1; write `curated_content.json` + Postgres.
5. **run_prompt_lab.py** — compare two prompt versions on golden units using `prompt_improvement.compare`.
6. Tests + notebook update for v2 steps.
