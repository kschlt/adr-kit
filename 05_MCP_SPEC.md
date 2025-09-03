# ADR Kit — MCP Server Spec

Server entry: `python -m adr_kit.mcp.server`

Tools:
- `adr.create(payload)` → returns created ID + path
- `adr.supersede({old_id, payload})` → marks old ADR as superseded, creates new ADR
- `adr.validate({id?})` → diagnostics
- `adr.index({filters?})` → list of ADRs
- `adr.exportLintConfig({framework})` → ESLint/Ruff/import-linter config
- `adr.renderSite()` → builds static site via Log4brains

Resources:
- `adr.index.json` (machine-readable index)

Implementation:
- Use **FastMCP** to expose tools/resources.
- Log4brains CLI integration for `renderSite`.
