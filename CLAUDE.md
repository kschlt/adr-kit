# Project Context: What You're Building

**You are developing ADR Kit** - a Python library and CLI tool that other projects install to manage their Architectural Decision Records.

**Key understanding:**
- You're building the tool itself, NOT using it
- Any ADRs in `docs/adr/` or `tests/fixtures/` are test fixtures, not real decisions
- Real users: `uv tool install adr-kit` → `adr-kit mcp-server` → use MCP tools in their project

**Mental model:** Ask "Does this make ADR Kit better for other projects?"

## Technology Stack

- **Python 3.10+** (minimum version, don't use 3.11+ features)
- **FastMCP** (MCP server framework in `adr_kit/mcp/server.py`)
- **Pydantic v2** (data models)
- **Typer** (CLI)
- **Sentence-transformers + FAISS** (local semantic search)

## Quick Start

```bash
# Install in editable mode (requires uv)
uv pip install -e ".[dev]"

# Run unit tests
pytest tests/ --cov=adr_kit

# Quality checks
ruff check adr_kit/ tests/
black adr_kit/ tests/
mypy adr_kit/
```

## Development vs Testing: Critical Distinction

**This project installs itself to test the MCP server.** You must understand what to edit vs what to ignore:

### What You Edit (Source Code)
- ✅ `adr_kit/` - **SOURCE CODE** - All library code lives here
- ✅ `tests/` - **TEST CODE** - Unit and integration tests
- ✅ `tests/fixtures/` - **TEST DATA** - Example ADRs for testing

### What You Never Touch (Generated/Installed)
- ❌ `adr_kit.egg-info/` - Installation metadata (auto-generated)
- ❌ `.venv/` or `venv/` - Virtual environment with installed packages
- ❌ `examples/*/` - Read-only reference projects (if present)
- ❌ `.testenv/` - Temporary test installations (auto-generated during tests)
- ❌ Any `site-packages/` directory - Installed packages

### Testing Workflow

**Two types of tests:**

1. **Unit/Integration Tests** (standard)
   ```bash
   pytest tests/
   ```
   - Tests import from `adr_kit/` directly (editable install)
   - No MCP server running needed
   - Fast feedback loop

2. **MCP Server Tests** (requires installation)
   ```bash
   # The test suite handles this automatically
   pytest tests/test_mcp_server.py
   ```
   - Tests start actual MCP server process
   - Uses installed `adr-kit` command
   - Tests real MCP tool invocations
   - May create temporary projects in `.testenv/`

**Critical rule:** When MCP server tests fail, **always fix the source in `adr_kit/`**, never edit installed files. The editable install means changes to `adr_kit/` immediately affect the installed command.

## Key Constraint

**No external network calls in core library code** - MCP servers must work offline and cannot make unauthorized requests. Only Log4brains site generation may use network features.

## Project Structure

```
adr_kit/
├── core/           # Parsing, validation, models
├── index/          # JSON/SQLite generation
├── enforce/        # Lint rule generators
├── mcp/server.py   # FastMCP server (primary interface)
└── cli.py          # Typer CLI (minimal)

tests/fixtures/     # Example ADRs (NOT real decisions)
```

## Design Principles

- MCP server is primary interface (CLI is minimal wrapper)
- Rich, actionable error messages
- Type safety with Pydantic/FastMCP
- Backward compatibility for public APIs

## Additional Documentation

- Performance targets, security requirements: `docs/requirements.md`
- ADR format specification: Examples in `tests/fixtures/`