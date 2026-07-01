# Manual setup — Pipeline v2

One-time and per-machine steps before running **Pipeline v2** (`PIPELINE_VERSION=2`).

## 1. Environment file

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Value |
|----------|--------|
| `OPENAI_API_KEY` | Your OpenAI key |
| `PIPELINE_VERSION` | `2` |
| `ALIGNMENT_TOP_K` | `10` |
| `OPENAI_RELEVANCE_MODEL` | `gpt-4o-mini` |
| `AWS_DEFAULT_REGION` | `us-east-2` (or your AWS region) |

Optional judge / prompt lab:

| Variable | Default |
|----------|---------|
| `JUDGE_PASS_THRESHOLD` | `7.0` |
| `PROMPT_IMPROVEMENT_MIN_DELTA` | `0.25` |

## 2. Infrastructure

```bash
make up
# or: docker compose up -d
```

## 3. Python dependencies

```bash
uv sync --extra dev
uv pip install -e .
```

## 4. Database migration (chunk_relevance)

```bash
alembic upgrade head
```

Creates `ibrary.chunk_relevance` (revision `006`).

## 5. DynamoDB tables (publish step)

```bash
python scripts/create_dynamodb_tables.py
```

## 6. Textbook PDF

```bash
make download-textbook
```

Expected path: `data/docs/extracted_source_content/biology/Biology2e-WEB.pdf`

## 7. Hybrid embeddings + chapter-scoped alignment

After upgrading, set in `.env` (defaults in `.env.example`):

```bash
EMBEDDING_BODY_MAX_CHARS=2000
ALIGNMENT_CHAPTER_FILTER=true
ALIGNMENT_CHAPTER_FILTER_FALLBACK=true
```

Re-run align (embeds all chunks under a new `model_version` key such as `text-embedding-3-small:body2000`):

```bash
python scripts/run_pipeline.py --steps align
```

Re-validate curriculum if `curriculum_validated.json` lacks `textbook_chapters` on units:

```bash
python scripts/run_pipeline.py --steps validate,align
```

## 8. Run v2 pipeline

**Setup only** (extract → validate → align → filter_relevance):

```bash
python scripts/run_pipeline.py --pipeline-version 2
```

**Full** (through publish):

```bash
python scripts/run_pipeline.py --full --pipeline-version 2
```

**Resume** after alignment:

```bash
python scripts/run_pipeline.py --pipeline-version 2 --resume-from filter_relevance
```

**Single unit curation** (after filter_relevance):

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps curate --curate-unit bio_sss1_theme1_topic1_content0
```

## 9. Verify outputs

| Artifact | Path |
|----------|------|
| Alignment | `data/docs/extracted_source_content/biology/curriculum_textbook_alignment.json` |
| Relevance | `data/docs/extracted_source_content/biology/chunk_relevance.json` |
| Curated modules | `data/docs/extracted_source_content/biology/curated_content.json` |
| Judge report | `data/docs/extracted_source_content/biology/udl_subtopic_evaluation.json` |

## Cost notes

- **filter_relevance**: one LLM call per (unit × top-10 chunk). Budget ~N_units × 10 calls.
- **curate**: uses excerpts only in v2 (smaller context than full chunks).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `relation "chunk_relevance" does not exist` | Run `alembic upgrade head` |
| `no_alignment_file` | Run `--steps align` first |
| `no_relevant_excerpts` for a unit | Re-run `filter_relevance`; check `chunk_relevance` rows in Postgres |
| Empty `OPENAI_API_KEY` | Set in `.env` and restart shell |
