# ADR Kit Development Makefile
# This Makefile is for DEVELOPMENT ONLY (not included in distribution package)

.PHONY: help install clean test lint format build dev-setup uninstall reinstall

# Default target
help:
	@echo "ADR Kit Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  dev-setup    - Set up development environment"
	@echo "  install      - Install in editable mode with dev dependencies"
	@echo "  uninstall    - Remove adr-kit package"
	@echo "  reinstall    - Clean uninstall + fresh install"
	@echo "  clean        - Remove all generated artifacts"
	@echo ""
	@echo "Development:"
	@echo "  test         - Run test suite"
	@echo "  lint         - Run linting (ruff + mypy)"
	@echo "  format       - Format code (black + ruff)"
	@echo "  build        - Build distribution packages"
	@echo ""
	@echo "⚠️  This Makefile is for DEVELOPMENT use only."

# Development environment setup
dev-setup:
	@echo "🔧 Setting up development environment..."
	pip install -e ".[dev]"
	@echo "✅ Development setup complete"

# Install in editable mode
install:
	pip install -e ".[dev]"

# Clean uninstall using our script
uninstall:
	@chmod +x scripts/clean-install.sh
	@scripts/clean-install.sh uninstall

# Clean all artifacts
clean:
	@chmod +x scripts/clean-install.sh
	@scripts/clean-install.sh clean

# Full reinstall
reinstall:
	@chmod +x scripts/clean-install.sh
	@scripts/clean-install.sh reinstall

# Run tests
test:
	pytest tests/ --cov=adr_kit --cov-report=term-missing

# Run comprehensive tests (like the old run_workflow_tests.py)
test-all:
	@echo "🧪 Running comprehensive test suite..."
	pytest tests/ -v --cov=adr_kit --cov-report=term-missing --cov-report=html
	@echo "✅ All tests complete. Coverage report in htmlcov/"

# Linting
lint:
	@echo "🔍 Running linting..."
	ruff check adr_kit/ tests/
	mypy adr_kit/

# Format code
format:
	@echo "🎨 Formatting code..."
	black adr_kit/ tests/
	ruff check --fix adr_kit/ tests/

# Build distribution packages
build:
	@echo "📦 Building distribution packages..."
	python -m build
	@echo "✅ Packages built in dist/"

# Quick development cycle: clean -> install -> test
dev-cycle: clean install test
	@echo "✅ Development cycle complete"

# Quality check: format + lint + test
quality: format lint test
	@echo "✅ Quality checks passed"

# Release preparation: clean + format + lint + test + build
release-prep: clean install format lint test-all build
	@echo "✅ Release preparation complete"
	@echo "📦 Distribution packages ready in dist/"