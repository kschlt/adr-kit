---
id: ADR-0001
title: Use Python and FastAPI for the ADR Kit backend
status: accepted
date: 2025-09-03
deciders: [adr-kit-team]
tags: [backend, architecture, python, api]
supersedes: []
superseded_by: []
---

# Context

We need to build a toolkit for managing Architectural Decision Records (ADRs) that includes:
- A Python library for parsing and validating ADRs
- A CLI tool for common ADR operations
- An MCP server for integration with coding agents
- Support for generating lint configurations from ADR decisions

The solution needs to be:
- Fast and reliable for processing hundreds of ADRs
- Easy to integrate with existing development workflows
- Extensible for future requirements
- Well-typed and maintainable

# Decision

We will use **Python 3.12** with **FastAPI** for the ADR Kit implementation:

1. **Core library** in Python using Pydantic for data modeling
2. **CLI interface** using Typer for modern command-line experience  
3. **MCP server** using FastMCP for agent integration
4. **Validation** using JSON Schema and custom semantic rules
5. **Indexing** supporting both JSON and SQLite outputs
6. **Enforcement** generating ESLint, Ruff, and import-linter configurations

# Consequences

## Positive

- ✅ **Strong typing**: Pydantic provides excellent data validation and typing
- ✅ **Performance**: Python 3.12 offers good performance for file processing tasks
- ✅ **Ecosystem**: Rich ecosystem of libraries for YAML, JSON Schema, SQLite
- ✅ **Developer experience**: Typer and Rich provide excellent CLI UX
- ✅ **Agent integration**: FastMCP enables seamless integration with coding agents
- ✅ **Maintainability**: Clear module structure and comprehensive test suite
- ✅ **Extensibility**: Plugin architecture allows for custom lint rule generators

## Negative

- ❌ **Runtime dependency**: Requires Python runtime in target environments
- ❌ **Package management**: Need to manage Python dependencies for distribution
- ❌ **Performance ceiling**: May need optimization for very large ADR repositories (>1000s)

# Alternatives

## Alternative 1: TypeScript/Node.js
- **Pros**: Excellent JSON/YAML handling, good performance, npm distribution
- **Cons**: Less mature ecosystem for CLI tools, complex async model for file operations
- **Decision**: Python chosen for better data validation and CLI library ecosystem

## Alternative 2: Go
- **Pros**: Single binary distribution, excellent performance, good CLI libraries
- **Cons**: Less flexible data modeling, smaller ecosystem for schema validation
- **Decision**: Python chosen for rapid development and rich validation libraries

## Alternative 3: Rust
- **Pros**: Maximum performance, excellent error handling, single binary
- **Cons**: Steeper learning curve, longer development time, smaller ecosystem
- **Decision**: Python chosen for faster time-to-market and easier maintenance