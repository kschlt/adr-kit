# ADR Kit — Architectural Decision Records (Kickoff Pack)

Date: 2025-09-03

This kickoff pack bootstraps **ADR Kit**: a reusable library + CLI + MCP server to manage
**Architectural Decision Records (ADRs)** in the MADR format, enforce them via lint/CI, and expose them
to coding agents (Claude Code, Cursor) for architectural guardrails.

**Core ideas**
- Human-friendly Markdown ADRs → machine-friendly JSON/SQLite index for queries & enforcement.
- Standard format: MADR (Markdown ADRs) + Log4brains compatibility.
- Enforce decisions in code (generate ESLint/Ruff/import-linter configs).
- Provide CLI and MCP tools for create/validate/index/supersede operations.
- Integrate with CI and pre-commit for continuous enforcement.
- Browsable web UI via Log4brains (or similar).

**What’s included**
- Vision & Scope
- Functional & Non-functional requirements
- File formats (MADR + JSON Schema)
- CLI & MCP specs
- Enforcement & CI examples
- Example ADRs
- Kickstart prompt for Claude Code

**See also**
- `01_VISION_AND_SCOPE.md`
- `02_SPEC_FUNCTIONAL_NONFUNCTIONAL.md`
- `03_FORMAT_AND_SCHEMAS.md`
- `04_CLI_SPEC.md`
- `05_MCP_SPEC.md`
- `06_ENFORCEMENT_AND_CI.md`
- `07_EXAMPLES.md`
- `08_CLOUD_CODE_KICKSTART_PROMPT.md`
