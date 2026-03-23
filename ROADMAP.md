# ADR Kit — Roadmap

This document tracks what's planned, in what order, and why. Priorities reflect what most directly unblocks the core value of ADR Kit.

> For current capabilities and limitations, see [README.md](README.md#current-status)
> For technical implementation details, see [TECHNICAL.md](TECHNICAL.md)

---

## Up Next

### Pattern Enforcement via Linter Adapters

**Why:** Pattern policies currently generate standalone validation scripts but don't produce native ESLint or Ruff rules. Native linter integration gives IDE-level feedback — developers see violations inline without running a separate script.

**What:** Extend the ESLint and Ruff adapters to emit rules for the `patterns` policy type (regex-based code pattern matching with per-language support).

### Config Enforcement

**Why:** Config enforcement models exist (`TypeScriptConfig`, `PythonConfig`) but no validation logic runs at any level. Teams can define required tsconfig/ruff/mypy settings in ADR policies, but violations aren't caught.

**What:** Implement validators that check `tsconfig.json`, `ruff.toml`, and `mypy.ini`/`pyproject.toml` settings against `config_enforcement` policies. Wire into the staged enforcement pipeline at CI level.

---

## Later

- **Semantic search as primary conflict detection** — Currently keyword-based. Semantic search (sentence-transformers) is implemented but used as optional enhancement. Making it primary improves conflict detection for conceptually related ADRs that don't share keywords.
- **ADR templates** — Common decision types (library choice, architecture pattern, API design) as starting templates to reduce ADR creation friction.
- **Log4brains integration** — Static site generation for browsing ADRs with history and status tracking.
- **Import-linter support** — Python enforcement via import-linter in addition to Ruff, for more expressive architecture boundary rules.

---

## Recently Completed

### Staged Enforcement

Enforcement pipeline with three stages: pre-commit (import checks on staged files, <5s), pre-push (architecture boundaries on changed files, <15s), and CI (comprehensive validation, <2min). Git hooks via `adr-kit init --with-enforcement` or `adr-kit setup-enforcement`. JSON reporter for agent/CI consumption.

### Complete Enforcement Loop

Architecture layer boundary enforcement at push level. Standalone validation script generator (`generate-scripts`) creates stdlib-only Python scripts for all policy types. CI workflow generator (`generate-ci`) creates GitHub Actions YAML. Approval workflow auto-generates scripts.

### DX Polish

Importance-weighted ranking in `adr_planning_context` for better ADR relevance scoring. Individual ADR MCP resources (`adr://{adr_id}`) for progressive disclosure. Health check version detection fix.

---

For release history, see [CHANGELOG.md](CHANGELOG.md).
