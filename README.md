# pyvelo-vault

**pyvelo-vault** is a self-hosted, personal athletic data hub, designed for cyclists and data enthusiasts who want to own their data. It allows you to connect to various fitness platforms (like Strava), aggregate all your activities into a private, local database, and explore your performance with a personalized dashboard.

The entire application is built with a "Python-first" philosophy and is designed for easy deployment using Docker, giving you complete control over your athletic history.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pyvelo-vault.git
cd pyvelo-vault

# Configure environment variables (see below)
cp .env.example .env
# Edit .env with your actual values

# Start the application
make up
# or: docker-compose up
```

### Environment Configuration

The application uses environment variables for sensitive configuration. A `.env.example` file is provided with all required variables:

1. **Copy the example file:**

   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your actual values:**
   - `SECRET_KEY`: Generate a secure key with `openssl rand -hex 32`
   - `POSTGRES_PASSWORD`: Set a strong database password
   - `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`: Get these from the [Strava API Settings](https://www.strava.com/settings/api)
   - Other variables have sensible defaults for local development

### Access the Application

- **Frontend**: <http://localhost:8501>
- **API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs>

## Development

### Setup Development Environment

```bash
# Complete setup (recommended)
make dev-setup

# Or step by step:
uv sync                      # Install dependencies
uv run pre-commit install    # Install git hooks
make sync-deps              # Sync requirements.txt
make up                     # Start services
```

### Common Commands

```bash
# Development
make install              # Install dependencies with uv
make sync-deps           # Sync requirements.txt from pyproject.toml
make format              # Format code with Black and isort
make lint                # Run pre-commit hooks

# Testing
cd backend && make test              # Run all tests
cd backend && make test-cov          # Run tests with coverage
cd backend && make test-unit         # Run unit tests only
cd backend && make test-integration  # Run integration tests only

# Docker
make up                  # Start all services
make down                # Stop all services
make restart             # Restart services
make logs                # Show logs
make build               # Rebuild containers

# Documentation
make docs                # Build Sphinx documentation
make docs-open           # Build and open docs

# Utilities
make clean               # Remove build artifacts
make fresh-start         # Clean rebuild (deletes data)
```

See `make help` for all available commands.

## Testing

pyvelo-vault has a comprehensive test suite with **150+ tests** covering all backend modules.

### Quick Test Commands

```bash
# Install test dependencies
uv pip install --group test

# Run all tests
cd backend && pytest

# Run with coverage
cd backend && pytest --cov=app --cov-report=html

# Run specific tests
cd backend && pytest tests/test_models.py
cd backend && pytest -m unit           # Unit tests only
cd backend && pytest -m integration    # Integration tests only
```

### High-Level Functionality

This application will allow a user to:

- **Connect Securely:** Authenticate with external fitness platforms (starting with Strava) using their own API keys to maintain privacy and control.
- **Aggregate Your Data:** Download and consolidate a complete history of all activities into a single, local source of truth, achieving full data sovereignty.
- **Analyze & Visualize:** Use a clean web interface to view dashboards, track progress over time, and gain custom insights that other platforms don't offer.
- **Own Your History:** Keep your data on your own machine, forever. No subscriptions, no data selling, no risk of a service shutting down and taking your logs with it.
- **Extensible by Design:** The architecture will allow for new data providers (e.g., Garmin Connect, Wahoo) to be added in the future.

### Quick Architecture Overview

`pyvelo-vault` is built on a modern, containerized architecture that separates concerns for scalability and maintainability. The core components are:

- **Web Frontend:** A user interface built with **Streamlit** for data visualization, dashboards, and user settings. It communicates exclusively with the API backend.
- **API Backend:** A headless API powered by **FastAPI**. It handles all user authentication, business logic, and database interactions, providing a secure and fast JSON interface.
- **Background Worker:** A **Celery** and **Redis**-based system for handling all long-running tasks like syncing data from external services. This ensures the UI remains fast and responsive at all times.
- **Database:** A **PostgreSQL** database (with the PostGIS extension) for storing all structured user and activity data, enabling powerful queries and future geospatial analysis.

The entire stack is orchestrated by **Docker Compose**, allowing for a simple, one-command deployment for anyone who wishes to self-host the application.
