# ADR Kit — Technical Reference

This document explains how each layer of ADR Kit works in detail, with concrete examples, configuration reference, and operational notes.

→ For a product overview and quick start, see [README.md](README.md)
→ For what's planned, see [ROADMAP.md](ROADMAP.md)

---

## Layer 1: ADR Lifecycle Management

### The Problem It Solves

Architectural decisions emerge continuously during development — when you pick a library, define a pattern, or decide what to avoid. Without active management, they're never documented, and when they need to evolve, there's no historical record of what was decided before.

### How It Works

During every chat session, the AI checks: "Does this choice have architectural relevance?" If yes, it calls `adr_preflight` to see if an ADR exists. If not, it proposes one via `adr_create`. Once you approve, the ADR is active and enforced.

**Proposing a new ADR:**

```
You: "Let's use FastAPI for the backend API"
AI: [adr_preflight({choice: "fastapi"})] → REQUIRES_ADR
AI: [adr_create({decision: "Use FastAPI...", context: "..."})]
AI: "Here's ADR-0001. Review it?"
You: "Approved"
AI: [adr_approve({id: "ADR-0001"})] → Enforcement active
```

### Decision Quality Gate

Vague decisions can't be enforced. ADR Kit evaluates quality before creating any file:

```
❌ "Use a modern framework with good performance"
   → Rejected: specify exact framework name and version

✅ "Use FastAPI 0.100+. Don't use Flask or Django."
   → Accepted: specific, has explicit constraints
```

**What gets evaluated:**
- **Specificity**: Are technologies named concretely?
- **Trade-offs**: Are both pros and cons documented?
- **Context**: Why is this decision needed now?
- **Constraints**: Are there explicit "don't use X" policies?
- **Alternatives**: What options were rejected and why?

If the quality score is below threshold, the agent receives structured feedback and revises the decision before any file is created — no partial ADR files accumulate in your repository.

### Superseding Decisions

ADRs are immutable records. When a decision needs to change, you supersede it — the old ADR stays as historical record.

```
You: "We need axios for this specific external API integration"
AI: [adr_preflight({choice: "axios"})] → BLOCKED (conflicts with ADR-0003: Use React Query)
AI: "Two options:
     A) Find a React Query solution for this case
     B) Supersede ADR-0003 to allow axios for external APIs"
You: "Option B"
AI: [adr_supersede({supersedes: "ADR-0003", decision: "Allow axios for external APIs..."})]
AI: "ADR-0015 created. ADR-0003 marked superseded.
     Note: 3 files use React Query for external calls — they'd need migrating."
```

Superseding always surfaces migration implications — the AI identifies what existing code conflicts with the new decision.

---

## Layer 2: Context Loading

### The Problem It Solves

AI agents can't remember decisions from previous conversations. Loading all ADRs upfront wastes context window before any real work begins.

### How It Works

Before implementing a feature, the AI calls `adr_planning_context` with the current task description. ADR Kit filters by relevance and returns only the decisions that apply:

```
Task: "Implement user authentication"
Domain: backend, security

ADR Kit returns:
✅ ADR-0005: Use Auth0 for Authentication
   - Constraint: Don't implement custom auth
   - Warning: ⚠️ Rate limiting required on auth endpoints

✅ ADR-0008: JWT Token Structure
   - Constraint: Access tokens expire in 1 hour
   - Constraint: Refresh tokens stored in httpOnly cookies

Filtered out (not relevant):
❌ ADR-0001: React Query (frontend)
❌ ADR-0012: CSS-in-JS (styling)
```

**How filtering works:** Primary method is keyword and tag matching. Semantic search (sentence-transformers, `all-MiniLM-L6-v2`) is available as an enhancement for finding conceptually related ADRs that don't share keywords. AI warnings from ADR consequences are surfaced for any moderately relevant decision (relevance ≥ 0.4).

---

## Layer 3: Enforcement

### The Problem It Solves

Even with relevant context loaded, agents make mistakes or skip constraints under time pressure. Enforcement works independently of context loading — violations are caught regardless.

### How It Works

Approved ADRs with a `policy` block automatically generate lint rules:

```yaml
# ADR-0003: Use React Query for data fetching
policy:
  imports:
    prefer: [react-query, @tanstack/react-query]
    disallow: [axios]
```

Generates `.eslintrc.adrs.json`:

```json
{
  "rules": {
    "no-restricted-imports": ["error", {
      "paths": [{
        "name": "axios",
        "message": "Use React Query instead (ADR-0003). To change this decision, supersede the ADR."
      }]
    }]
  }
}
```

And for Python, updates `pyproject.toml` under `[tool.ruff]`.

**The feedback loop:** Violations aren't dead ends. The error message tells the developer (or agent) which ADR is being violated — feeding back into lifecycle management. Either fix the code to comply, or supersede the ADR if the decision needs to evolve.

### Staged Enforcement

Beyond lint rules, ADR Kit enforces policies at three stages during the development workflow:

| Stage | When | Budget | What Runs |
|---|---|---|---|
| **Pre-Commit** | `git commit` | <5s | Import restrictions, syntax patterns (staged files only) |
| **Pre-Push** | `git push` | <15s | Architecture layer boundaries (changed files) |
| **CI** | Pull request | <2min | All checks comprehensively (safety net) |

Set up enforcement with `adr-kit init --with-enforcement` or `adr-kit setup-enforcement`. The hooks are idempotent and non-interfering — they append managed sections to existing hooks without overwriting.

Use `adr-kit enforce <level> --format json` to get an AI-readable `EnforcementReport` with structured violation data for agents and CI pipelines.

### Standalone Scripts and CI Generation

For teams that want enforcement without a runtime dependency on ADR Kit:

