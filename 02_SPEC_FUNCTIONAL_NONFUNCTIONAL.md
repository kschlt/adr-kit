# ADR Kit — Functional & Non-functional Requirements

## Functional Requirements
1. **Create ADRs**
   - From MADR template (Markdown front-matter + sections).
2. **Validate ADRs**
   - Schema validation: required fields (`id`, `title`, `status`, etc.).
   - Semantic rules: if `status=superseded`, must have `superseded_by`.
3. **Index ADRs**
   - Emit `docs/adr/adr-index.json`.
   - Optional SQLite `.project-index/catalog.db` (tables: `adr`, `adr_links`).
4. **Supersede ADRs**
   - New ADR auto-updates old ADR’s status.
5. **Publish ADRs**
   - Integrate with Log4brains to render web UI.
6. **Enforce Decisions**
   - Generate ESLint configs (ban disallowed libs).
   - Generate Ruff/import-linter rules for Python code.
7. **Search/Query**
   - Filter ADRs by status, tags, deciders.
8. **MCP Tools**
   - `adr.create`, `adr.supersede`, `adr.validate`, `adr.index`, `adr.exportLintConfig`, `adr.renderSite`.

## Non-Functional Requirements
- **Language**: Python 3.12+
- **Perf**: 500 ADRs validated in < 1s.
- **DX**: Friendly errors, cross-links to superseded ADRs.
- **Extensibility**: Allow project-specific lint rule generators.
