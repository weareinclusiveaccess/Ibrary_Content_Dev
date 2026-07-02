.PHONY: content-api content-api-install content-api-docker content-api-env help

# Prefer uv when installed; otherwise use the project venv + pip.
UV := $(shell command -v uv 2>/dev/null)
VENV_PY := .venv/bin/python

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

content-api-env: ## Create .env.content-api from example (skips if it exists)
	@test -f .env.content-api || cp .env.content-api.example .env.content-api
	@echo "Edit .env.content-api (your main .env is unchanged)"

content-api-install: ## Install content-api dependencies (uv or pip)
ifeq ($(UV),)
	@if ! test -x $(VENV_PY) || ! $(VENV_PY) -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then \
		echo "Creating .venv with python3 (requires Python >=3.10)..."; \
		rm -rf .venv; \
		python3 -m venv .venv; \
	fi
	$(VENV_PY) -m pip install -U pip
	$(VENV_PY) -m pip install -e ".[content-api,dev]"
	@echo "Installed with pip into .venv (uv not found)."
else
	uv sync --extra content-api --extra dev
	uv pip install -e .
endif

content-api: content-api-install ## Run the DynamoDB content read API locally (port 8080)
ifeq ($(UV),)
	$(VENV_PY) scripts/run_content_api.py
else
	uv run --extra content-api --extra dev python scripts/run_content_api.py
endif

content-api-docker: ## Build the content API container image
	docker build -f Dockerfile.content-api -t ibrary-content-api:dev .
