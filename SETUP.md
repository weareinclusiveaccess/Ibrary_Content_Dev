# Project Setup Guide

This document outlines all the steps needed to set up the IBrary project for development, including the biology content pipeline.

## Complete Setup Checklist

### 1. Prerequisites

- [ ] **Python 3.10+** installed
- [ ] **UV package manager** installed
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- [ ] **Git** installed
- [ ] **Docker & Docker Compose** installed (required for PostgreSQL + DynamoDB Local)
- [ ] **Redis** (optional, for caching) — `brew install redis` or `apt-get install redis`

### 2. Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd Ibrary_Content_Dev

# Install dependencies
uv sync --extra dev

# Install package in editable mode
uv pip install -e .
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your configuration. Key variables:

**Required:**
- `OPENAI_API_KEY` — OpenAI API key (used for embeddings and curation)
- `DATABASE_URL` — PostgreSQL connection string (default: `postgresql://ibrary:ibrary_dev@localhost:5432/ibrary`)

**Pipeline Configuration:**
- `PIPELINE_VERSION` — `1` (legacy) or `2` (recommended: `filter_relevance`, excerpt-based curation, media linking; default in code may still be `1` — set `2` explicitly)
- `PIPELINE_SUBJECT_SLUG` — S3 path prefix for textbook images (default: `biology`)
- `OPENAI_MODEL` — LLM model for curation (default: `gpt-4-turbo-preview`)
- `OPENAI_EMBEDDING_MODEL` — Embedding model (default: `text-embedding-3-small`)
- `ALIGNMENT_TOP_K` — Number of textbook chunks to align per curriculum unit (default: `2`)
- `MAX_CONTEXT_TOKENS` — Max tokens for textbook context in curation prompt (default: `8000`)
- `ALIGNMENT_CONFIDENCE_THRESHOLD` — Minimum similarity score for alignment (default: `0.7`)
- `CURATE_CURRICULUM_ONLY_IF_NO_EXCERPTS` — When v2 relevance yields no excerpts, curate from curriculum only and flag `textbook_grounded: false` (default: `true`)

**Infrastructure:**
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — PostgreSQL credentials (defaults provided)
- `DYNAMODB_ENDPOINT_URL` — DynamoDB endpoint (default: `http://localhost:8000`)
- `S3_BUCKET` — S3 bucket for extracted textbook images (default: `ibrary-content`)
- `S3_ENDPOINT_URL` — S3 endpoint (leave empty for AWS, set for LocalStack)
- `AWS_PROFILE` — optional; use a named profile from `~/.aws/credentials` instead of keys in `.env` (recommended)

#### AWS access key and S3 bucket (textbook images)

The **extract** step uploads OpenStax figures to S3. You need an AWS account, an IAM access key (or SSO profile), and a bucket in the same region as `AWS_DEFAULT_REGION`.

