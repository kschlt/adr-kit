# ADR Kit

**AI-First Architectural Decision Records** - A production-ready toolkit designed for AI agents to manage ADRs with sophisticated workflow automation and policy enforcement.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-comprehensive-green)](#testing--validation)

## What is ADR Kit?

ADR Kit transforms architectural decisions into **enforceable code policies** through a sophisticated workflow system. It provides **clean agent-friendly interfaces** backed by **comprehensive Python automation workflows**.

**Key Philosophy:** Simple entry points for agents, sophisticated automation underneath.

## Architecture: Clean Separation of Concerns

```
Agent Request → Clean MCP Interface → Sophisticated Workflow → Business Logic
     ↑               ↑                      ↑                    ↑
  FastMCP        Agent-Friendly       Step-by-Step         Core Components
 Compatible        Interfaces         Automation           & Intelligence  
```

**Perfect for:**
- **Agent Integration**: Clean, predictable MCP interfaces
- **Business Logic Evolution**: Sophisticated workflows can evolve independently  
- **Debugging & Maintenance**: Clear separation, comprehensive logging
- **Testing**: Each component tested thoroughly

## Core Features

- **🎯 6-Entry-Point Architecture** - Simple interface for AI agents, comprehensive automation underneath
- **🧠 Intelligent Conflict Detection** - Semantic search prevents duplicate or conflicting decisions
- **🛡️ Automatic Policy Enforcement** - ADRs become ESLint/Ruff rules automatically
- **🚪 Preflight Validation** - Check technical choices before implementation
- **📝 MADR Format** - Industry standard with structured policy enforcement
- **🔍 Semantic Search** - Vector-based ADR discovery and relationship detection
- **🌐 Static Site Generation** - Beautiful documentation sites for developer transparency

## Quick Start for AI Agents

### 1. Installation & Setup

**Recommended Installation (Virtual Environment):**
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install ADR Kit with all dependencies
pip install adr-kit

# Initialize in your project
cd your-project
adr-kit init

# Start MCP server for AI integration  
adr-kit mcp-server
```

**Alternative Installation (Global with pipx):**
```bash
# Install globally with pipx (recommended for CLI tools)
pipx install adr-kit

# Or upgrade if already installed
pipx upgrade adr-kit
```

**Built-in Updates:**
```bash
# Check for and install updates
adr-kit update

# Just check for updates
adr-kit update --check
```

### 2. Configure Your AI Agent (Claude Code/Cursor)

Add to your MCP settings.json:
```json
{
  "mcpServers": {
    "adr-kit": {
      "command": "adr-kit", 
      "args": ["mcp-server"]
    }
  }
}
```

**Quick Setup:**
```bash
# For Cursor IDE
adr-kit setup-cursor

# For Claude Code  
adr-kit setup-claude
```

### 3. Start Using with Your AI Agent

Tell your AI agent:
- *"Analyze my project for architectural decisions that need ADRs"*
- *"Check if I can use PostgreSQL in this project"* 
- *"Create an ADR for switching to React Query"*
- *"Give me architectural context for implementing authentication"*

## How It Works: 6 MCP Entry Points → Sophisticated Workflows

ADR Kit provides **6 clean MCP interfaces** that trigger **comprehensive internal workflows**:

| MCP Tool | Workflow Backend | Purpose |
|----------|------------------|---------|
| `adr_analyze_project()` | AnalyzeProjectWorkflow | Technology detection, project scanning |
| `adr_preflight()` | PreflightWorkflow | Policy conflict detection, decision validation |
| `adr_create()` | CreationWorkflow | Semantic analysis, ADR generation |
| `adr_approve()` | ApprovalWorkflow | Policy activation, automation triggers |
| `adr_supersede()` | SupersedeWorkflow | Relationship management, history tracking |
| `adr_planning_context()` | PlanningWorkflow | Contextual guidance, constraint extraction |

### 🔍 1. `adr_analyze_project()` - Discover Missing ADRs
Scans your codebase and generates prompts for the agent to identify architectural decisions that need documentation.

### 🚦 2. `adr_preflight(choice)` - Validate Technical Choices
Before any technical decision, check: **ALLOWED** | **REQUIRES_ADR** | **BLOCKED**
- Prevents conflicts with existing decisions
- Routes agent to create ADRs when needed

### 📝 3. `adr_create(proposal)` - Create ADR Proposals  
Agent writes comprehensive ADRs with:
- Context, decision, consequences, alternatives
- Structured policies for automatic enforcement
- Conflict detection and validation

### ✅ 4. `adr_approve(adr_id)` - Trigger Full Automation
When human approves an ADR, automatically:
- Updates constraints contract
- Generates lint rules (ESLint, Ruff, import-linter)
- Rebuilds indexes and relationships
- Enables policy enforcement

### 🔄 5. `adr_supersede(old, new)` - Replace Decisions
Manages decision evolution with proper relationships and history tracking.

### 🗺️ 6. `adr_planning_context(task)` - Get Architectural Context
Provides curated guidance for specific development tasks based on existing ADRs.

## The Agent Workflow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Agent as AI Agent  
    participant ADR as ADR Kit

    Dev->>Agent: "We need to switch to PostgreSQL"
    Agent->>ADR: adr_preflight("postgresql")
    ADR-->>Agent: REQUIRES_ADR (conflicts with ADR-0003)
    Agent->>ADR: adr_create({title: "Use PostgreSQL", supersedes: ["ADR-0003"]})
    ADR-->>Agent: Created ADR-0007, conflicts detected
    Agent->>Dev: "Created ADR-0007. Please review."
    Dev->>Agent: "Approved" 
    Agent->>ADR: adr_approve("ADR-0007")
    ADR-->>Agent: ✅ Contract updated, lint rules generated, enforcement active
```

## ADR Format with Policy Enforcement

ADRs use MADR format with structured policies that become executable rules:

```markdown
---
id: ADR-0001
title: Use React Query for data fetching
status: accepted
deciders: [frontend-team, tech-lead]
tags: [frontend, data]
policy:
  imports:
    disallow: [axios, fetch]
    prefer: [react-query, @tanstack/react-query]
  boundaries:
    rules:
      - forbid: "components -> database"
---

## Context
Custom data fetching is scattered across components...

## Decision  
Use React Query for all data fetching operations.

## Consequences
### Positive
- Standardized patterns, built-in caching, better DX
### Negative
- Additional dependency, learning curve

## Alternatives
- **Native fetch()**: Simple but lacks caching
- **Axios**: Good client but no state management
```

**This automatically generates:**
```json
// .eslintrc.adrs.json
{
  "rules": {
    "no-restricted-imports": [
      "error",
      {
        "paths": [
          {"name": "axios", "message": "Use React Query instead (ADR-0001)"}
        ]
      }
    ]
  }
}
```

## Testing & Validation

ADR Kit includes **comprehensive test coverage** for reliable production use:

### Quick Validation
```bash
# Test core functionality
python run_workflow_tests.py

# Quick component check
adr-kit mcp-health
```

### Test Coverage
- **Unit Tests**: Individual workflow components and business logic
- **Integration Tests**: MCP server ↔ workflow integration 
- **End-to-End Tests**: Complete workflow chains (analyze → create → approve)
- **Error Scenarios**: Permission errors, disk full, concurrent execution
- **Performance Tests**: Large projects, memory efficiency, timing
- **Edge Cases**: Unicode handling, malformed input, corruption recovery

### Test Architecture Benefits
```python
# Each workflow is a testable Python function
workflow = CreationWorkflow(adr_dir="/test")
result = workflow.execute(creation_input)

assert result.success is True
assert result.data["creation_result"].adr_id.startswith("ADR-")
```

## Directory Structure

```
your-project/
├── docs/adr/                    # ADR files
│   ├── ADR-0001-react-query.md
│   └── adr-index.json          # Generated index
├── .eslintrc.adrs.json         # Generated lint rules
├── .adr-kit/                   # System files
│   └── constraints.json        # Policy contract
└── tests/                      # Comprehensive test suite
    ├── test_workflow_base.py    # Workflow infrastructure tests
    ├── test_workflow_*.py       # Individual workflow tests
    └── test_mcp_integration.py  # MCP ↔ workflow integration
```

## Manual Usage (Optional)

Basic CLI commands for non-AI workflows:

```bash
# Validate ADRs
adr-kit validate

# Generate documentation site  
adr-kit render-site

# Export lint configurations
adr-kit export-lint eslint --out .eslintrc.adrs.json
```

## Integration

### CI/CD Pipeline
```yaml
# .github/workflows/adr.yml
- run: pip install adr-kit
- run: adr-kit validate
- run: git diff --exit-code .eslintrc.adrs.json  # Ensure rules are current
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: adr-validate
      entry: adr-kit validate
      language: system
```

## Development

For development on ADR Kit itself:

```bash
# Development commands
make dev-setup     # Set up development environment
make reinstall     # Clean uninstall + fresh install (for testing changes)
make test          # Run test suite
make quality       # Format + lint + test
```

See `scripts/` directory for additional development tools.

## Learn More

- **MADR Format**: [Markdown ADR specification](https://adr.github.io/madr/)
- **MCP Protocol**: [Model Context Protocol for AI agents](https://modelcontextprotocol.io)
- **Example ADR**: See `docs/adr/ADR-0001-sample.md` for complete example

## License

MIT License - see [LICENSE](LICENSE) file for details.