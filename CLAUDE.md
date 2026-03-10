# Project Context: What You're Building

**You are developing ADR Kit** - a Python library and CLI tool that other projects install to manage their Architectural Decision Records.

**Key understanding:**
- You're building the tool itself, NOT using it
- Any ADRs in `docs/adr/` are test fixtures created when you run `adr-kit init` locally (gitignored)
- The `guide/` folder contains **project documentation** (WORKFLOWS.md etc), not ADRs
- Real users install ADR Kit, which creates `docs/adr/` in *their* project (standard location)
- In this project: `guide/` = our docs, `docs/adr/` = test fixtures (gitignored)

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

## Development Commands

Use Makefile commands for common development tasks:

```bash
# Setup & Installation
make install      # Install in editable mode with uv
make reinstall    # Clean uninstall + fresh install (recommended for testing)
make clean        # Remove all generated artifacts
make uninstall    # Remove adr-kit package

# Testing
make test-unit    # Fast unit tests (no dependencies)
make test-integration  # Unit + integration tests
make test-all     # All tests including MCP server tests
make test-server  # MCP server tests only

# Quality
make lint         # Run linting (ruff + mypy)
make format       # Format code (black + ruff)

# Development
make server       # Start MCP server manually
make build        # Build distribution packages
```

**Common workflow:**
```bash
# Edit source code in adr_kit/
make reinstall    # Clean install to test changes
make test-all     # Verify everything works
```

## Development vs Testing: Critical Distinction

**This project installs itself to test the MCP server.** You must understand what to edit vs what to ignore.

### Three Versions of ADR Kit

1. **SOURCE CODE** (what we edit)
   - Location: `adr_kit/` directory
   - This is the library you're developing
   - **Always make changes here**

2. **LOCAL EDITABLE INSTALL** (for testing in this project)
   - Installed via: `uv pip install -e ".[dev]"`
   - Lives in: `.venv/lib/python3.X/site-packages/adr_kit/` (symlinked to source)
   - Command: `.venv/bin/adr-kit` or `uv run adr-kit`
   - **This is what you test with** - changes to source code immediately apply

3. **SYSTEM INSTALL** (on your machine)
   - Installed via: `uv tool install adr-kit`
   - Lives in: `~/.local/share/uv/tools/adr-kit/`
   - Command: `~/.local/bin/adr-kit` or just `adr-kit` (in PATH)
   - **DO NOT use this for testing** - it's a frozen version

### What You Edit (Source Code)
- ✅ `adr_kit/` - **SOURCE CODE** - All library code lives here
- ✅ `tests/` - **TEST CODE** - Unit and integration tests
- ✅ `guide/` - **PROJECT DOCUMENTATION** - WORKFLOWS.md, guides, etc.

### What You Never Touch (Generated/Installed)

**Build artifacts:**
- ❌ `adr_kit.egg-info/` - Installation metadata (auto-generated)
- ❌ `dist/` - Distribution packages
- ❌ `build/` - Build artifacts
- ❌ `.venv/` or `venv/` - Virtual environment with installed packages
- ❌ Any `site-packages/` directory - Installed packages

**Test artifacts:**
- ❌ `.testenv/` - Temporary test installations (auto-generated during tests)
- ❌ `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` - Tool caches
- ❌ `.coverage`, `htmlcov/` - Coverage reports

**ADR Kit's own working files (when using it to test itself):**
- ❌ `.adr-kit/` - Working directory (backups, state)
- ❌ `.project-index/` - Vector embeddings for semantic search
- ❌ `docs/adr/` - **ENTIRE DIRECTORY** created by `adr-kit init` (test fixtures only)
  - Includes: ADR-*.md files, .adr/ cache, adr-index.json, *.backup files
  - **Important**: In this project, `docs/adr/` is gitignored test data
  - Project documentation lives in `guide/` instead
- ❌ `.eslintrc.adrs.json` - Generated lint config

**External installations:**
- ❌ `~/.local/share/uv/tools/adr-kit/` - System installation
- ❌ `examples/*/` - Read-only reference projects (if present)

All of these are git-ignored and removed by `make clean` or `make reinstall`.

### Development Workflow: Edit → Test → Verify

**ALWAYS follow this pattern:**

1. **Make changes to source code** in `adr_kit/`

