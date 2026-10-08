.PHONY: up down db-migrate dynamodb-setup download-textbook pipeline pipeline-full pipeline-resume pipeline-full-resume portal-start portal-stop portal-status portal-logs portal-roll portal-cf-origin content-api content-api-install content-api-docker content-api-env help

# Prefer uv when installed; otherwise use the project venv + pip.
UV := $(shell command -v uv 2>/dev/null)
VENV_PY := .venv/bin/python

# --- Reviewer portal lifecycle ----------------------------------------------
# All portal commands delegate to scripts/portal_admin.py so that the recipes
# don't depend on a POSIX-shell-only feature like `$(...)` substitution
# (Make on Windows defaults to cmd.exe, which would otherwise break).
PORTAL_ADMIN := uv run python scripts/portal_admin.py

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start Docker services (PostgreSQL + DynamoDB Local)
	docker compose up -d

down: ## Stop Docker services
	docker compose down

db-migrate: ## Run Alembic migrations
	alembic upgrade head

dynamodb-setup: ## Create DynamoDB tables
	python scripts/create_dynamodb_tables.py

download-textbook: ## Download OpenStax Biology 2e PDF (~380 MB)
	sh scripts/download_textbook.sh

pipeline: ## Default: extract PDF + validate curriculum + align (no LLM curation)
	python scripts/run_pipeline.py

pipeline-full: ## Full run through publish (curation, judge, DynamoDB)
	python scripts/run_pipeline.py --full

pipeline-resume: ## Resume within default setup (STEP=extract|validate|align). For curate+: use pipeline-full-resume
	python scripts/run_pipeline.py --resume-from $(STEP)

pipeline-full-resume: ## Resume full pipeline from STEP (e.g. STEP=curate)
	python scripts/run_pipeline.py --full --resume-from $(STEP)

# --- Reviewer portal (deployed on AWS) --------------------------------------

portal-start: ## Start the EC2 portal instance and repoint CloudFront origin
	$(PORTAL_ADMIN) start

portal-stop: ## Stop the EC2 portal instance (preserves EBS, ~$$0.65/mo)
	$(PORTAL_ADMIN) stop

portal-status: ## Show instance state, container status, and portal URL
	$(PORTAL_ADMIN) status

portal-logs: ## Tail the last 80 lines of the portal container
	$(PORTAL_ADMIN) logs

portal-roll: ## Pull :latest from ECR and restart the container on EC2
	$(PORTAL_ADMIN) roll

portal-cf-origin: ## Force CloudFront origin to current EC2 public DNS
	$(PORTAL_ADMIN) cf-origin

# --- Public content read API ------------------------------------------------

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
