#!/bin/bash
# Sync requirements.txt files from pyproject.toml using uv
set -e

echo "Syncing requirements.txt files from pyproject.toml..."

# Backend requirements (only backend dependencies)
echo "Generating backend/requirements.txt..."
uv pip compile pyproject.toml --extra backend --universal --quiet -o backend/requirements.txt

# Frontend requirements (only frontend dependencies)
echo "Generating frontend/requirements.txt..."
uv pip compile pyproject.toml --extra frontend --universal --quiet -o frontend/requirements.txt

echo ""
echo "Requirements files updated!"
echo ""
echo "To apply changes:"
echo "  docker-compose build"
