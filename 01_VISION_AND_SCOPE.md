# ADR Kit — Vision & Scope

## Vision
Provide a **standardized, repo-native** way to record, publish, and enforce **Architectural Decision Records (ADRs)**.

ADRs become the **architectural memory**: why we chose FastAPI over Flask, why we use React Query instead of SWR, etc.
The kit ensures ADRs are both **readable** (Markdown) and **actionable** (validated, enforceable, agent-visible).

## Goals
- Use MADR format for ADRs (Markdown with front-matter).
- Support Log4brains to publish ADRs as a static site.
- Supersede/replace logic: new ADRs mark old ones as deprecated.
- Index ADRs as JSON/SQLite for quick access and agent consumption.
- Generate lint/CI rules from ADRs (e.g., banned imports).
- Expose ADRs via MCP tools so coding agents follow architectural guardrails.

## Non-Goals
- Replace human architecture reviews entirely.
- Define *all* best practices (teams still need discussions).
- Serve as a project management tool (we integrate, not replace).

## Scope
- Python 3.12 library (`adr_kit/`).
- CLI (`adr-kit`).
- MCP server (`python -m adr_kit.mcp.server`).
- Schemas + validation logic.
- Enforcement via generated lint configs.
- CI/pre-commit integration.
