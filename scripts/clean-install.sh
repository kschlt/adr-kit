#!/bin/bash
# ADR Kit Development - Clean Install/Uninstall Script
# This script is for DEVELOPMENT ONLY (not included in distribution package)

set -e

PROJECT_NAME="adr-kit"

usage() {
    echo "ADR Kit Development - Clean Install Script"
    echo ""
    echo "Usage: $0 [uninstall|clean|reinstall|test]"
    echo ""
    echo "Commands:"
    echo "  uninstall  - Remove $PROJECT_NAME package only"
    echo "  clean      - Remove all $PROJECT_NAME artifacts (working files, configs, etc.)"
    echo "  reinstall  - Full clean + reinstall in editable mode"
    echo "  test       - Run quick functionality test after install"
    echo ""
    echo "⚠️  This script is for DEVELOPMENT use in the $PROJECT_NAME project itself."
    echo "   It safely removes/cleans generated artifacts but preserves source code."
    echo "   For end-users, simple 'pip uninstall $PROJECT_NAME' is sufficient."
}

uninstall_package() {
    echo "🗑️  Uninstalling $PROJECT_NAME package..."
    pip uninstall $PROJECT_NAME -y 2>/dev/null || echo "   (package was not installed)"
}

clean_artifacts() {
    echo "🧹 Cleaning $PROJECT_NAME artifacts..."

    # Working directories created by ADR Kit
    for dir in ".adr-kit" ".project-index" ".log4brains"; do
        if [ -d "$dir" ]; then
            echo "   Removing $dir/"
            rm -rf "$dir"
        fi
    done

    # Generated configuration files
    for file in ".eslintrc.adrs.json"; do
        if [ -f "$file" ]; then
            echo "   Removing $file"
            rm -f "$file"
        fi
    done

    # Generated indexes (but NOT the source ADRs)
    for file in "docs/adr/adr-index.json"; do
        if [ -f "$file" ]; then
            echo "   Removing $file"
            rm -f "$file"
        fi
    done

    # IDE configuration files (ADR Kit specific)
    for file in ".claude/settings.local.json" ".cursor/mcp.json"; do
        if [ -f "$file" ]; then
            echo "   Removing $file"
            rm -f "$file"
        fi
    done

    # Python build artifacts specific to adr-kit
    for dir in "${PROJECT_NAME//-/_}.egg-info" "dist" "build"; do
        if [ -d "$dir" ]; then
            echo "   Removing $dir/"
            rm -rf "$dir"
        fi
    done

    # Cache directories (preserve .venv)
    echo "   Cleaning cache directories..."
    find . -name "__pycache__" -not -path "./.venv*" -exec rm -rf {} + 2>/dev/null || true
    for cache_dir in ".mypy_cache" ".pytest_cache" ".ruff_cache"; do
        [ -d "$cache_dir" ] && rm -rf "$cache_dir"
    done

    # Coverage files
    rm -f .coverage .coverage.* 2>/dev/null || true
    [ -d "htmlcov" ] && rm -rf htmlcov/

    echo "✅ Cleanup complete"
}

reinstall() {
    echo "🔄 Performing full reinstall..."
    uninstall_package
    clean_artifacts
    echo ""
    echo "📦 Installing $PROJECT_NAME in editable mode..."
    pip install -e ".[dev]"
    echo "✅ Reinstall complete"
    echo ""
    test_installation
}

test_installation() {
    echo "🧪 Testing installation..."

    if command -v adr-kit >/dev/null 2>&1; then
        echo "✅ CLI available"

        if adr-kit --help >/dev/null 2>&1; then
            echo "✅ CLI functional"
        else
            echo "❌ CLI not working properly"
            return 1
        fi

        echo "✅ Package version: $(pip show $PROJECT_NAME | grep Version | cut -d' ' -f2)"

        # Test MCP server (don't fail if dependencies missing)
        if adr-kit mcp-health >/dev/null 2>&1; then
            echo "✅ MCP server ready"
        else
            echo "⚠️  MCP server has dependency issues (check with: adr-kit mcp-health)"
        fi
    else
        echo "❌ CLI not available in PATH"
        return 1
    fi
}

# Main execution
case "${1:-}" in
    "uninstall")
        uninstall_package
        ;;
    "clean")
        clean_artifacts
        ;;
    "reinstall")
        reinstall
        ;;
    "test")
        test_installation
        ;;
    "help"|"--help"|"-h"|"")
        usage
        ;;
    *)
        echo "❌ Error: Unknown command '$1'"
        echo ""
        usage
        exit 1
        ;;
esac