.PHONY: test test-unit test-integration test-cov test-watch install-test help

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-test:  ## Install test dependencies
	uv pip install --group test

test:  ## Run all tests
	pytest

test-unit:  ## Run only unit tests
	pytest -m unit

test-integration:  ## Run only integration tests
	pytest -m integration

test-cov:  ## Run tests with coverage report
	pytest --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

test-watch:  ## Run tests in watch mode (requires pytest-watch)
	ptw

test-fast:  ## Run tests in parallel (requires pytest-xdist)
	pytest -n auto

test-verbose:  ## Run tests with verbose output
	pytest -vv

clean:  ## Clean test artifacts and cache
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

