# ADR Kit

Keep AI agents architecturally consistent.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## The Problem

Each new chat with your AI agent (Cursor, Claude Code, Copilot) starts with blank context:

- **Monday**: "Use React Query" → implements with React Query
- **Wednesday**: New chat → uses axios (no memory of Monday)
- **Friday**: Different conversation → uses fetch() again

The standard solution — Architectural Decision Records (ADRs) — doesn't transfer directly. An agent can't read all your ADRs upfront without burning the context window before the actual work begins. And most projects don't have ADRs at all, because manual maintenance was too much overhead.

**ADR Kit bridges the gap**: AI agents create and maintain ADRs automatically. Relevant decisions are loaded into context selectively, only when needed. Violations are caught by lint rules generated directly from your ADRs.

## How It Works

ADR Kit operates in three layers:

**1. Lifecycle Management** — AI detects when a decision has architectural relevance, checks for existing ADRs, and either applies them or proposes a new one. Quality gate: vague decisions ("use a modern framework") are rejected before any file is created. When a decision evolves, the old ADR is superseded — never edited — preserving the full history.

**2. Context at the Right Time** — Before implementing a feature, ADR Kit surfaces only the relevant decisions. Out of 50 ADRs, 3–5 relevant ones reach the agent's context. Right information, right time, without flooding the context window.

**3. Enforcement** — Approved ADRs automatically generate ESLint and Ruff lint rules. Violations are blocked with a clear reference to the decision they violate, triggering a choice: fix the code, or supersede the ADR if the decision needs to evolve.

## Quick Start

### Install

```bash
uv tool install adr-kit
```

Or try without installing:

```bash
uvx adr-kit --help
```

### Connect to Your AI Agent

```bash
cd your-project
adr-kit init           # Creates docs/adr/
adr-kit setup-cursor   # or: adr-kit setup-claude
```

This connects ADR Kit to your AI agent via MCP.

### Start Working

ADR Kit works in every chat session, whether your project is new or established:

```
You: "Let's use FastAPI for the backend API"
AI: [Calls adr_preflight({choice: "fastapi"})]
AI: "No existing ADR. I'll propose one."
AI: [Calls adr_create()] → Proposes ADR-0001 (status: proposed)
AI: "Here's the proposed ADR. Review it?"
You: "Looks good, approve it"
AI: [Calls adr_approve()] → Enforcement now active
```

<details>
<summary><b>Starting with an existing codebase?</b></summary>

Let the AI discover the architectural decisions already baked into your code:

```
You: "Analyze my project for architectural decisions"
AI: [Calls adr_analyze_project()]
AI: "You're using React, TypeScript, PostgreSQL, Docker."
AI: "Found a conflict: PostgreSQL in 80% of code, MySQL in the legacy module.
     Document both, or propose migrating to consistent PostgreSQL usage?"
```

Review and approve the proposed ADRs. Your implicit decisions are now explicit, documented, and enforced.

</details>

## The 6 MCP Tools

AI agents interact with ADR Kit through 6 tools:

| Tool | When AI Uses It | What It Does |
|------|-----------------|--------------|
| `adr_analyze_project` | Starting with existing codebase | Detects tech stack, proposes ADRs for discovered decisions |
| `adr_preflight` | Before making a technical choice | Returns ALLOWED / REQUIRES_ADR / BLOCKED |
| `adr_create` | Documenting a decision | Proposes ADR with quality validation and conflict detection |
| `adr_approve` | After your review | Activates enforcement: generates lint rules, updates indexes |
| `adr_supersede` | Replacing an existing decision | Creates new ADR, marks old as superseded |
| `adr_planning_context` | Before implementing a feature | Returns relevant ADRs filtered by task and domain |

## ADR Format

ADRs use [MADR format](https://adr.github.io/madr/) with an optional `policy` block for enforcement:

```markdown
---
id: ADR-0001
title: Use React Query for data fetching
status: proposed
date: 2025-10-01
tags: [frontend, data-fetching]
policy:
  imports:
    prefer: [react-query, @tanstack/react-query]
    disallow: [axios]
---

## Context
Custom data fetching is scattered across components...

## Decision
Use React Query for all data fetching. Don't use axios directly.

## Consequences
### Positive
- Standardized caching, built-in loading states
### Negative
- Additional dependency, learning curve
```

After approval, the `policy` block automatically generates lint rules that block violations:

```javascript
import axios from 'axios';  // ❌ ESLint: Use React Query instead (ADR-0001)
```

## FAQ

**Q: What languages are supported?**
A: Lifecycle management and context loading are language-agnostic. Enforcement currently generates ESLint rules (JavaScript/TypeScript) and Ruff rules (Python). Other languages require manual policy application for now.

**Q: Can I use this with existing ADRs?**
A: Yes. ADR Kit reads standard MADR format. Add a `policy:` block to existing ADRs to enable enforcement.

**Q: Does this work offline?**
A: Yes. No external API calls. Semantic search uses local models. Your ADRs and policies stay on your machine.

**Q: What if a decision can't be expressed as a lint rule?**
A: Not all decisions map to lint rules — "use microservices" can't become an ESLint rule. These decisions still benefit from lifecycle management and context loading (layers 1 and 2). Enforcement only applies to decisions with concrete, checkable constraints: library choices, coding patterns, file structure.

**Q: Does this replace code reviews?**
A: No. ADR Kit catches architectural violations automatically, but code reviews catch logic errors, security issues, and design problems that lint rules can't detect.

## Current Status

**Working today:**
- Selective context loading by task relevance (`adr_planning_context`)
- Implicit decision discovery in existing codebases (`adr_analyze_project`)
- ADR creation with quality gate — rejects vague decisions before file creation
- ESLint and Ruff rule generation from import policies

**Current limitations:**
- Enforcement is linter-based only. Pattern policies, architecture boundaries, and config enforcement are modelled but not yet active.
- Language support: JavaScript/TypeScript (ESLint) and Python (Ruff). Other languages require manual policy application.

See [ROADMAP.md](ROADMAP.md) for what's planned and why.

## Learn More

- [TECHNICAL.md](TECHNICAL.md) — How each layer works in detail, with examples
- [ROADMAP.md](ROADMAP.md) — What's coming and in what order
- [CHANGELOG.md](CHANGELOG.md) — Release history
- [CONTRIBUTING.md](CONTRIBUTING.md) — Set up the dev environment
- [MADR Format](https://adr.github.io/madr/) — The ADR specification ADR Kit builds on
- [MCP Protocol](https://modelcontextprotocol.io) — How AI agents connect to external tools

---

MIT License — see [LICENSE](LICENSE)
