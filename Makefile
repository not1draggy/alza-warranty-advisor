.DEFAULT_GOAL := help
SHELL := /bin/bash

BACKEND := backend
FRONTEND := frontend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python

.PHONY: help
help: ## Show the available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: setup-backend setup-frontend ## Install all dependencies

.PHONY: setup-backend
setup-backend: ## Create the backend virtualenv and install dependencies
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e "$(BACKEND)[dev]"

.PHONY: setup-frontend
setup-frontend: ## Install frontend dependencies
	cd $(FRONTEND) && npm install --no-audit --no-fund

.PHONY: test
test: ## Run the backend test suite
	cd $(BACKEND) && .venv/bin/python -m pytest --cov=app --cov-report=term-missing

.PHONY: lint
lint: ## Lint and type-check both projects
	cd $(BACKEND) && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
	cd $(FRONTEND) && npm run lint && npm run typecheck

.PHONY: format
format: ## Auto-format the backend
	cd $(BACKEND) && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

.PHONY: dev-api
dev-api: ## Run the API against a local database
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

.PHONY: dev-web
dev-web: ## Run the web app in development mode
	cd $(FRONTEND) && npm run dev

.PHONY: migrate
migrate: ## Apply database migrations
	cd $(BACKEND) && .venv/bin/alembic upgrade head

.PHONY: up
up: ## Start the whole stack with Docker Compose
	docker compose up --build -d
	@echo "web: http://localhost:3000  ·  api: http://localhost:8000/docs"

.PHONY: down
down: ## Stop the stack
	docker compose down

.PHONY: logs
logs: ## Tail the stack logs
	docker compose logs -f --tail=100

.PHONY: clean
clean: ## Remove build artefacts and caches
	rm -rf $(VENV) $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/.mypy_cache
	rm -rf $(FRONTEND)/node_modules $(FRONTEND)/.next
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