2. **Test changes immediately** (editable install makes this instant)
   ```bash
   # Run unit tests (fast, no server needed)
   pytest tests/unit/

   # Run MCP server tests (spawns real server)
   pytest tests/mcp/

   # Manual MCP server testing
   uv run adr-kit mcp-server  # Starts server with your latest code
   ```

3. **Verify you're using the local version**
   ```bash
   # Should show: /path/to/adr-kit/.venv/bin/adr-kit
   uv run which adr-kit

   # Should show your local path
   uv run adr-kit --version
   ```

**CRITICAL RULES:**
- ✅ **ALWAYS use `uv run adr-kit`** when testing manually in this project
- ❌ **NEVER use just `adr-kit`** - that runs the system install
- ✅ **ALWAYS edit source in `adr_kit/`** - never edit installed files
- ❌ **NEVER test using `~/.local/bin/adr-kit`** - that's the system install
- ✅ **Check `.mcp.json` uses local path** - should be `uv run adr-kit` or `.venv/bin/adr-kit`

### Testing Workflow

**Two types of tests:**

1. **Unit/Integration Tests** (standard)
   ```bash
   pytest tests/
   ```
   - Tests import from `adr_kit/` directly (editable install)
   - No MCP server running needed
   - Fast feedback loop
   - **Changes to source code immediately visible**

2. **MCP Server Tests** (requires installation)
   ```bash
   # The test suite handles this automatically
   pytest tests/test_mcp_server.py
   ```
   - Tests start actual MCP server process using local editable install
   - Uses `uv run adr-kit` command internally
   - Tests real MCP tool invocations
   - May create temporary projects in `.testenv/`
   - **Tests use your latest source code changes**

**Critical rule:** When MCP server tests fail, **always fix the source in `adr_kit/`**, never edit installed files. The editable install means changes to `adr_kit/` immediately affect the installed command.

## Key Constraint

**No external network calls in core library code** - MCP servers must work offline and cannot make unauthorized requests. Only Log4brains site generation may use network features.

## Project Structure

```
adr-kit/
├── adr_kit/          # 📦 SOURCE CODE (packaged, what you edit)
│   ├── core/         # Parsing, validation, models
│   ├── index/        # JSON/SQLite generation
│   ├── enforce/      # Lint rule generators
│   ├── mcp/          # MCP server (primary interface)
│   └── cli.py        # Typer CLI (minimal)
├── tests/            # 🧪 TEST CODE (dev only, not packaged)
│   ├── unit/         # Unit tests
│   ├── integration/  # Integration tests
│   └── mcp/          # MCP server tests
├── guide/            # 📚 PROJECT DOCUMENTATION (dev only, not packaged)
│   └── WORKFLOWS.md  # Deep dive into workflows
├── docs/adr/         # ❌ TEST FIXTURES (gitignored, created by adr-kit init)
├── schemas/          # 📦 JSON SCHEMAS (packaged)
├── scripts/          # 🔧 DEVELOPMENT TOOLS (dev only)
├── Makefile          # 🔧 DEVELOPMENT COMMANDS (dev only)
├── .agent/           # 📝 DEVELOPMENT NOTES (dev only)
├── README.md         # 📦 USER DOCS (packaged)
└── pyproject.toml    # 📦 PACKAGE CONFIG (packaged)
```

**What gets packaged for distribution:**
- ✅ `adr_kit/` - Runtime source code
- ✅ `README.md`, `LICENSE` - Documentation
- ✅ `schemas/` - JSON schemas
- ✅ `pyproject.toml` - Package metadata

**What stays local (dev only):**
- ❌ `tests/`, `scripts/`, `.agent/`, `guide/` - Development files
- ❌ `docs/adr/` - Test fixtures (gitignored)
- ❌ `Makefile` - Development commands
- ❌ All generated artifacts listed above

Configured in `pyproject.toml`:
```toml
[tool.setuptools.packages.find]
include = ["adr_kit*"]
exclude = ["tests*", "scripts*", ".agent*"]
```

## Design Principles

- MCP server is primary interface (CLI is minimal wrapper)
- Rich, actionable error messages
- Type safety with Pydantic/FastMCP
- Backward compatibility for public APIs

## Additional Documentation

- **Development workflows**: See `guide/dev/` for task workflow and git workflow guides
- Performance targets, security requirements: `docs/requirements.md`
- ADR format specification: Examples in `tests/fixtures/`