# ADR Kit

**AI-First Architectural Decision Records** - A toolkit designed for autonomous AI agents to manage ADRs in MADR format with rich contextual understanding and workflow automation.

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🤖 AI-First Design

ADR Kit is purpose-built for AI agents like **Claude Code** to autonomously manage architectural decisions. It provides "dumb but reliable" infrastructure that enforces standards and enables controlled AI agent operation through rich MCP (Model Context Protocol) tools.

## ✨ Features

- **🧠 Standardized MCP Tools** with rich contextual guidance for AI agents
- **🔄 Enforced Workflow** - Query → Create → Approve → Supersede  
- **🔍 Built-in Conflict Detection** before ADR creation
- **📝 MADR-compliant** ADR creation and validation
- **⚡ Controlled AI Operation** with clear boundaries and standards
- **📊 Reliable Indexing** with automatic relationship tracking
- **🛡️ Standards Enforcement** via automated lint rule generation
- **🌐 Consistent Documentation** with Log4brains integration

## 🚀 Quick Start for AI Agents

### Installation

```bash
# Requires Python 3.11+
pip install adr-kit
```

### Start MCP Server (Primary Interface)

```bash
# Launch MCP server for AI agent integration
adr-kit mcp-server
```

### MCP Tools Available for AI Agents

AI agents can now use these standardized tools:

- **`adr_init()`** - Initialize ADR system in repository
- **`adr_query_related()`** - Find related ADRs before making decisions  
- **`adr_create()`** - Create new ADRs with rich context
- **`adr_approve()`** - Approve proposed ADRs and handle relationships
- **`adr_supersede()`** - Replace existing decisions
- **`adr_validate()`** - Validate ADRs for compliance
- **`adr_index()`** - Generate comprehensive indexes

### Manual CLI (Legacy)

Basic commands still available for manual use:

```bash
# Initialize structure
adr-kit init

# Show available tools  
adr-kit info

# Validate existing ADRs
adr-kit validate
```

## 📚 AI Agent Workflow

### 🧠 Controlled Decision Process

ADR Kit provides standardized infrastructure that enables AI agents to manage architectural decisions through a reliable, enforced workflow:

#### 1. **Query Phase** - Conflict Detection
```python
# AI agent detects architectural decision need
# ALWAYS queries related ADRs first
adr_query_related("database migration", tags=["backend", "data"])
# Returns: Related ADRs, conflicts, recommendations
```

#### 2. **Create Phase** - Proposed ADRs  
```python  
# Creates ADR in 'proposed' status for human review
adr_create({
    "title": "Migrate from MySQL to PostgreSQL",
    "tags": ["database", "backend"],
    "deciders": ["backend-team"],
    "content": "# Context\n[AI-generated context]..."
})
# Returns: ADR-0007 in 'proposed' status
```

#### 3. **Approve Phase** - Human Review
```python
# After human approval, AI agent activates the ADR
adr_approve("ADR-0007", supersede_ids=["ADR-0003"])
# Automatically handles: status changes, relationships, index updates
```

#### 4. **Supersede Phase** - Decision Evolution
```python
# When decisions need updating
adr_supersede({
    "old_id": "ADR-0007", 
    "payload": {"title": "Enhanced Database Strategy", ...}
})
# Creates ADR-0008 that supersedes ADR-0007
```

### 🎯 Tool Semantics

Each MCP tool includes rich contextual guidance:

- **🎯 WHEN TO USE** - Clear scenarios for autonomous operation
- **🔄 WORKFLOW** - Step-by-step process guidance
- **⚡ AUTOMATICALLY HANDLES** - Behind-the-scenes operations
- **💡 TIPS & GUIDANCE** - Best practices and error recovery

### 📋 Manual Commands (Legacy)

For manual operation when needed:

```bash
# Initialize ADR structure
adr-kit init [--adr-dir docs/adr]

# Validate ADRs  
adr-kit validate [--id ADR-0001]

# Show MCP tools info
adr-kit info

# Legacy command reference  
adr-kit legacy
```

#### Generate static site
```bash
# Requires log4brains: npm install -g log4brains
adr-kit render-site
```

### Python Library

```python
from adr_kit import parse_adr_file, validate_adr, ADRStatus
from adr_kit.index import generate_adr_index
from datetime import date

# Parse an ADR file
adr = parse_adr_file("docs/adr/ADR-0001-example.md")
print(f"ADR {adr.id}: {adr.title}")

# Validate ADR
result = validate_adr(adr)
if result.is_valid:
    print("✅ ADR is valid")
else:
    for issue in result.errors:
        print(f"❌ {issue}")

# Generate index
index = generate_adr_index("docs/adr")
print(f"Indexed {len(index.entries)} ADRs")
```

### Enhanced MCP Server for AI Agents

ADR Kit's MCP server provides standardized, reliable tools that enforce proper ADR workflow and enable controlled AI operation:

```bash
# Start enhanced MCP server with rich contextual tools
adr-kit mcp-server
```

**MCP Tools with Rich Context:**

- **`adr_init()`** - Initialize ADR system with conflict detection
- **`adr_query_related()`** - Find related/conflicting ADRs before creation
- **`adr_create()`** - Create proposed ADRs with rich context
- **`adr_approve()`** - Approve ADRs with automatic relationship management
- **`adr_supersede()`** - Replace decisions with bidirectional updates
- **`adr_validate()`** - Validate with actionable error guidance
- **`adr_index()`** - Generate comprehensive indexes with filtering
- **`adr_export_lint()`** - Generate enforcement configurations
- **`adr_render_site()`** - Build static documentation

