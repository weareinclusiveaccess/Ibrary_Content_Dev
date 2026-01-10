# Project Setup Guide

This document outlines all the steps needed to set up the IBrary project for development.

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
- [ ] **Redis** (optional, for caching) - `brew install redis` or `apt-get install redis`
- [ ] **PostgreSQL/MySQL** (optional, for production database)

### 2. Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd IBrary

# Install dependencies
uv sync --extra dev

# Install package in editable mode
uv pip install -e .
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your configuration
# At minimum, you need at least one LLM API key:
# - OPENAI_API_KEY (recommended for development)
# - ANTHROPIC_API_KEY
# - GOOGLE_API_KEY
```

**Required Environment Variables:**
- At least one LLM API key (OpenAI, Anthropic, or Google)
- `DATABASE_URL` (defaults to SQLite if not set)
- `LOG_LEVEL` (defaults to INFO)

**Optional Environment Variables:**
- `REDIS_URL` - For caching (set `REDIS_ENABLED=true` to enable)
- `STORAGE_BACKEND` - Storage backend (local, s3, gcs)
- `STORAGE_PATH` - Local storage path
- Cost control settings (`MAX_COST_PER_REQUEST`, `MAX_TOKENS_PER_REQUEST`)

### 4. Spacy Model Setup

```bash
# Download the English model (required for text processing)
python -m spacy download en_core_web_sm

# Alternative models (larger, more accurate):
# python -m spacy download en_core_web_md
# python -m spacy download en_core_web_lg
```

### 5. Database Setup

**For SQLite (default, no setup needed):**
- Database file will be created automatically at `./ibrary.db`

**For PostgreSQL:**
```bash
# Install PostgreSQL and create database
createdb ibrary

# Update .env:
DATABASE_URL=postgresql://user:password@localhost:5432/ibrary
```

**For MySQL:**
```bash
# Install MySQL and create database
mysql -u root -p
CREATE DATABASE ibrary;

# Update .env:
DATABASE_URL=mysql://user:password@localhost:3306/ibrary
```

**Run migrations (if using Alembic):**
```bash
# Create migrations
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### 6. Redis Setup (Optional)

```bash
# Install Redis
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Update .env:
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
```

### 7. Development Tools Setup

```bash
# Install pre-commit hooks (recommended)
uv run pre-commit install

# Verify installation
uv run pre-commit run --all-files
```

### 8. Verify Installation

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

## Common Issues

### Issue: UV not found
**Solution:** Add UV to your PATH:
```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.cargo/bin:$PATH"
# Then reload: source ~/.bashrc
```

### Issue: Spacy model not found
**Solution:** Download the model explicitly:
```bash
python -m spacy download en_core_web_sm
# Verify: python -m spacy validate
```

### Issue: Database connection errors
**Solution:** Check DATABASE_URL format and credentials:
- SQLite: `sqlite:///./ibrary.db`
- PostgreSQL: `postgresql://user:pass@host:port/dbname`
- MySQL: `mysql://user:pass@host:port/dbname`

### Issue: Import errors
**Solution:** Ensure package is installed in editable mode:
```bash
uv pip install -e .
```

## Next Steps

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
2. Check [docs/QUICKSTART.md](docs/QUICKSTART.md) for usage examples
3. Review the project structure in [README.md](README.md)

## Additional Resources

- [UV Documentation](https://github.com/astral-sh/uv)
- [Pytest Documentation](https://docs.pytest.org/)
- [Black Code Style](https://black.readthedocs.io/)
- [Ruff Linter](https://docs.astral.sh/ruff/)
