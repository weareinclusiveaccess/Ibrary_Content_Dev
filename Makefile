.PHONY: up down db-migrate dynamodb-setup download-textbook pipeline pipeline-full pipeline-resume pipeline-full-resume portal-start portal-stop portal-status portal-logs portal-roll portal-cf-origin help

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