**Each tool includes:**
- 🎯 **WHEN TO USE** scenarios for autonomous operation
- 🔄 **WORKFLOW** step-by-step process guidance  
- ⚡ **AUTOMATICALLY HANDLES** behind-the-scenes operations
- 💡 **CONTEXTUAL ERROR RESPONSES** with recovery guidance

**Standards Enforcement Features:**
- Mandatory conflict detection before ADR creation
- Enforced Proposed → Accepted status workflow
- Automatic relationship management (supersedes/superseded_by)
- Rich error context with actionable guidance
- Clear boundaries and standards for controlled AI operation

## 📋 ADR Format

ADRs use MADR format with YAML front-matter:

```markdown
---
id: ADR-0001
title: Use React Query for data fetching
status: accepted
date: 2025-09-03
deciders: [frontend-team, tech-lead]
tags: [frontend, data, api]
supersedes: [ADR-0003]
superseded_by: []
---

# Context

What is the context of this decision? What problem are we trying to solve?

# Decision

What is the change that we're proposing or doing?

# Consequences

What are the positive and negative consequences of this decision?

## Positive

- Standardized data fetching
- Built-in caching and background updates
- Excellent developer experience

## Negative  

- Additional dependency
- Learning curve for team

# Alternatives

What other alternatives have been considered?

- **Native fetch()**: Simple but lacks caching
- **Axios**: Good HTTP client but no query management
- **SWR**: Similar features but smaller ecosystem
```

## 🔧 Configuration

### Validation Rules

ADR Kit enforces these validation rules:

- **Schema validation** against JSON Schema
- **ID format**: `ADR-NNNN` (4-digit zero-padded)
- **Required fields**: `id`, `title`, `status`, `date`
- **Status values**: `proposed`, `accepted`, `superseded`, `deprecated`
- **Semantic rules**: Superseded ADRs must have `superseded_by`

### Directory Structure

```
your-project/
├── docs/adr/                    # ADR files
│   ├── ADR-0001-example.md
│   ├── ADR-0002-another.md  
│   └── adr-index.json          # Generated JSON index
├── .project-index/             # Optional SQLite catalog
│   └── catalog.db
└── .eslintrc.adrs.json        # Generated lint rules
```

## 🧪 Development

### Setup

```bash
git clone https://github.com/kschlt/adr-kit.git
cd adr-kit
# Requires Python 3.11+ for FastMCP support
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/
```

## 🤖 AI Agent Integration

### Claude Code Integration

ADR Kit is optimized for **Claude Code** and similar AI agents. The MCP server provides standardized, reliable infrastructure that enforces proper ADR standards while enabling controlled autonomous operation:

```bash
# 1. Start MCP server in your project
adr-kit mcp-server

# 2. AI agents can now:
# - Detect architectural decisions in conversations
# - Query for conflicts before creating ADRs  
# - Create proposed ADRs with rich context
# - Guide humans through approval workflow
# - Handle superseding relationships automatically
```

### Autonomous Workflow Example

When an AI agent detects an architectural decision:

1. **🔍 Query**: `adr_query_related("database", ["backend"])` → Finds existing database ADRs
2. **📝 Create**: `adr_create({...})` → Creates ADR-0007 in 'proposed' status  
3. **💬 Human Review**: Agent presents ADR to human for approval
4. **✅ Approve**: `adr_approve("ADR-0007", supersede_ids=["ADR-0003"])` → Activates decision
5. **📊 Index**: Automatically updates relationships and generates indexes

### Benefits for AI Agents

- **🧠 Standardized Interface** - Clear, consistent tool signatures and behavior
- **🔄 Enforced Workflow** - Prevents invalid state transitions and ensures compliance
- **⚡ Built-in Guardrails** - Mandatory conflict detection prevents inconsistent decisions  
- **💡 Rich Error Context** - Detailed feedback enables autonomous error recovery
- **📋 Automatic Standards** - Handles complex relationship logic reliably

## 🔗 Integration

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: adr-validate
        name: Validate ADRs
        entry: adr-kit validate
        language: system
        pass_filenames: false
```

### GitHub Actions

```yaml
name: ADR Validation
on: [pull_request, push]

jobs:
  validate-adrs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install adr-kit
      - run: adr-kit validate
      - run: adr-kit index --out docs/adr/adr-index.json
```

### Enforcement Examples

ADR Kit can generate lint rules from your architectural decisions:

**ESLint example** - Ban deprecated libraries:
```json
{
  "rules": {
    "no-restricted-imports": [
      "error", 
      {
        "paths": [{
          "name": "moment", 
          "message": "Use date-fns instead (ADR-0042)"
        }]
      }
    ]
  }
}
```

**Ruff example** - Enforce Python standards:
```toml
[tool.ruff]
select = ["E", "W", "F", "UP"]  # Based on ADR decisions
```

## 📖 Examples

See the `docs/adr/` directory for example ADRs:

- [ADR-0001: Use Python and FastAPI for the ADR Kit backend](docs/adr/ADR-0001-sample.md)


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [MADR](https://adr.github.io/madr/) for the ADR format specification
- [Log4brains](https://github.com/thomvaill/log4brains) for static site generation
- [Pydantic](https://pydantic.dev/) for data validation
- [Typer](https://typer.tiangolo.com/) for the CLI framework

## 📞 Support

- 📚 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/kschlt/adr-kit/issues)

---

Built with ❤️ for better architectural decision making.