- **`adr-kit generate-scripts`** creates stdlib-only Python validation scripts from ADR policies. Scripts support `--quick` (pre-push) and `--full` (CI) modes and output `EnforcementReport` JSON.
- **`adr-kit generate-ci`** creates a GitHub Actions workflow YAML that runs enforcement checks on pull requests.

Both are generated automatically when an ADR is approved.

### What's Automatic on Approval

When you call `adr_approve`, this happens without any manual steps:

1. ADR status updated to `accepted`
2. Constraints contract rebuilt
3. ESLint rules generated (if JS/TS policy present)
4. Ruff rules generated (if Python policy present)
5. ADR index updated
6. Codebase validated against new constraints
7. Standalone validation scripts generated (if ADR has enforceable policies)
8. Git hooks updated (if enforcement is configured)

---

## Policy Schema

The `policy` block in ADR front-matter supports five enforcement types:

| Type | What It Enforces | Status |
|------|-----------------|--------|
| `imports` | Library restrictions (JS/TS) | Active |
| `python` | Module restrictions (Python) | Active |
| `patterns` | Code pattern rules with regex | Enforced via generated scripts; no native linter rules yet |
| `architecture` | Layer boundaries + required structure | Enforced at push level + generated scripts |
| `config_enforcement` | Tool configuration (tsconfig, ruff, mypy) | Defined, not yet enforced |

<details>
<summary><b>Full policy schema reference</b></summary>

```yaml
policy:
  imports:
    disallow: [string]           # Libraries/packages to ban (JS/TS)
    prefer: [string]             # Recommended alternatives

  python:
    disallow_imports: [string]   # Python module bans

  patterns:
    patterns:
      rule_name:                 # Named pattern rules
        description: string
        language: string         # python, typescript, etc.
        rule: string | object    # Regex or structured query
        severity: error | warning | info
        autofix: boolean

  architecture:
    layer_boundaries:
      - rule: string             # "layer -> layer" (e.g., "ui -> database")
        check: string            # Path pattern (glob)
        action: block | warn
        message: string
    required_structure:
      - path: string             # Required path (glob supported)
        description: string

  config_enforcement:
    typescript:
      tsconfig: object           # Required tsconfig.json settings
    python:
      ruff: object               # Required Ruff configuration
      mypy: object               # Required mypy configuration

  rationales: [string]           # Human-readable reasons for the policies
```

</details>

See [tests/fixtures/examples/](tests/fixtures/examples/) for complete ADR examples with policy blocks.

---

## Directory Structure

After `adr-kit init`, your project looks like:

```
your-project/
├── docs/adr/                      # ADR files
│   ├── ADR-0001-react-query.md
│   ├── ADR-0002-typescript.md
│   └── adr-index.json            # Auto-generated — don't edit
├── .adr-kit/
│   └── constraints_accepted.json  # Merged policies — auto-generated
├── .project-index/
│   └── adr-vectors/              # Semantic search embeddings
├── .eslintrc.adrs.json           # Auto-generated lint rules — don't edit
└── pyproject.toml                # [tool.ruff] section managed by ADR Kit
```

Files in `.adr-kit/`, `.project-index/`, and `.eslintrc.adrs.json` are auto-generated. Add them to `.gitignore` or commit them — both are valid depending on your workflow.

---

## Manual CLI Usage

Most users interact with ADR Kit through AI agents. The CLI exists for manual operations and CI/CD:

```bash
# Validation
adr-kit validate                # Validate all ADRs
adr-kit validate --id ADR-0001  # Validate a specific ADR

# Policy management
adr-kit contract-build          # Rebuild constraints contract
adr-kit contract-status         # View current contract

# Lint rule management
adr-kit guardrail-apply         # Apply lint rules manually
adr-kit guardrail-status        # Check guardrail status
adr-kit preflight postgresql    # Manual preflight check

# Staged enforcement
adr-kit enforce commit          # Run commit-level checks (staged files)
adr-kit enforce push            # Run push-level checks (changed files)
adr-kit enforce ci              # Run CI-level checks (all files)
adr-kit enforce ci --format json  # JSON output for agents/CI

# Enforcement setup
adr-kit setup-enforcement       # Configure git hooks
adr-kit enforce-status          # Show enforcement configuration

# Script & CI generation
adr-kit generate-scripts        # Generate standalone validation scripts
adr-kit generate-ci             # Generate GitHub Actions workflow

# Maintenance
adr-kit mcp-health              # Test MCP server connectivity
adr-kit update                  # Check for updates
```

---

## CI/CD Integration

The fastest way to set up CI enforcement is to generate a workflow automatically:

```bash
adr-kit generate-ci    # Creates .github/workflows/adr-enforcement.yml
```

The generated workflow runs `adr-kit enforce ci --format json` on pull requests and fails on violations.

<details>
<summary><b>Manual CI setup (alternative)</b></summary>

```yaml
# .github/workflows/adr.yml
name: ADR Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Install ADR Kit
        run: uv tool install adr-kit

      - name: Validate ADRs
        run: adr-kit validate

      - name: Enforce policies
        run: adr-kit enforce ci --format json

      - name: Check lint rules are current
        run: git diff --exit-code .eslintrc.adrs.json
```

</details>

---

## Health Check

After installation, verify the MCP server is working:

```bash
adr-kit mcp-health
```

Expected output:
- ✅ FastMCP dependency: OK
- ✅ MCP server: OK
- ✅ Workflow backend system: OK
- 📡 6 MCP Tools available

---

## Project Status

ADR Kit is under active development. Test coverage: 309 tests (220 unit + 66 integration + 23 other) across the core workflows, MCP server integration, quality assessment, and enforcement systems.

See [ROADMAP.md](ROADMAP.md) for what's planned and [CONTRIBUTING.md](CONTRIBUTING.md) to contribute.
