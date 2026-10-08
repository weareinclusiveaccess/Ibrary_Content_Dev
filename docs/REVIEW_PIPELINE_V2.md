# Review guide — Pipeline v2 implementation

Use this checklist to verify the implementation **without trusting the summary alone**. Work top to bottom; each section builds on the previous one.

**Related docs**

- Setup: [MANUAL_SETUP_V2.md](MANUAL_SETUP_V2.md)
- Spec: [superpowers/specs/2026-05-16-biology-pipeline-v2-design.md](superpowers/specs/2026-05-16-biology-pipeline-v2-design.md)
- Plan: [superpowers/plans/2026-05-16-pipeline-v2-implementation.md](superpowers/plans/2026-05-16-pipeline-v2-implementation.md)

**Estimated time:** 45–90 minutes (longer if you run full `extract` on the 380 MB PDF).

---

## Part A — Static review (no API calls)

### Step 1: Confirm files exist

| Area | Paths to open |
|------|----------------|
| Relevance | `src/ibrary/relevance/` (`scorer.py`, `filter_runner.py`, `store.py`, `context.py`) |
| Config | `src/ibrary/config.py`, `.env.example` |
| DB | `alembic/versions/006_add_chunk_relevance.py`, `ChunkRelevance` in `src/ibrary/models.py` |
| CLI | `scripts/run_pipeline.py`, `scripts/run_prompt_lab.py` |
| Judging | `src/ibrary/judging/` |
| Orchestrator (stubs) | `src/ibrary/pipeline/subagents.py`, `orchestrator.py` |
| Docs | `docs/MANUAL_SETUP_V2.md`, this file |

**Pass if:** all paths exist; duplicate `docs/BIOLOGY_PIPELINE_ORCHESTRATOR.md` is **gone**.

---

### Step 2: Config defaults

Open `src/ibrary/config.py` and confirm:

| Setting | Expected default |
|---------|------------------|
| `PIPELINE_VERSION` | `1` (overridden by env / CLI) |
| `ALIGNMENT_TOP_K` | `10` |
| `OPENAI_RELEVANCE_MODEL` | `gpt-4o-mini` |
| `JUDGE_PASS_THRESHOLD` | `7.0` |
| `AWS_DEFAULT_REGION` | `us-east-2` |

Open `.env.example` — v2 block should include `PIPELINE_VERSION=2`, `ALIGNMENT_TOP_K=10`, `OPENAI_RELEVANCE_MODEL`.

**Pass if:** values match; your local `.env` has `OPENAI_API_KEY` set (do not commit `.env`).

---

### Step 3: Pipeline step wiring

Open `scripts/run_pipeline.py`:

1. `SETUP_STEPS_V2` includes `filter_relevance` after `align`.
2. `--pipeline-version` choices are `1` and `2`.
3. `step_filter_relevance` calls `filter_relevance_for_units` + `save_relevance_json`.
4. `step_judge` uses `results`, not `scores` (bug fix).

**Pass if:** v2 default setup runs four steps when `--pipeline-version 2` and no `--steps`.

---

### Step 4: Curation v2 branch

Open `src/ibrary/curation/curation_service.py`, function `curate_all`:

- When `PIPELINE_VERSION` (env) `>= 2`, it calls `build_curation_excerpts(unit_id)` instead of full chunk bodies.
- Skips units with no relevant excerpts (`no_relevant_excerpts` log).

Open `src/ibrary/relevance/context.py` — excerpts come from DB rows where `relevant = true`.

**Pass if:** v2 path is clearly separate from v1 full-chunk path.

---

### Step 5: What is still a stub (expected)

Open `src/ibrary/pipeline/subagents.py`:

- `RelevanceAgent`, `TextCuratorAgent`, `MediaLinkerAgent`, `FormulaAgent`, `ModuleAssemblerAgent` log `*_status = stub`.
- **Curation today** still goes through `curation_service`, not the orchestrator DAG.

**Pass if:** you understand orchestrator agents are **not** production-ready yet; relevance filter **is**.

---

## Part B — Environment & database (local machine)

### Step 6: Prerequisites

From repo root:

```bash
make up
uv sync --extra dev
uv pip install -e .
```

**Pass if:** Postgres and DynamoDB local containers are healthy.

---

### Step 7: Migration

```bash
alembic current
alembic upgrade head
alembic current
```

**Pass if:** current revision is `006` (or head includes `006_add_chunk_relevance`).

