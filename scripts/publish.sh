#!/bin/bash
# Publish ADR Kit to PyPI using uv
# This script extracts credentials from ~/.pypirc and uses uv publish

set -e  # Exit on error

echo "📦 Publishing ADR Kit to PyPI..."

# Check if dist/ exists
if [ ! -d "dist" ]; then
    echo "❌ Error: dist/ directory not found. Run 'uv build' first."
    exit 1
fi

# Check if ~/.pypirc exists
if [ ! -f ~/.pypirc ]; then
    echo "❌ Error: ~/.pypirc not found. Configure PyPI credentials first."
    exit 1
fi

# Extract PyPI token from ~/.pypirc
echo "🔑 Extracting credentials from ~/.pypirc..."
TOKEN=$(grep -A2 '\[pypi\]' ~/.pypirc | grep password | sed 's/password = //' | tr -d ' ')

if [ -z "$TOKEN" ]; then
    echo "❌ Error: Could not extract password from ~/.pypirc"
    exit 1
fi

# Publish with uv
echo "🚀 Publishing to PyPI..."
UV_PUBLISH_USERNAME="__token__" \
UV_PUBLISH_PASSWORD="$TOKEN" \
uv publish "$@"

echo "✅ Published successfully!"
echo "🔗 View at: https://pypi.org/project/adr-kit/"
