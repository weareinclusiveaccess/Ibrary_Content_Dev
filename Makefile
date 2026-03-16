.PHONY: up down db-migrate dynamodb-setup download-textbook pipeline help

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

pipeline: ## Run the full content pipeline
	python scripts/run_pipeline.py

pipeline-resume: ## Resume pipeline from a step (usage: make pipeline-resume STEP=curate)
	python scripts/run_pipeline.py --resume-from $(STEP)
