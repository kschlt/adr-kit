# ADR Kit

A comprehensive toolkit for managing Architectural Decision Records (ADRs) in the MADR (Markdown ADR) format. ADR Kit provides a Python library, CLI tool, and MCP server for creating, validating, indexing, and enforcing ADR decisions in your development workflow.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **📝 MADR-compliant** ADR creation and management
- **🔍 Validation** using JSON Schema and semantic rules
- **📊 Indexing** with JSON and SQLite outputs for queries
- **🔗 Superseding logic** with automatic relationship management  
- **⚡ CLI tool** with rich terminal output
- **🤖 MCP server** for coding agent integration
- **🛡️ Enforcement** via ESLint, Ruff, and import-linter config generation
- **🌐 Static site** generation via Log4brains integration
- **🧪 Comprehensive testing** with pytest

## 🚀 Quick Start

### Installation

```bash
pip install adr-kit
```

### Initialize ADR structure

```bash
adr-kit init
```

### Create your first ADR

```bash
adr-kit new "Use React Query for data fetching" \
  --tags frontend,data \
  --deciders frontend-team
```

### Validate and index ADRs

```bash
adr-kit validate
adr-kit index --out docs/adr/adr-index.json
```

## 📚 Usage

### CLI Commands

#### Initialize ADR structure
```bash
adr-kit init [--adr-dir docs/adr]
```

#### Create new ADR
```bash
adr-kit new "ADR Title" \
  [--tags tag1,tag2] \
  [--deciders person1,person2] \
  [--status proposed|accepted]
```

#### Validate ADRs
```bash
# Validate all ADRs
adr-kit validate

# Validate specific ADR
adr-kit validate --id ADR-0001
```

#### Generate indexes
```bash
# JSON index
adr-kit index --out docs/adr/adr-index.json

# SQLite catalog (optional)
adr-kit index --sqlite .project-index/catalog.db
```

#### Supersede existing ADRs
```bash
adr-kit supersede ADR-0001 --title "Updated Decision"
```

#### Export lint configurations
```bash
# ESLint rules from ADR decisions
adr-kit export-lint eslint --out .eslintrc.adrs.json

# Ruff configuration  
adr-kit export-lint ruff --out ruff.adrs.toml

# Import linter rules
adr-kit export-lint import-linter --out .import-linter.adrs.ini
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

### MCP Server for Coding Agents

Start the MCP server to expose ADR tools to coding agents like Claude Code:

```bash
python -m adr_kit.mcp.server
```

Available MCP tools:
- `adr.create()` - Create new ADRs
- `adr.supersede()` - Supersede existing ADRs  
- `adr.validate()` - Validate ADRs
- `adr.index()` - Query ADR index
- `adr.exportLintConfig()` - Generate lint configs
- `adr.renderSite()` - Build static site

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
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/
```

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