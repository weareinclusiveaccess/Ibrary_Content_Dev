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

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your LLM API keys
   ```

3. **Install the package in editable mode:**
   ```bash
   uv pip install -e .
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

### Code Formatting
```bash
uv run black src tests
uv run ruff check src tests
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
