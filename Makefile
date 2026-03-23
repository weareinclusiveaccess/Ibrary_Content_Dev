.PHONY: up down db-migrate dynamodb-setup download-textbook pipeline pipeline-full pipeline-resume pipeline-full-resume help

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