**Option A — IAM access key (typical for local dev)**

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/).
2. Open **IAM** → **Users** → **Create user** (e.g. `ibrary-dev`).
3. **Permissions** — attach a policy scoped to your bucket, or for early dev only:
   - `AmazonS3FullAccess` (broad; tighten before production), or
   - Custom policy allowing `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, `s3:DeleteObject` on `arn:aws:s3:::ibrary-content` and `arn:aws:s3:::ibrary-content/*`.
4. Finish creating the user → open the user → **Security credentials** tab.
5. **Access keys** → **Create access key** → choose **Command Line Interface (CLI)** → confirm.
6. Copy **Access key ID** and **Secret access key** (secret is shown **once**; store it in a password manager).

**Store credentials (pick one)**

*Recommended — AWS CLI profile* (keeps secrets out of `.env`):

```ini
# Windows: %USERPROFILE%\.aws\credentials
# macOS/Linux: ~/.aws/credentials

[ibrary]
aws_access_key_id = AKIAxxxxxxxxxxxxxxxx
aws_secret_access_key = your-secret-key
```

```ini
# ~/.aws/config
[profile ibrary]
region = us-east-2
```

In `.env`:

```env
AWS_PROFILE=ibrary
AWS_DEFAULT_REGION=us-east-2
S3_BUCKET=ibrary-content
S3_ENDPOINT_URL=
# Do not set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY when using a profile
```

*Alternative — keys in `.env`* (works but easier to leak; never commit `.env`):

```env
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-2
S3_BUCKET=ibrary-content
S3_ENDPOINT_URL=
```

**Create the S3 bucket**

1. Console → **S3** → **Create bucket**.
2. **Bucket name:** `ibrary-content` (must match `S3_BUCKET` in `.env`).
3. **AWS Region:** same as `AWS_DEFAULT_REGION` (e.g. `us-east-2`). Region cannot be changed later; create a new bucket if you need another region.
4. Block public access: leave **on** (app uses private objects + signed URLs or backend access).
5. Default storage class: **S3 Standard** is fine for development (you can add lifecycle rules later).
6. Create bucket.

**Verify**

```bash
aws s3 ls s3://ibrary-content/biology/textbook-images/ --profile ibrary --summarize
# or, if using .env keys only:
aws s3 ls s3://ibrary-content/biology/textbook-images/ --summarize
```

**Upload images from the textbook**

```bash
python scripts/run_pipeline.py --pipeline-version 2 --steps extract
```

Look for log line `images_uploaded` (not `s3_upload_skipped`). Objects appear under `{PIPELINE_SUBJECT_SLUG}/textbook-images/` (default: `biology/textbook-images/`).

**DynamoDB Local + real S3**

`.env.example` sets `AWS_ACCESS_KEY_ID=local` for DynamoDB Local. Those values **override** an AWS profile. For real S3, remove or comment out `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` and use `AWS_PROFILE` instead. Keep `DYNAMODB_ENDPOINT_URL=http://localhost:8000` for local publish testing.

**Option B — SSO (organization account)**

If your org uses IAM Identity Center, run `aws configure sso`, create a profile, then set `AWS_PROFILE=that-profile` and `AWS_SDK_LOAD_CONFIG=1` in `.env`. No long-lived access keys required.

### 4. Docker Services

The project uses Docker Compose to run PostgreSQL (with pgvector) and DynamoDB Local. Ensure **Docker Desktop** is running.

**Windows (PowerShell), from project root:**
```powershell
.\scripts\compose.ps1 up -d
.\scripts\compose.ps1 ps
```

**Linux/macOS or Git Bash:**
```bash
make up
# or
docker compose up -d

make ps
# or: docker compose ps
```

Services:
- **PostgreSQL** (`pgvector/pgvector:pg16`) — port 5432, textbook chunks + embeddings
- **DynamoDB Local** (`amazon/dynamodb-local`) — port 8000, curated content serving

**Connect with pgAdmin:** Host `127.0.0.1`, Port `5432`, Database `ibrary`, Username `ibrary`, Password `ibrary_dev`. If it fails, set Connection → SSL mode to **Prefer** or **Disable**.

### 5. Database Setup

**Prerequisite:** Start the containers first (Step 4). PostgreSQL and DynamoDB Local must be running.

**Windows (PowerShell)** — run from the project root:

```powershell
# Run Alembic migrations (creates PostgreSQL tables)
uv run alembic upgrade head

# Create DynamoDB tables
uv run python scripts/create_dynamodb_tables.py
```

**Linux/macOS or Git Bash:**

```bash
make db-migrate
# or
uv run alembic upgrade head

make dynamodb-setup
# or
uv run python scripts/create_dynamodb_tables.py
```

The migration creates schema **`ibrary`** and tables: `textbooks`, `textbook_chunks`, `textbook_chunk_embeddings`, `textbook_images`, `curated_content`, `content_manual_quality_check`, and `content_udl_scores`. It also creates role **`der`** (password `der_ibrary_dev` until you change it) with usage/create on the schema and full privileges on existing objects. Set `POSTGRES_SCHEMA=ibrary` in `.env` (default in code) so the app uses the same schema. Ensure `DATABASE_URL` in `.env` matches your Postgres (default: `postgresql://ibrary:ibrary_dev@127.0.0.1:5432/ibrary`).

Alembic’s **`alembic_version`** table lives in the same **`ibrary`** schema as the app tables (configured in `alembic/env.py`). **If your database still has `public.alembic_version`** from an older setup, move it once so Alembic keeps tracking correctly:

```sql
CREATE SCHEMA IF NOT EXISTS ibrary;
CREATE TABLE ibrary.alembic_version (version_num VARCHAR(32) NOT NULL);
INSERT INTO ibrary.alembic_version SELECT version_num FROM public.alembic_version;
DROP TABLE public.alembic_version;
```

Skip the `CREATE TABLE` / `INSERT` if `ibrary.alembic_version` already exists with the right revision; only drop `public.alembic_version` when `ibrary` holds the same row.

**If you already ran an older migration** that created tables in `public` and revision `002`, reset the DB volume or drop those tables, then `alembic stamp base` (or delete the row from `alembic_version`) and run `uv run alembic upgrade head` again.

### 6. Download Textbook

The OpenStax Biology 2e PDF (~380 MB) is too large for GitHub and must be downloaded separately. It is freely available under a CC BY 4.0 license.

```bash
make download-textbook
# or
sh scripts/download_textbook.sh
```

This downloads `Biology2e-WEB.pdf` to `data/docs/extracted_source_content/biology/`. The script skips the download if the file already exists.

### 7. Spacy Model Setup

```bash
# Download the English model (required for text processing)
python -m spacy download en_core_web_sm
```

### 8. Source Documents

The following source documents must be present for the content pipeline:

| Document | Path | Tracked in git? |
|----------|------|-----------------|
| Biology 2e Textbook | `data/docs/extracted_source_content/biology/Biology2e-WEB.pdf` | No — download via `make download-textbook` |
| NERDC Curriculum | `data/docs/extracted_source_content/biology/OLD NERDC CURRICULUM SSCE BIOLOGY .pdf` | Yes |
| Curriculum JSON | `data/docs/extracted_source_content/biology/biology_curriculum_structured.json` | Yes |
| UDL Guidelines | `data/docs/udlg3-graphicorganizer-digital-numbers-a11y.pdf` | Yes |

### 9. Running the Content Pipeline

**Initial setup (default)** loads the textbook and curriculum into the database and builds embeddings + alignment. It does **not** run LLM curation—curation depends on your chosen model, prompts, and review workflow, so you run it when you are ready.

```bash
# Default: extract → validate → align (chunks in Postgres + curriculum_textbook_alignment.json)
make pipeline
# or
python scripts/run_pipeline.py

# Run only one step
python scripts/run_pipeline.py --steps extract

# Explicitly list steps (comma-separated, pipeline order)
python scripts/run_pipeline.py --steps extract,validate,align

# Resume within the default setup (extract | validate | align only)
python scripts/run_pipeline.py --resume-from validate
```

**Full pipeline** (curation through publish)—opt-in when prompts/models are configured:

```bash
make pipeline-full
# or
python scripts/run_pipeline.py --full

# Resume from curation or later (must use --full so those steps are in scope)
python scripts/run_pipeline.py --full --resume-from curate

# Skip the UDL judge when it is part of the selected steps
python scripts/run_pipeline.py --full --skip-judge
```

Makefile helpers for resume:

```bash
make pipeline-resume STEP=validate          # default setup only
make pipeline-full-resume STEP=curate       # full pipeline, start at curate
```

Pipeline steps (in order):

| Phase | Step | What it does |
|--------|------|----------------|
| Setup (default v1) | **extract** | Parse Biology2e-WEB.pdf, load chunks (+ images to S3 when configured) into PostgreSQL |
| | **validate** | Validate curriculum JSON (topics 1-6, SSS 1) |
| | **align** | Embed textbook chunks; align with curriculum via pgvector |
| Setup (v2 only) | **filter_relevance** | LLM relevance gate on aligned chunks; writes excerpt JSON used by curation |
| After setup | **curate** | Generate UDL lesson JSON (RAG + optional textbook figure linking) |
| | **judge** | Evaluate curated content against UDL criteria; persists per unit |
| | **publish** | Write human-approved content to DynamoDB |

**Pipeline v2 (recommended):**

```bash
# Default setup + relevance filter
python scripts/run_pipeline.py --pipeline-version 2

# Curation and judge (incremental save to file + Postgres after each unit)
python scripts/run_pipeline.py --pipeline-version 2 --steps curate,judge

# Or full flow
python scripts/run_pipeline.py --pipeline-version 2 --full
```

Set `PIPELINE_VERSION=2` in `.env` to avoid passing `--pipeline-version` every time.

`OPENAI_API_KEY` is still required for the default run because **align** calls the embedding API.

#### Pipeline outputs (biology)

| Artifact | Path | Notes |
|----------|------|--------|
| Textbook image manifest | `data/docs/extracted_source_content/biology/textbook_image_manifest.json` | `image_id`, captions, S3 URLs from **extract** |
| Curated modules | `data/docs/extracted_source_content/biology/curated_content.json` | One object per curriculum unit after **curate** |
| UDL judge results | `data/docs/extracted_source_content/biology/udl_subtopic_evaluation.json` | After **judge** |
| Chunk relevance (v2) | `data/docs/extracted_source_content/biology/chunk_relevance.json` | After **filter_relevance** (also in Postgres `chunk_relevance`) |

#### Curated content and textbook images

Each curated unit is stored as JSON with at least:

- **`curated_content`** — Markdown lesson for students (prose, `##` sections, review questions). **Does not** embed images as `![](url)`; figures may be described in words only.
- **`images`** — Array of linked textbook assets (`image_id`, `s3_url`, `caption`, `alt_text`) chosen during curation from aligned chunks via the media linker.

**How images get into the pipeline**

1. **extract** — PyMuPDF extracts figures → S3 `s3://{S3_BUCKET}/{PIPELINE_SUBJECT_SLUG}/textbook-images/{image_id}.{ext}` → Postgres `textbook_images` + manifest.
2. **curate** — The curation LLM may emit internal `image_placeholders` (intent + search hints). The media linker selects real `image_id` values from candidates in aligned chunks and fills `images[]`. Placeholders are stripped from the exported JSON.
3. **Postgres** — `ibrary.curated_content.curated_content_md` holds the markdown; `images` column is JSON `{"images": [...], "formulas": [...]}`.

**Lesson “Figure 1” vs textbook “FIGURE 34.1”**

These are not the same thing and are **not linked** in stored data:

| Source | Example | Meaning |
|--------|---------|---------|
| `curated_content` prose | “(Figure 1) showing a plate with seven labels…” | Pedagogical / lesson-local label or description written by the curation LLM. May refer to an imagined diagram. |
| `images[].caption` | `FIGURE 34.1 For humans, fruits and vegetables…` | Original OpenStax caption from the PDF (chapter 34, figure 1). |

**Do not** map `images[0]` to “Figure 1” in the markdown unless you implement that rule in your app — order follows media-linker picks from textbook chunks, not lesson renumbering. The first attached image may be unrelated to a “Figure 1” mentioned only in prose.

**Serving / UI guidance (current behavior)**

- Render `curated_content` as markdown.
- Display `images[]` separately (figures panel, carousel, or appendix) using `s3_url`, `caption`, and `alt_text`.
- Inline placement after a specific `##` heading is **not** persisted yet (`after_heading` on placeholders is not applied to the exported module).

**Inspect in Postgres**

```sql
SELECT curriculum_unit_id, title,
       left(curated_content_md, 120) AS lesson_preview,
       jsonb_array_length(images::jsonb -> 'images') AS image_count
FROM ibrary.curated_content
ORDER BY curriculum_unit_id
LIMIT 10;
```

**Fix S3 URLs after a path change** (e.g. migrating to `biology/textbook-images/`):

```bash
uv run python scripts/fix_curated_image_urls.py
```

See also [README.md](README.md) § “Curated lessons and textbook images”.

**Bulk load JSON → Postgres** (if you curated/judged to files but Postgres is empty):

```bash
uv run python scripts/load_curated_to_postgres.py
```

**Reviewer portal (local):**

```bash
# Point at Neon development branch (direct host, not -pooler)
# DATABASE_URL_REVIEW=postgresql://...@ep-xxx.eu-west-2.aws.neon.tech/neondb?sslmode=require

uv run python scripts/run_review_portal.py
# Open http://127.0.0.1:8090 — API key from REVIEW_API_KEY in .env (default: dev-review-key-change-me)
```

Features: browse 88 units, read lesson markdown + figures (S3 presigned if AWS profile works), UDL judge sidebar, **Approve (verified)** / **Send back to draft**, reviewer notes.

See [docs/plans/2026-05-16-reviewer-portal.md](docs/plans/2026-05-16-reviewer-portal.md) for production (Cognito + deploy).

### 10. Internal API (Optional)

The read API serves published content from DynamoDB. It requires API key authentication.

```bash
uvicorn ibrary.serving.api:app --reload --port 8080
```

Endpoints:
- `GET /topics?class_name=SSS 1&theme_number=1` — list topics
- `GET /topics/{topic_number}` — get a topic
- `GET /topics/{topic_number}/subtopics` — list subtopics
- `GET /topics/{topic_number}/subtopics/{content_index}` — get a subtopic

All requests require the `X-API-Key` header.

### 11. Development Tools Setup

```bash
# Install pre-commit hooks (recommended)
uv run pre-commit install

# Verify installation
uv run pre-commit run --all-files
```

### 12. Verify Installation

```bash
# Run tests
uv run pytest

# Check code formatting
uv run black --check src tests
uv run isort --check-only src tests

# Run linter
uv run ruff check src tests

# Type check
uv run mypy src
```

## Available Make Commands

```bash
make help              # Show all available commands
make up                # Start Docker services
make down              # Stop Docker services
make db-migrate        # Run Alembic migrations
make dynamodb-setup    # Create DynamoDB tables
make download-textbook # Download OpenStax Biology 2e PDF (~380 MB)
make pipeline                 # Default: extract + validate + align
make pipeline-full            # Through publish (curation, judge, DynamoDB)
make pipeline-resume STEP=validate   # Resume default setup from STEP
make pipeline-full-resume STEP=curate  # Resume full flow from STEP
```

## Common Issues

### Docker services not starting
**Solution:** Ensure Docker Desktop is running and ports 5432/8000 are free:
```bash
docker compose down && docker compose up -d
docker compose logs postgres
docker compose logs dynamodb-local
```

### "password authentication failed for user ibrary"
Another PostgreSQL is using port 5432 with different credentials, or the project container was first created with different env. Reset so the project's Postgres is recreated from your `.env`:

**Windows (PowerShell, from project root):**
```powershell
.\scripts\reset-postgres.ps1
```
Then create DynamoDB tables: `uv run python scripts/create_dynamodb_tables.py`

**Linux/macOS / Git Bash:** Stop other Postgres or free port 5432, then:
```bash
docker compose down -v
docker compose up -d
# wait ~10s, then:
uv run alembic upgrade head
uv run python scripts/create_dynamodb_tables.py
```

### Alembic migration fails (other)
**Solution:** Ensure PostgreSQL is running and `DATABASE_URL` in `.env` matches the container (e.g. `postgresql://ibrary:ibrary_dev@127.0.0.1:5432/ibrary`). Check containers: `.\scripts\compose.ps1 ps` (Windows) or `make ps`.

### PDF extraction produces no chunks
**Solution:** Verify `Biology2e-WEB.pdf` exists and PyMuPDF is installed:
```bash
ls data/docs/extracted_source_content/biology/Biology2e-WEB.pdf
python -c "import fitz; print('PyMuPDF OK')"
```

### Import errors
**Solution:** Ensure package is installed in editable mode:
```bash
uv pip install -e .
```

### OpenAI API errors during curation
**Solution:** Verify your API key and model access:
```bash
python -c "from openai import OpenAI; print(OpenAI().models.list())"
```

The pipeline supports `--resume-from` to restart from the last successful step without re-running earlier steps.

## Project Structure

```
Ibrary_Content_Dev/
├── docker-compose.yml              # PostgreSQL pgvector + DynamoDB Local
├── Makefile                         # Convenience commands
├── alembic.ini                      # Alembic configuration
├── alembic/                         # Database migrations
│   └── versions/
│       └── 001_add_textbook_tables.py
├── scripts/
│   ├── run_pipeline.py              # End-to-end pipeline orchestrator
│   ├── create_dynamodb_tables.py    # DynamoDB table setup
│   ├── setup_dynamodb_local.sh      # DynamoDB Local bootstrap
│   └── init_pgvector.sql            # pgvector extension init
├── src/
│   ├── ibrary/                      # Main package
│   │   ├── config.py                # Central configuration
│   │   ├── db.py                    # SQLAlchemy engine/session
│   │   ├── models.py                # ORM models
│   │   ├── curriculum/              # Curriculum validation
│   │   ├── textbook/                # PDF extraction + DB loading
│   │   ├── alignment/               # Embedding + alignment
│   │   ├── relevance/               # Chunk relevance filter (pipeline v2)
│   │   ├── curation/                # UDL content generation (RAG)
│   │   ├── enrichment/              # Textbook image media linker
│   │   ├── judging/                 # UDL subtopic judge
│   │   └── serving/                 # DynamoDB writer + API
│   └── sourceContentProcessor/      # Legacy extractors
└── data/docs/
    ├── udlg3-graphicorganizer-digital-numbers-a11y.pdf
    └── extracted_source_content/biology/
        ├── Biology2e-WEB.pdf
        ├── OLD NERDC CURRICULUM SSCE BIOLOGY .pdf
        ├── biology_curriculum_structured.json
        ├── textbook_image_manifest.json   # after extract
        ├── curated_content.json           # after curate
        └── udl_subtopic_evaluation.json   # after judge
```

## Additional Resources

- [UV Documentation](https://github.com/astral-sh/uv)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [CAST UDL Guidelines](https://udlguidelines.cast.org/)
