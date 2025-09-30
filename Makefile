# ADR Kit Development Makefile
# This Makefile is for DEVELOPMENT ONLY (not included in distribution package)

.PHONY: help install clean test test-all test-server lint format build uninstall reinstall server dev-setup dev-cycle dev-reload quality release-prep

# =============================================================================
# Help & Documentation
# =============================================================================

help:
	@echo "ADR Kit Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install      - Install in editable mode with dev dependencies"
	@echo "  uninstall    - Remove adr-kit package"
	@echo "  reinstall    - Clean uninstall + fresh install"
	@echo "  clean        - Remove all generated artifacts"
	@echo ""
	@echo "Development & Testing:"
	@echo "  test         - Run test suite (fast - excludes MCP server tests)"
	@echo "  test-all     - Run comprehensive test suite (includes MCP server tests)"
	@echo "  test-server  - Test MCP server specifically"
	@echo "  lint         - Run linting (ruff + mypy)"
	@echo "  format       - Format code (black + ruff)"
	@echo "  server       - Start MCP server"
	@echo "  build        - Build distribution packages"
	@echo ""
	@echo "Workflows:"
	@echo "  dev-setup    - Initial development setup with guidance"
	@echo "  dev-cycle    - clean + install + test"
	@echo "  dev-reload   - reinstall + test (for after code changes)"
	@echo "  quality      - format + lint + test"
	@echo "  release-prep - full preparation for release"
	@echo ""
	@echo "⚠️  This Makefile is for DEVELOPMENT use only."

# =============================================================================
# Setup & Installation
# =============================================================================

install:
	@echo "🔧 Installing in editable mode with dev dependencies..."
	pip install -e ".[dev]"
	@echo "✅ Installation complete"

uninstall:
	@echo "🗑️ Removing adr-kit package..."
	@chmod +x scripts/clean-install.sh
	@scripts/clean-install.sh uninstall
	@echo "✅ Uninstall complete"

reinstall:
	@echo "🔄 Performing clean uninstall and fresh install..."
	@chmod +x scripts/clean-install.sh
	@scripts/clean-install.sh reinstall
	@echo "✅ Reinstall complete"

clean:
	@echo "🧹 Cleaning all generated artifacts..."
	@chmod +x scripts/clean-install.sh
	@scripts/clean-install.sh clean
	@echo "✅ Clean complete"

# =============================================================================
# Development & Testing
# =============================================================================

test:
	@echo "🧪 Running test suite (fast - excludes MCP server tests)..."
	pytest tests/ --cov=adr_kit --cov-report=term-missing --ignore=tests/test_mcp_server.py
	@echo "✅ Fast tests complete"

test-all:
	@echo "🧪 Running comprehensive test suite (includes MCP server tests)..."
	pytest tests/ -v --cov=adr_kit --cov-report=term-missing --cov-report=html
	@echo "✅ All tests complete. Coverage report in htmlcov/"

test-server:
	@echo "🧪 Running MCP server tests..."
	pytest tests/test_mcp_server.py -v
	@echo "✅ MCP server tests complete"

lint:
	@echo "🔍 Running linting..."
	ruff check adr_kit/ tests/
	mypy adr_kit/
	@echo "✅ Linting complete"

format:
	@echo "🎨 Formatting code..."
	black adr_kit/ tests/
	ruff check --fix adr_kit/ tests/
	@echo "✅ Formatting complete"

server:
	@echo "🚀 Starting MCP server..."
	adr-kit mcp-server

build:
	@echo "📦 Building distribution packages..."
	python -m build
	@echo "✅ Packages built in dist/"

# =============================================================================
# Workflows
# =============================================================================

dev-setup: install test
	@echo "✅ Development setup complete"
	@echo "💡 Next steps:"
	@echo "   1. Run 'make server' to start MCP server"
	@echo "   2. Run 'make test-server' to test server functionality"
	@echo "   3. Use 'make dev-reload' after making code changes"

dev-cycle: clean install test
	@echo "✅ Development cycle complete"

dev-reload: reinstall test
	@echo "✅ Code reloaded and tested"
	@echo "💡 Run 'make test-server' if you changed MCP server code"

quality: format lint test
	@echo "✅ Quality checks passed"

release-prep: clean install format lint test-all build
	@echo "✅ Release preparation complete"
	@echo "📦 Distribution packages ready in dist/"