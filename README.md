# Ibrary_Content_Dev

# IBrary - Automated Content Rewording Component

An automated, standardized content rewording component that transforms curriculum-aligned secondary school content into simplified, relatable, accessibility-aware explanations optimized for visually impaired learners and audio-first delivery.

## Overview

IBrary provides an API-driven content rewording pipeline that:
- Transforms approved curriculum content into accessible formats
- Validates content for readability, accessibility, and semantic fidelity
- Uses profile-driven transformation for consistency
- Caches results to optimize costs and performance
- Supports multiple LLM providers (OpenAI, Anthropic, Google)

## MVP Scope

**Initial Target:**
- **Grade Level:** SSS1 (Senior Secondary School 1)
- **Subjects:** Chemistry, Physics, Biology
- **Focus:** Audio-first, accessible content for visually impaired learners

## Features

- ✅ Profile-based content transformation
- ✅ Multi-provider LLM support (OpenAI, Anthropic, Google)
- ✅ Hybrid evaluation (deterministic + semantic checks)
- ✅ Caching and versioning
- ✅ Accessibility-focused validation
- ✅ Tiered failure handling with retries
- ✅ Cost control mechanisms

## Project Structure

```
ibrary/
├── src/
│   └── ibrary/
│       ├── __init__.py
│       ├── api/              # API endpoints
│       ├── core/              # Core transformation logic
│       ├── llm/               # LLM provider abstractions
│       ├── profiles/          # Transformation profiles
│       ├── validation/        # Validation and evaluation
│       ├── storage/           # Content storage and caching
│       └── utils/             # Utilities
├── config/                    # Configuration files
│   └── profiles/              # Transformation profile definitions
├── tests/                     # Test suite
├── docs/                      # Documentation
└── pyproject.toml            # Project configuration
```

## Installation

### Prerequisites

- Python 3.10 or higher
- UV package manager

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd IBrary
   ```

2. **Install UV package manager** (if not already installed):
   ```bash
   # On macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # On Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **Install dependencies:**
   ```bash
   # Install production dependencies
   uv sync
   
   # Install development dependencies (includes black, isort, ruff, pytest, etc.)
   uv sync --extra dev
   ```

4. **Set up environment variables:**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env with your LLM API keys (at least one provider required)
   # Required: OPENAI_API_KEY or ANTHROPIC_API_KEY or GOOGLE_API_KEY
   ```

5. **Download Spacy model** (required for text processing):
   ```bash
   python -m spacy download en_core_web_sm
   # Or use the model you prefer: en_core_web_md, en_core_web_lg
   ```

6. **Install the package in editable mode:**
   ```bash
   uv pip install -e .
   ```

7. **Set up pre-commit hooks** (recommended):
   ```bash
   uv run pre-commit install
   ```

## Quick Start

See `docs/QUICKSTART.md` for detailed usage examples.

## Configuration

Transformation profiles define how content is transformed. See `config/profiles/` for example profiles.

## Development

### Running Tests
```bash
uv run pytest
```

### Code Formatting and Linting

This project uses **black** for code formatting, **isort** for import sorting, and **ruff** for linting.

#### Format Code
```bash
# Format with black
uv run black src tests

# Sort imports with isort
uv run isort src tests

# Or format and sort in one go
uv run black src tests && uv run isort src tests
```

#### Lint Code
```bash
# Check code with ruff
uv run ruff check src tests

# Auto-fix issues where possible
uv run ruff check --fix src tests

# Format with ruff (alternative to black)
uv run ruff format src tests
```

#### Format and Lint Everything
```bash
# Run all formatters and linters
uv run black src tests
uv run isort src tests
uv run ruff check --fix src tests
uv run ruff format src tests
```

### Pre-commit Hooks

Install pre-commit hooks to automatically format and lint code before commits:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files

# Run hooks on staged files only (automatic on commit)
uv run pre-commit run
```

### Type Checking
```bash
uv run mypy src
```

## Architecture

This project follows the architecture decisions outlined in the proposal document:
- **Stateless API** design
- **Profile-based transformation** for consistency
- **Two-pass generation** with self-check
- **Hybrid evaluation** (deterministic + semantic)
- **Tiered failure handling**
- **Built-in cost controls**
- **Hybrid content creation** (profile-based cache)

## License

MIT
