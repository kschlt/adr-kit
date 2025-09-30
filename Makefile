# ADR Kit Development Makefile
# This Makefile is for DEVELOPMENT ONLY (not included in distribution package)

.PHONY: help install clean test-unit test-integration test-all test-server lint format build uninstall reinstall server dev-setup dev-cycle dev-reload quality release-prep

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
	@echo "  test-unit    - Run unit tests only (fastest - no dependencies)"
	@echo "  test-integration - Run unit + integration tests (requires installation)"
	@echo "  test-all     - Run all tests (includes MCP server tests)"
	@echo "  test-server  - Run MCP server tests only"
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

test-unit:
	@echo "🧪 Running unit tests (fastest - no dependencies)..."
	pytest tests/unit/ --cov=adr_kit --cov-report=term-missing
	@echo "✅ Unit tests complete"

test-integration:
	@echo "🧪 Running unit + integration tests (requires installation)..."
	pytest tests/unit/ tests/integration/ --cov=adr_kit --cov-report=term-missing
	@echo "✅ Integration tests complete"

test-all:
	@echo "🧪 Running all tests (includes MCP server tests)..."
	pytest tests/ -v --cov=adr_kit --cov-report=term-missing --cov-report=html
	@echo "✅ All tests complete. Coverage report in htmlcov/"

test-server:
	@echo "🧪 Running MCP server tests..."
	pytest tests/mcp/ -v
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

dev-setup: install test-integration
	@echo "✅ Development setup complete"
	@echo "💡 Next steps:"
	@echo "   1. Run 'make server' to start MCP server"
	@echo "   2. Run 'make test-server' to test server functionality"
	@echo "   3. Use 'make dev-reload' after making code changes"

dev-cycle: clean install test-integration
	@echo "✅ Development cycle complete"

dev-reload: reinstall test-integration
	@echo "✅ Code reloaded and tested"
	@echo "💡 Next steps:"
	@echo "   - Run 'make test-server' if you changed MCP server code"
	@echo "   - Run 'make test-unit' for fastest feedback during development"

quality: format lint test-integration
	@echo "✅ Quality checks passed"

release-prep: clean install format lint test-all build
	@echo "✅ Release preparation complete"
	@echo "📦 Distribution packages ready in dist/"