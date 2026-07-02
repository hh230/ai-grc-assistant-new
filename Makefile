# AI GRC Assistant — developer task runner.
.DEFAULT_GOAL := help
.PHONY: help bootstrap dev up down lint typecheck test format db-up db-down

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

bootstrap: ## Install JS + Python workspaces
	pnpm install
	uv sync

dev: ## Run the full dev stack (turbo)
	pnpm dev

up: ## Start local infrastructure (Postgres+pgvector, etc.)
	docker compose -f docker/compose/docker-compose.yml up -d

down: ## Stop local infrastructure
	docker compose -f docker/compose/docker-compose.yml down

db-up: ## Start only dependencies (db + bus)
	docker compose -f docker/compose/docker-compose.deps.yml up -d

db-down: ## Stop dependencies
	docker compose -f docker/compose/docker-compose.deps.yml down

lint: ## Lint JS + Python
	pnpm lint
	uv run ruff check .

typecheck: ## Typecheck JS + Python
	pnpm typecheck
	uv run mypy .

test: ## Run all tests
	pnpm test
	uv run pytest

format: ## Format JS + Python
	pnpm format
	uv run black .
	uv run ruff check --fix .
