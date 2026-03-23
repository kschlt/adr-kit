# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `CHANGELOG.md` with full version history
- `TECHNICAL.md` with implementation details for each layer
- `CONTRIBUTING.md` with development environment setup
- `SECURITY.md` with supported versions and vulnerability reporting
- Release CI workflow (`.github/workflows/release.yml`) with PyPI Trusted Publishing and automated GitHub Release creation
- "Releasing" section in `CLAUDE.md` documenting the tag-based release process
- Staged enforcement pipeline: `adr-kit enforce <level>` validates ADR policies at commit, push, and CI stages
- `adr-kit setup-enforcement` command for configuring git hooks
- `adr-kit enforce-status` command for viewing enforcement configuration
- `--with-enforcement` flag on `adr-kit init` for one-step git hook setup
- Enforcement classifier maps ADR policy types to enforcement levels (commit/push/CI)
- `StagedValidator` runs classified checks against staged, changed, or all files per enforcement level
- `HookGenerator` creates pre-commit and pre-push git hooks with managed sections (idempotent, non-interfering)
- JSON enforcement reporter (`--format json`) with AI-readable `EnforcementReport` schema
- Architecture layer boundary enforcement at push level
- Standalone validation script generator (`adr-kit generate-scripts`) — creates stdlib-only Python scripts from ADR policies with `--quick` and `--full` modes
- CI workflow generator (`adr-kit generate-ci`) — creates GitHub Actions YAML for ADR enforcement on pull requests
- Approval workflow auto-generates validation scripts for newly approved ADRs
- Importance-weighted ranking in `adr_planning_context` — centrality, policy richness, tag breadth, and status penalties applied as multiplicative boost on relevance scores
- Individual ADR MCP resources (`adr://{adr_id}`) for progressive disclosure — agents fetch full ADR content on demand via `resource_uri` field

### Changed
- README rewritten for user focus: problem statement, quick start, tool reference, FAQ
- `ROADMAP.md` "Recent Additions" section replaced with link to this changelog
- CI workflow consolidated from 13 to 8 checks: dedicated lint job (blocks tests), trimmed test matrix to `(ubuntu + macOS) × (3.11–3.13) + ubuntu-only 3.10`

### Fixed
- `pyproject.toml` project URLs updated from placeholder `your-org` to correct `kschlt`
- Added Python 3.13 classifier to package metadata
- `mcp-health` now shows detected version at startup and joins update thread for in-order notification

### Removed
- `PolicyPatternExtractor` and regex-based policy extraction — replaced by agent reasoning approach

---

## [0.2.7] - 2026-02-10

### Added
- Decision quality guidance system: two-phase ADR creation with structured reasoning steps, quality criteria, and anti-pattern examples
- Pre-validation quality gate: quality check runs before file creation, enabling correction loop without partial files — ADRs below B-grade threshold (75 pts) return `REQUIRES_ACTION` with improvement guidance
- `skip_quality_gate` parameter on `adr_create` for test overrides
- Pattern policy models (`PatternRule`, `PatternPolicy`) with JSON schema
- Architecture policy models (`LayerBoundaryRule`, `RequiredStructure`, `ArchitecturePolicy`) with JSON schema
- Config enforcement models (`TypeScriptConfig`, `PythonConfig`, `ConfigEnforcementPolicy`) with JSON schema
- `adr_create` policy suggestion engine: auto-detects policy candidates from decision text and returns a structured promptlet guiding policy construction
- AI warning extraction in `adr_planning_context`: consequences containing warnings are surfaced for relevant decisions
- Domain filtering in `adr_planning_context` for 60–80% context reduction

### Changed
- Integration test architecture: replaced ~308 lines of regex extraction with a reasoning-agent promptlet. Agents reason about policies from their own decision text rather than ADR Kit extracting via pattern matching
- MCP tool documentation moved from static docstrings to just-in-time response payloads (context-efficient ping-pong pattern)

### Fixed
- `adr_create` content generation simplified to prevent empty sections

---

## [0.2.6] - 2025-12-15

### Added
- Policy validation warnings for ADR creation — front-matter policy blocks are validated on `adr_create`
- Constraint extraction guide and example ADR fixtures
- MCP server configuration for development (`.mcp.json`)
- Middleware to fix stringified JSON parameters from buggy MCP clients

### Changed
- Project structure refactored and developer documentation improved
- Version read dynamically from package metadata

### Fixed
- CLI version detection with semantic comparison
- `uv run` prefix added to all Makefile tool commands

---

## [0.2.5] - 2025-11-01

### Added
- Complete MCP server redesign with clean entry points and comprehensive tests
- Strict mypy type safety configuration
- Full test suite reorganization (unit / integration / MCP server)
- Python 3.10 compatibility fixes (`datetime.timezone.utc`)

### Changed
- Migrated from pipx to uv for package installation
- CI Python version matrix updated to match package requirements (`3.10+`)
- `setup-uv` action upgraded from v4 to v6

### Fixed
- MCP server startup `TypeError` (Rich console parameter)
- MCP server `next_steps` type compatibility
- Windows-specific test failures
- All deprecation warnings eliminated

---

## [0.1.0] - 2025-09-03

Initial release.

- 6 MCP tools: `adr_analyze_project`, `adr_preflight`, `adr_create`, `adr_approve`, `adr_supersede`, `adr_planning_context`
- MADR format with optional `policy` block for enforcement
- ESLint and Ruff rule generation from import policies
- Selective context loading by task relevance
- Local semantic search via sentence-transformers and FAISS
- `adr-kit init`, `setup-cursor`, `setup-claude` CLI commands

[Unreleased]: https://github.com/kschlt/adr-kit/compare/v0.2.7...HEAD
[0.2.7]: https://github.com/kschlt/adr-kit/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/kschlt/adr-kit/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/kschlt/adr-kit/compare/v0.1.0...v0.2.5
[0.1.0]: https://github.com/kschlt/adr-kit/releases/tag/v0.1.0
