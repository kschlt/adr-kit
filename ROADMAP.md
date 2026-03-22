# ADR Kit — Roadmap

This document tracks what's planned, in what order, and why. Priorities reflect what most directly unblocks the core value of ADR Kit.

→ For current capabilities and limitations, see [README.md](README.md#current-status)
→ For technical implementation details, see [TECHNICAL.md](TECHNICAL.md)

---

## Up Next

### Staged Enforcement

**Why:** Import restrictions currently either block immediately or warn. Real projects need a transition period — warn on existing violations, block new ones. Without staged enforcement, teams can't adopt ADR Kit on a codebase that already has violations.

**What:** A warn → block enforcement pipeline with thresholds, so teams can clean up existing violations incrementally without being blocked from day one.

### Complete Enforcement Loop

**Why:** Pattern policies, architecture boundaries, and config enforcement are fully modelled in the schema but don't yet generate lint rules. The enforcement story is incomplete until all policy types produce real output.

**What:** Extend the guardrail generator to cover pattern rules (regex), architecture layer boundaries, and tool configuration enforcement (tsconfig, ruff/mypy settings).

### DX Polish

**Why:** Several rough edges in the day-to-day workflow slow down adoption: error messages that don't suggest next steps, missing `--adr-dir` defaults, gaps in CLI output.

**What:** Targeted improvements to error messages, CLI UX, and feedback quality across the MCP tools.

---

## Later

- **Semantic search as primary conflict detection** — Currently keyword-based. Semantic search (sentence-transformers) is implemented but used as optional fallback. Making it primary improves conflict detection for conceptually related ADRs that don't share keywords.
- **ADR templates** — Common decision types (library choice, architecture pattern, API design) as starting templates to reduce ADR creation friction.
- **Log4brains integration** — Static site generation for browsing ADRs with history and status tracking.
- **Import-linter support** — Python enforcement via import-linter in addition to Ruff, for more expressive architecture boundary rules.

---

For release history, see [CHANGELOG.md](CHANGELOG.md).
