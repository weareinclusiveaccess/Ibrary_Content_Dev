# Contributing to IBrary

Thank you for your interest in contributing to IBrary! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/your-username/IBrary.git
   cd IBrary
   ```

2. **Set up your development environment:**
   ```bash
   # Install dependencies
   uv sync --extra dev
   
   # Set up environment variables
   cp .env.example .env
   # Edit .env with your API keys
   
   # Download Spacy model
   python -m spacy download en_core_web_sm
   
   # Install pre-commit hooks
   uv run pre-commit install
   ```

## Code Style

This project uses:
- **Black** for code formatting (line length: 100)
- **isort** for import sorting (Black profile)
- **Ruff** for linting
- **mypy** for type checking

Before committing, ensure your code passes all checks:

```bash
# Format code
uv run black src tests
uv run isort src tests

# Lint code
uv run ruff check src tests
uv run ruff check --fix src tests  # Auto-fix issues

# Type check
uv run mypy src
```

Or use pre-commit hooks (automatic):
```bash
uv run pre-commit run --all-files
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_specific.py

# Run with verbose output
uv run pytest -v
```

## Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes:**
   - Write clean, documented code
   - Follow existing code style
   - Add tests for new features
   - Update documentation as needed

3. **Ensure all checks pass:**
   ```bash
   # Format and lint
   uv run black src tests
   uv run isort src tests
   uv run ruff check --fix src tests
   
   # Run tests
   uv run pytest
   
   # Type check
   uv run mypy src
   ```

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   # or
   git commit -m "fix: fix bug description"
   ```

   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `style:` for formatting changes
   - `refactor:` for code refactoring
   - `test:` for test changes
   - `chore:` for maintenance tasks

5. **Push and create a pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Process

1. Update the README.md if needed
2. Add tests for new functionality
3. Ensure all CI checks pass
4. Request review from maintainers
5. Address any feedback
6. Once approved, your PR will be merged

## Project Structure

```
IBrary/
├── src/ibrary/          # Main source code
│   ├── api/            # API endpoints
│   ├── core/           # Core transformation logic
│   ├── llm/            # LLM provider abstractions
│   ├── profiles/       # Transformation profiles
│   ├── validation/     # Validation and evaluation
│   ├── storage/        # Content storage and caching
│   └── utils/          # Utilities
├── config/             # Configuration files
├── tests/              # Test suite
└── docs/               # Documentation
```

## Questions?

Feel free to open an issue for questions or discussions!
