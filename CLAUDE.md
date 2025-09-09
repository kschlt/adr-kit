# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADR Kit is a Python library and CLI tool for managing Architectural Decision Records (ADRs) in the MADR (Markdown ADR) format. The project is AI-first, designed for autonomous agents like Claude Code to manage architectural decisions.

**Key Features:**
- Python 3.10+ library (`adr_kit/`) for creating, validating, and indexing ADRs
- CLI tool (`adr-kit`) with essential ADR management operations (minimal by design)
- MCP server (`adr-kit mcp-server`) for exposing rich contextual tools to AI agents
- **Structured policy system** with front-matter policy blocks for automated enforcement
- JSON Schema validation with semantic rule enforcement
- **Log4brains integration** for beautiful static site generation
- Lint rule generators for ESLint, Ruff, and import-linter with policy extraction
- **Semantic search** with local vector embeddings (sentence-transformers)
- **Immutability system** with content digests and tamper detection
- SQLite catalog generation for complex querying

## Architecture

The project is fully implemented with this structure:

```
adr_kit/
├── core/
│   ├── model.py          # Pydantic models for ADR data structures
│   ├── parse.py          # YAML front-matter + Markdown parsing
│   └── validate.py       # JSON Schema + semantic validation engine
├── index/
│   ├── json_index.py     # JSON index generation with relationships
│   └── sqlite_index.py   # SQLite catalog with complex queries
├── enforce/
│   ├── eslint.py         # ESLint rule generation from ADRs
│   └── ruff.py           # Ruff/import-linter config generation
├── cli.py                # Typer-based CLI interface (10K+ lines)
└── mcp/
    └── server.py         # MCP server with rich AI agent tools (30K+ lines)
```

## Development Commands

### Setup and Installation
```bash
# Install in development mode with dev dependencies (requires Python 3.10+)
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests with coverage
pytest tests/ --cov=adr_kit --cov-report=term-missing

# Run specific test file
pytest tests/test_core_model.py -v

# Run tests for specific functionality
pytest tests/test_cli.py::test_validate_command -v
```

### Code Quality
```bash
# Lint code with ruff
ruff check adr_kit/ tests/

# Format code with black  
black adr_kit/ tests/

# Type checking with mypy
mypy adr_kit/
```

### CLI Commands

All CLI commands support `--adr-dir` to specify ADR directory (defaults to `docs/adr`):

```bash
# Initialize ADR structure
adr-kit init [--adr-dir docs/adr]

# Create new ADR
adr-kit new "Use React Query" --tags frontend,data --deciders team-lead

# Validate ADRs (single or all)
adr-kit validate [--id ADR-0001]

# Generate JSON index
adr-kit index --out docs/adr/adr-index.json

# Supersede existing ADR
adr-kit supersede ADR-0003 --title "Enhanced Database Strategy"

# Generate lint configurations
adr-kit export-lint eslint --out .eslintrc.adrs.json
adr-kit export-lint ruff --out pyproject.toml

# Start MCP server for AI agents (primary interface)
adr-kit mcp-server

# Legacy manual commands
adr-kit legacy  # Show all available legacy commands
```

## ADR Format with Structured Policy

ADRs use MADR format with YAML front-matter and structured policy support:

```yaml
---
id: ADR-0001
title: "Use React Query instead of custom data fetching"
status: accepted
date: 2025-09-03
deciders: ["frontend-team", "tech-lead"]
tags: ["frontend", "data", "performance"]
supersedes: ["ADR-0003"]
superseded_by: []
policy:
  imports:
    disallow: ["axios", "fetch"]
    prefer: ["@tanstack/react-query"]
  boundaries:
    layers:
      - name: "api"
        path: "src/api/*"
    rules:
      - forbid: "components -> database"
  python:
    disallow_imports: ["requests"]
  rationales: ["Performance", "Caching", "Developer experience"]
---

## Context

Custom data fetching logic is scattered across components, leading to code duplication and inconsistent error handling.

## Decision

Use React Query (@tanstack/react-query) for all data fetching operations.

## Consequences

### Positive
- Standardized data fetching patterns
- Built-in caching and background updates
- Better error handling and loading states

### Negative  
- Additional dependency and learning curve
- Migration effort for existing code

## Alternatives

- **Native fetch()**: Simple but lacks caching and state management
- **Axios**: Good HTTP client but no query management features
```

## MCP Integration for AI Agents

The MCP server (`adr-kit mcp-server`) is the primary interface for AI agents, providing standardized tools with rich contextual guidance:

### Available MCP Tools

#### **Core ADR Lifecycle**
- **`adr_init()`** - Initialize ADR system with directory structure
- **`adr_query_related()`** - Find related/conflicting ADRs before creation (semantic search)
- **`adr_create()`** - Create proposed ADRs with structured policy support
- **`adr_approve()`** - Approve ADRs with immutability and digest tracking
- **`adr_supersede()`** - Replace decisions with bidirectional updates
- **`adr_validate()`** - Validate ADRs with policy requirements and tamper detection

#### **Policy & Enforcement**  
- **`adr_export_lint_config()`** - Generate ESLint/Ruff configs from structured policies
- **`adr_guard()`** - Validate code changes against ADR policies (upcoming)

#### **Search & Discovery**
- **`adr_semantic_index()`** - Build vector embeddings for semantic search (upcoming)
- **`adr_match()`** - Semantic search through ADR content (upcoming)
- **`adr_index()`** - Generate JSON/SQLite indexes with metadata filtering

#### **Site Generation**
- **`adr_render_site()`** - Generate beautiful static site via Log4brains integration

### AI Agent Workflow

1. **Query Phase**: Always check `adr_query_related()` for conflicts before creating ADRs
2. **Create Phase**: Use `adr_create()` with structured policy to generate ADRs in 'proposed' status
3. **Policy Phase**: Extract and structure policies in front-matter for automated enforcement
4. **Approve Phase**: Use `adr_approve()` after human review to freeze decisions with content digests
5. **Enforce Phase**: Use `adr_export_lint_config()` to generate automated enforcement rules
6. **Supersede Phase**: Use `adr_supersede()` when decisions need updating
7. **Site Generation**: Use `adr_render_site()` to create browsable documentation

## Key Implementation Details

- **Python 3.10+ compatibility** (required for FastMCP and semantic search)
- **Pydantic v2** for data validation and parsing with structured policy models
- **Typer** for minimal CLI interface with rich help and validation
- **Log4brains integration** for proven static site generation (no library modification)
- **Sentence-transformers** for fast local semantic search (optimized for Mac Silicon)
- **FAISS** for sub-100ms vector similarity search
- **No external network calls** in core logic (fully local semantic search)
- **Performance optimized**: validates 500+ ADRs in under 1 second, semantic search <100ms
- **Rich error context**: detailed validation messages with actionable guidance for AI agents
- **Automatic relationship management**: bidirectional supersede logic with immutability
- **Content digest tracking**: SHA-256 hashes for tamper detection and approval workflow
- Always use most modern Python approaches
  - Maximize type safety and typing
  - Leverage FastAPI and FastMCP type safety features