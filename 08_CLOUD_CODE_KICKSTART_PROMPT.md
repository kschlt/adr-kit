# Kickstart Prompt for Claude Code / Cursor

You are my **Repo Sub-Agent Builder**. Use the provided ADR Kit kickoff docs to scaffold a Python library
named **adr-kit** with CLI and an MCP server.

## Objectives
- Implement `adr_kit/` as a Python package (Python 3.12).
- Provide a CLI `adr-kit` using Typer or Click.
- Implement JSON Schema validation (see `schemas/adr.schema.json`) and semantic rules.
- Emit `docs/adr/adr-index.json` and optional `.project-index/catalog.db` (SQLite).
- Implement MCP server exposing tools described in `05_MCP_SPEC.md`.
- Add lint rule generators (ESLint, Ruff, import-linter).
- Provide Log4brains integration for static site rendering.
- Provide unit tests (pytest).

## Constraints
- No external network calls in core logic (except Log4brains binary invocation).
- Clear error messages for invalid ADRs.
- ADR supersede logic must auto-update old/new ADRs consistently.

## Steps
1) Read all kickoff files (Vision, Specs, Schemas, CLI, MCP, CI).
2) Propose project layout + `pyproject.toml`.
3) Implement modules:
   - `adr_kit/core/model.py` (pydantic model)
   - `adr_kit/core/parse.py` (front-matter + markdown)
   - `adr_kit/core/validate.py` (jsonschema + semantic rules)
   - `adr_kit/index/json_index.py` + `index/sqlite_index.py`
   - `adr_kit/cli.py`
   - `adr_kit/mcp/server.py`
   - `adr_kit/enforce/eslint.py` / `ruff.py`
4) Add tests under `tests/`.
5) Generate a starter ADR in `docs/adr/ADR-0001-sample.md`.
6) Run `adr-kit validate` and `adr-kit index --out docs/adr/adr-index.json` successfully.
7) Print commands to run locally.

## Deliverables
- All source files.
- Docstrings summarizing design decisions.
