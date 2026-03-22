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

## Recent Additions

**Decision Quality Guidance (Mar 2026)**
Added a two-phase quality assessment system for ADR creation. Phase 1: structured guidance (6 reasoning steps, quality criteria, anti-patterns) provided to the agent before drafting. Phase 2: quality gate runs before file creation — scoring 6 dimensions (specificity, balance, context, constraints, alternatives, completeness) with A–F grading. ADRs below B-grade threshold trigger a correction loop: the agent revises and resubmits without creating partial files.

**Integration Test Architecture (Mar 2026)**
Replaced ~308 lines of regex extraction with a reasoning-agent promptlet architecture. Root cause: regex patterns on large inputs caused exponential backtracking. Architectural shift: agents reason about policies from their own decision text rather than ADR Kit extracting them via pattern matching. Reduced test suite runtime from hanging to 0.4s.

**Expanded Policy Types (Mar 2026)**
Added Pydantic models and JSON schema for pattern policies, architecture boundary rules, and config enforcement. These are fully defined and validated but not yet generating lint output — unblocked by the enforcement pipeline work above.

**AI Warning Extraction (Mar 2026)**
ADR consequences containing warnings are now extracted and surfaced by `adr_planning_context` for relevant decisions. Reduces missed constraints from ADRs that document risks in the consequences section.

**Policy Suggestion Engine (Feb 2026)**
`adr_create` now auto-detects policy candidates from the decision text (import restrictions, patterns, architecture rules) and returns a structured promptlet guiding the agent through policy construction. Agents no longer need to infer the policy schema from scratch.