Optional — inspect table in Postgres:

```bash
docker compose exec postgres psql -U ibrary -d ibrary -c "\d ibrary.chunk_relevance"
```

**Pass if:** columns include `curriculum_unit_id`, `chunk_id`, `relevant`, `excerpt`, `embedding_score`, unique constraint on `(curriculum_unit_id, chunk_id)`.

---

### Step 8: Import smoke test (no OpenAI)

```bash
python -c "
from ibrary.relevance import filter_relevance_for_units, build_curation_excerpts
from ibrary.judging import evaluate_subtopics
from ibrary.config import ALIGNMENT_TOP_K, PIPELINE_VERSION
print('ALIGNMENT_TOP_K', ALIGNMENT_TOP_K)
print('PIPELINE_VERSION', PIPELINE_VERSION)
print('imports ok')
"
```

**Pass if:** no import errors.

---

## Part C — Runtime review (use existing data if possible)

Skip **extract** if you already have chunks + alignment from a prior run.

### Step 9: Alignment shape (top-10)

If `data/docs/extracted_source_content/biology/curriculum_textbook_alignment.json` exists, pick one unit id, e.g. `bio_sss1_theme1_topic1_content0`:

```bash
python -c "
import json
from pathlib import Path
p = Path('data/docs/extracted_source_content/biology/curriculum_textbook_alignment.json')
a = json.loads(p.read_text())
uid = 'bio_sss1_theme1_topic1_content0'
entry = a.get(uid)
matches = entry if isinstance(entry, list) else entry.get('matches', [])
print('match_count', len(matches))
print('first_chunk', matches[0]['chunk_id'] if matches else 'none')
"
```

**Pass if:** up to **10** matches per unit (after re-align with `ALIGNMENT_TOP_K=10`). If you still see only 2, re-run:

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps align
```

---

### Step 10: filter_relevance on ONE unit (controlled cost)

Temporarily limit work by editing is **not** required — run full filter only if budget allows. For a **minimal** review, use Python to score one pair:

```bash
python -c "
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
os.environ.setdefault('PIPELINE_VERSION', '2')

from ibrary.curriculum.validator import validate_curriculum
from ibrary.relevance.scorer import score_chunk_relevance
import json

validated = validate_curriculum('data/docs/extracted_source_content/biology/biology_curriculum_structured.json')
unit = next(u for u in validated.units if u.curriculum_unit_id == 'bio_sss1_theme1_topic1_content0')
align = json.loads(Path('data/docs/extracted_source_content/biology/curriculum_textbook_alignment.json').read_text())
entry = align[unit.curriculum_unit_id]
matches = entry if isinstance(entry, list) else entry['matches']
m = matches[0]
from sqlalchemy import text as sa_text
from ibrary.db import get_session
from ibrary.config import POSTGRES_SCHEMA
s = get_session()
row = s.execute(sa_text(f'SELECT title, content FROM {POSTGRES_SCHEMA}.textbook_chunks WHERE chunk_id = :c'), {'c': m['chunk_id']}).fetchone()
s.close()
r = score_chunk_relevance(unit, chunk_id=m['chunk_id'], chunk_title=row.title, chunk_content=row.content, embedding_score=m['score'])
print(r.model_dump_json(indent=2))
"
```

**Review the output:**

| Field | What to check |
|-------|----------------|
| `relevant` | Makes sense for the subtopic |
| `excerpt` | Subset of chunk text, not hallucinated |
| `confidence` | 1–10 scale |
| `rationale` | Short, grounded |

**Pass if:** JSON parses; excerpt (when relevant) is clearly from the chunk.

---

### Step 11: Full filter_relevance step

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps filter_relevance
```

**Pass if:**

1. Log lines `relevance_scored` per chunk.
2. File created: `data/docs/extracted_source_content/biology/chunk_relevance.json`.
3. Postgres has rows:

```bash
docker compose exec postgres psql -U ibrary -d ibrary -c "
  SELECT curriculum_unit_id, chunk_id, relevant, LEFT(excerpt, 80) AS excerpt_preview
  FROM ibrary.chunk_relevance
  WHERE curriculum_unit_id = 'bio_sss1_theme1_topic1_content0'
  LIMIT 5;
"
```

**Pass if:** at least some rows have `relevant = t` and non-null `excerpt`.

---

