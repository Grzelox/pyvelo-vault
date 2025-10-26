.PHONY: help install sync-deps build up down restart logs clean test format lint docs

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
install:  ## Install dependencies with uv
	uv sync

sync-deps:  ## Sync requirements.txt from pyproject.toml
	./scripts/sync-requirements.sh

# Docker
build:  ## Build Docker containers
	docker-compose build

up:  ## Start all services
	docker-compose up

up-detached:  ## Start all services in background
	docker-compose up -d

down:  ## Stop all services
	docker-compose down

down-volumes: 
	docker-compose down -v

restart:  ## Restart all services
	docker-compose restart

logs:  ## Show logs from all services
	docker-compose logs -f

# Code Quality
format:  ## Format code with Black and isort
	uv run black backend/ frontend/ --line-length 100
	uv run isort backend/ frontend/ --profile black --line-length 100

lint:  ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

# Documentation
docs:  ## Build Sphinx documentation
	cd docs && uv run make html

docs-open:
	cd docs && uv run make html && open build/html/index.html


# Cleanup
clean: 
	rm -rf docs/build/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

dev-setup:  ## Complete development setup
	uv sync
	uv run pre-commit install
	./scripts/sync-requirements.sh
	@echo ""
	@echo "Development environment ready!"
	@echo "Run 'make up' to start the application"

fresh-start:
	docker-compose down -v
	docker-compose build --no-cache
	docker-compose up

