# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADR Kit is a Python library and CLI tool for managing Architectural Decision Records (ADRs) in the MADR (Markdown ADR) format. The project provides:

- A Python 3.12+ library (`adr_kit/`) for creating, validating, and indexing ADRs
- CLI tool (`adr-kit`) for ADR management operations
- MCP server (`python -m adr_kit.mcp.server`) for exposing ADR tools to coding agents
- JSON Schema validation and semantic rule enforcement
- Integration with Log4brains for static site generation
- Lint rule generators for ESLint, Ruff, and import-linter

## Architecture

This is currently a specification/documentation project containing:

- **Specification Documents** (numbered `01_` through `08_`): Define the project vision, requirements, CLI spec, MCP spec, and implementation guidance
- **Schema Definition** (`schemas/adr.schema.json`): JSON Schema for ADR front-matter validation
- **Kickstart Documentation** (`08_CLOUD_CODE_KICKSTART_PROMPT.md`): Comprehensive implementation guide

### Core Components (To Be Implemented)

The project will be structured as:

```
adr_kit/
├── core/
│   ├── model.py          # Pydantic models for ADRs
│   ├── parse.py          # Front-matter + Markdown parsing
│   └── validate.py       # JSON Schema + semantic validation
├── index/
│   ├── json_index.py     # JSON index generation
│   └── sqlite_index.py   # SQLite catalog generation
├── enforce/
│   ├── eslint.py         # ESLint config generation
│   └── ruff.py           # Ruff/import-linter config generation
├── cli.py                # CLI interface using Typer/Click
└── mcp/
    └── server.py         # MCP server using FastMCP
```

## CLI Commands

The `adr-kit` CLI will provide these commands:

- `adr-kit init` - Initialize ADR structure in repository
- `adr-kit new "Title" --tags tag1,tag2` - Create new ADR
- `adr-kit validate [--id ADR-0007]` - Validate ADRs
- `adr-kit index --out docs/adr/adr-index.json` - Generate ADR index
- `adr-kit supersede ADR-0003 --title "New Title"` - Supersede existing ADR
- `adr-kit export-lint --framework eslint` - Generate lint configurations
- `adr-kit render-site` - Build static site via Log4brains

## Development Commands

**Note: This project is currently in specification phase. No build/test commands exist yet.**

When implemented, expected commands will be:
- `pytest tests/` - Run unit tests
- `python -m adr_kit.cli --help` - Test CLI locally
- `python -m adr_kit.mcp.server` - Start MCP server

## ADR Format

ADRs use MADR format with YAML front-matter:

```yaml
---
id: ADR-0001
title: "Decision Title"
status: accepted  # proposed, accepted, superseded, deprecated  
date: 2025-09-03
deciders: ["team-lead", "architect"]
tags: ["frontend", "data"]
supersedes: ["ADR-0002"]  # Optional
superseded_by: ["ADR-0004"]  # Auto-populated
---

# Decision content in Markdown
```

## Key Requirements

- Python 3.12+ compatibility
- No external network calls in core logic (except Log4brains)
- Clear error messages for invalid ADRs
- Consistent supersede logic that auto-updates related ADRs
- Performance target: validate 500 ADRs in <1 second