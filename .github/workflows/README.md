# GitHub Actions Workflows

This directory contains all CI/CD workflows for the IBrary project.

## Available Workflows

### 1. CI Workflow (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**Jobs:**
- **Lint & Format Check**: Validates code formatting with Black, isort, and Ruff
- **Type Check**: Runs mypy for type checking
- **Test**: Runs pytest across Python 3.10, 3.11, and 3.12
- **Security Scan**: Runs safety and bandit security checks

**Status Badge:**
```markdown
[![CI](https://github.com/YOUR_USERNAME/IBrary/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/IBrary/actions/workflows/ci.yml)
```

### 2. CodeQL Security Analysis (`.github/workflows/codeql.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Weekly schedule (Sundays at midnight)
- Manual workflow dispatch

**Purpose:**
- Advanced security vulnerability scanning
- Code quality analysis
- Automated security alerts

### 3. Dependency Review (`.github/workflows/dependency-review.yml`)

**Triggers:**
- Pull requests to `main` or `develop`

**Purpose:**
- Reviews dependency changes in PRs
- Fails on moderate or higher severity vulnerabilities
- Prevents merging insecure dependencies

### 4. Dependabot (`.github/dependabot.yml`)

**Triggers:**
- Weekly schedule (Mondays at 9:00 AM)

**Purpose:**
- Automatically updates Python dependencies
- Updates GitHub Actions
- Groups minor/patch updates
- Creates PRs with proper labels

**Configuration:**
- Weekly updates for Python packages
- Weekly updates for GitHub Actions
- Groups dev dependencies together
- Groups production dependencies together
- Limits open PRs to 5

### 5. Release Workflow (`.github/workflows/release.yml`)

**Triggers:**
- Push of version tags (e.g., `v1.0.0`)
- Manual workflow dispatch with version input

**Purpose:**
- Builds Python package
- Publishes to PyPI (requires `PYPI_API_TOKEN` secret)
- Creates GitHub release

**Required Secrets:**
- `PYPI_API_TOKEN`: PyPI API token for publishing

## Required GitHub Secrets

To enable full functionality, add these secrets to your repository:

1. **PYPI_API_TOKEN** (optional): Required for publishing to PyPI
   - Go to PyPI → Account Settings → API tokens
   - Create a new token with "Upload packages" scope
   - Add as repository secret: `PYPI_API_TOKEN`

2. **Codecov Token** (optional): For coverage reporting
   - Sign up at codecov.io
   - Add repository
   - Add token as secret: `CODECOV_TOKEN`

## Workflow Status Badges

Add these badges to your README.md:

```markdown
[![CI](https://github.com/YOUR_USERNAME/IBrary/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/IBrary/actions/workflows/ci.yml)
[![CodeQL](https://github.com/YOUR_USERNAME/IBrary/actions/workflows/codeql.yml/badge.svg)](https://github.com/YOUR_USERNAME/IBrary/actions/workflows/codeql.yml)
```

## Enabling Workflows

1. **First-time setup:**
   - Workflows are automatically enabled when pushed to `.github/workflows/`
   - Ensure your repository has Actions enabled:
     - Settings → Actions → General
     - Enable "Allow all actions and reusable workflows"

2. **CodeQL:**
   - First run requires repository owner approval
   - Go to Security → Code scanning → CodeQL analysis
   - Click "Set up this workflow"

3. **Dependabot:**
   - Automatically enabled with `.github/dependabot.yml`
   - Check status at: Insights → Dependency graph → Dependabot

## Customization

### Adjusting Python Versions

Edit `.github/workflows/ci.yml`:
```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]  # Modify as needed
```

### Adjusting Schedule

Edit `.github/dependabot.yml`:
```yaml
schedule:
  interval: "weekly"  # Options: daily, weekly, monthly
  day: "monday"       # Day of week
  time: "09:00"       # Time (UTC)
```

### Adding Coverage Reporting

Add Codecov step to `ci.yml`:
```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    file: ./coverage.xml
```

## Troubleshooting

**Workflows not running:**
- Check Actions tab → All workflows
- Verify workflow files are in `.github/workflows/`
- Check repository Actions settings are enabled

**Test failures:**
- Review test output in Actions tab
- Run tests locally: `uv run pytest`
- Check Python version compatibility

**Dependency update issues:**
- Check Dependabot settings
- Review dependency conflicts in PR comments
- Manually update conflicting dependencies
