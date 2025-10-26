#!/bin/bash
# Sync requirements.txt files from pyproject.toml using uv
set -e

echo "Syncing requirements.txt files from pyproject.toml..."

# Backend requirements (all production dependencies)
echo "Generating backend/requirements.txt..."
uv pip compile pyproject.toml --universal --quiet -o backend/requirements.txt

# Frontend requirements (only frontend-related dependencies)
echo "Generating frontend/requirements.txt..."
cat > frontend/requirements.txt << 'EOF'
streamlit
requests
pandas
EOF

echo "Requirements files updated!"
echo ""
echo "To apply changes:"
echo "  docker-compose build"