### Step 12: Curate ONE unit (v2 excerpts)

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps curate --curate-unit bio_sss1_theme1_topic1_content0
```

**Pass if:**

- No `no_relevant_excerpts` for that unit (if yes, revisit Step 11).
- `curated_content.json` contains an entry for that `curriculum_unit_id`.
- Module has `curated_content`, `learning_objectives`, `prompt_version`.
- `prompt_version` starts with `v2.0-student-self-study`.
- Logs show orchestrator: `text_curator` → `media_linker`/`formula` skip → `module_assembler`.

**Spot-check (student self-study):**

- `curated_content` is mostly prose; no `Teachers:` or `## Accessibility notes`.
- Inline **Check yourself** prompts and final **## Review questions** present.
- `teacher_activities` has at most 3 items (may be empty).

---

### Step 13: Judge ONE module

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps judge --curate-unit bio_sss1_theme1_topic1_content0
```

(If judge step ignores `--curate-unit`, judge after Step 12 only — it loads all modules in `curated_content.json`.)

**Pass if:**

- `udl_subtopic_evaluation.json` updated.
- Each result has `overall_score`, `correctness_score`, `clarity_score`, `passed`, `checkpoint_scores`.

Open `src/ibrary/judging/rubric.py` — pick one `checkpoint_id` from the report and confirm `principle` / `measures` are populated (enrichment).

---

### Step 14: Prompt lab (optional)

Requires two curated JSON files (baseline vs candidate). If you only have one file, skip.

```bash
python scripts/run_prompt_lab.py --baseline data/docs/extracted_source_content/biology/curated_content.json --candidate data/docs/extracted_source_content/biology/curated_content.json
```

**Pass if:** script runs and prints `PromptImprovementReport` JSON (scores will be identical if same file — that's OK for a smoke test).

---

## Part D — Regression & version comparison

### Step 15: v1 vs v2 behavior

| Check | v1 (`--pipeline-version 1`) | v2 (`--pipeline-version 2`) |
|-------|-----------------------------|-----------------------------|
| Default setup steps | 3 (no filter) | 4 (+ filter_relevance) |
| Curation input | Full chunk bodies from alignment | Excerpts from `chunk_relevance` |
| Requires `filter_relevance` first | No | Yes, for excerpt path |

**Pass if:** v1 still runs without migration errors; v2 fails gracefully with clear logs if relevance table is empty.

---

### Step 16: CLI help

```bash
python scripts/run_pipeline.py --help
```

**Pass if:** `--pipeline-version` documented; step list mentally matches Part A Step 3.

---

## Part E — Sign-off checklist

Copy into your PR / notes:

```
[ ] Config + .env.example reviewed (Part A 2)
[ ] Migration 006 applied; chunk_relevance table exists (Part B 7)
[ ] Imports smoke test passed (Part B 8)
[ ] Alignment has up to 10 matches per unit (Part C 9)
[ ] Single-chunk relevance call sensible (Part C 10)
[ ] filter_relevance JSON + DB rows (Part C 11)
[ ] Single-unit v2 curation produced module (Part C 12)
[ ] Judge report generated with enriched checkpoints (Part C 13)
[ ] Understood pipeline sub-agents are stubs (Part A 5)
[ ] Cost acceptable for full curriculum filter_relevance run
```

---

## Known gaps (do not fail review for these)

| Item | Status |
|------|--------|
| `TextCuratorAgent` / media / formulas | Stub |
| `LearningModule` v1 (`content_blocks`, `assets[]`) | Not implemented |
| Orchestrator not wired into `step_curate` | By design for this phase |
| Automated tests for relevance scorer | Not added |

---

## If something fails

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `relation "chunk_relevance" does not exist` | Migration not run | `alembic upgrade head` |
| `no_alignment_file` | Missing align step | `--steps align` |
| `no_relevant_excerpts` | Filter not run or all irrelevant | Re-run Step 11; inspect DB |
| OpenAI 401 | Bad/missing API key | Fix `.env` |
| Only 2 alignment matches | Old align with `TOP_K=2` | Re-align with `ALIGNMENT_TOP_K=10` |
| Import errors for `ibrary` | Package not installed | `uv pip install -e .` |

---

## Quick “minimum review” (15 minutes)

If time is limited:

1. Part A Steps 1–5 (static)
2. Part B Steps 7–8 (migration + import)
3. Part C Step 10 (one LLM relevance call)
4. Part C Step 12 (one unit curate)
5. Part E checklist

This validates the **highest-risk new surface**: relevance filter → excerpt curation → judge.
