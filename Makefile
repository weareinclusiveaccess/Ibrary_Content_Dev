.PHONY: content-api content-api-docker help

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

content-api: ## Run the DynamoDB content read API locally (port 8080)
	uv run --extra content-api --extra dev python scripts/run_content_api.py

content-api-docker: ## Build the content API container image
	docker build -f Dockerfile.content-api -t ibrary-content-api:dev .
