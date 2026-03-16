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
- `OPENAI_MODEL` — LLM model for curation (default: `gpt-4-turbo-preview`)
- `OPENAI_EMBEDDING_MODEL` — Embedding model (default: `text-embedding-3-small`)
- `ALIGNMENT_TOP_K` — Number of textbook chunks to align per curriculum unit (default: `2`)
- `MAX_CONTEXT_TOKENS` — Max tokens for textbook context in curation prompt (default: `8000`)
- `ALIGNMENT_CONFIDENCE_THRESHOLD` — Minimum similarity score for alignment (default: `0.7`)

**Infrastructure:**
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — PostgreSQL credentials (defaults provided)
- `DYNAMODB_ENDPOINT_URL` — DynamoDB endpoint (default: `http://localhost:8000`)
- `S3_BUCKET` — S3 bucket for extracted textbook images (default: `ibrary-content`)
- `S3_ENDPOINT_URL` — S3 endpoint (leave empty for AWS, set for LocalStack)

### 4. Docker Services

The project uses Docker Compose to run PostgreSQL (with pgvector) and DynamoDB Local.

```bash
# Start all services
make up
# or
docker compose up -d

# Verify services are running
docker compose ps
```

Services:
- **PostgreSQL** (`pgvector/pgvector:pg16`) — port 5432, textbook chunks + embeddings
- **DynamoDB Local** (`amazon/dynamodb-local`) — port 8000, curated content serving

### 5. Database Setup

```bash
# Run Alembic migrations to create tables
make db-migrate
# or
alembic upgrade head

# Create DynamoDB tables
make dynamodb-setup
# or
python scripts/create_dynamodb_tables.py
```

The migration creates: `textbooks`, `textbook_chunks`, `textbook_chunk_embeddings`, `textbook_images`, and `curated_content` tables in PostgreSQL.

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

The pipeline extracts textbook content, aligns it with the curriculum, and generates UDL-curated learning modules.

```bash
# Run the full pipeline
make pipeline
# or
python scripts/run_pipeline.py

# Resume from a specific step
python scripts/run_pipeline.py --resume-from curate

# Skip the UDL judge step
python scripts/run_pipeline.py --skip-judge
```

Pipeline steps (in order):
1. **extract** — Parse Biology2e-WEB.pdf, load chunks into PostgreSQL
2. **validate** — Validate curriculum JSON (topics 1-6, SSS 1)
3. **align** — Embed textbook chunks, align with curriculum via pgvector
4. **curate** — Generate UDL content via OpenAI (RAG with textbook context)
5. **judge** — Evaluate curated content against UDL criteria
6. **publish** — Write approved content to DynamoDB

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
make pipeline          # Run the full content pipeline
make pipeline-resume STEP=curate  # Resume from a step
```

## Common Issues

### Docker services not starting
**Solution:** Ensure Docker Desktop is running and ports 5432/8000 are free:
```bash
docker compose down && docker compose up -d
docker compose logs postgres
docker compose logs dynamodb-local
```

### Alembic migration fails
**Solution:** Ensure PostgreSQL is running and `DATABASE_URL` is correct:
```bash
docker compose ps  # check postgres is healthy
alembic upgrade head
```

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
│   │   ├── curation/                # UDL content generation (RAG)
│   │   ├── evaluation/              # UDL judge
│   │   └── serving/                 # DynamoDB writer + API
│   └── sourceContentProcessor/      # Legacy extractors
└── data/docs/
    ├── udlg3-graphicorganizer-digital-numbers-a11y.pdf
    └── extracted_source_content/biology/
        ├── Biology2e-WEB.pdf
        ├── OLD NERDC CURRICULUM SSCE BIOLOGY .pdf
        └── biology_curriculum_structured.json
```

## Additional Resources

- [UV Documentation](https://github.com/astral-sh/uv)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [CAST UDL Guidelines](https://udlguidelines.cast.org/)
