---
id: ADR-0001
title: Use FastAPI with FastMCP for ADR Kit backend and MCP server
status: accepted
date: 2025-09-05
deciders: [adr-kit-team]
tags: [backend, api, fastapi, fastmcp, python, mcp]
supersedes: []
superseded_by: []
policy:
  imports:
    disallow: [flask, django, tornado, bottle]
    prefer: [fastapi, fastmcp, pydantic, uvicorn]
  boundaries:
    layers:
      - name: mcp
      - name: core
      - name: storage
    rules:
      - forbid: "mcp -> storage"
      - forbid: "storage -> mcp"
  python:
    disallow_imports: [flask, django, tornado, bottle]
  rationales: ["Enforce FastAPI-only web framework", "Use FastMCP for MCP server implementation", "Maintain clean architecture layers"]
---

## Context

We need to build a backend API and MCP server for the ADR Kit that will serve as the foundation for:
- MCP server integration with coding agents
- REST API endpoints for ADR management
- Real-time validation and processing services
- Integration with various development tools

The API needs to be:
- Fast and reliable for processing hundreds of ADRs
- Easy to integrate with existing development workflows
- Extensible for future requirements
- Well-typed and maintainable
- Support async operations for better performance

## Decision

We will use **FastAPI** as the web framework for the ADR Kit backend API.

FastAPI provides:
- Automatic API documentation with OpenAPI/Swagger
- Built-in data validation using Pydantic
- High performance with async/await support
- Type hints throughout the codebase
- Easy integration with modern Python tooling

## Consequences

### Positive

- ✅ **Automatic documentation**: OpenAPI/Swagger docs generated from code
- ✅ **Type safety**: Pydantic models provide runtime validation and IDE support
- ✅ **Performance**: FastAPI is one of the fastest Python web frameworks
- ✅ **Async support**: Native async/await for better concurrency
- ✅ **Modern Python**: Leverages Python 3.12+ features and type hints
- ✅ **Ecosystem**: Excellent integration with uvicorn, pytest, and other tools

### Negative

- ❌ **Learning curve**: Team needs to understand FastAPI patterns
- ❌ **Dependency**: Adds FastAPI and uvicorn to project dependencies
- ❌ **Python requirement**: Ties the backend to Python runtime

## Alternatives

### Alternative 1: Flask
- **Pros**: Simple, lightweight, mature ecosystem
- **Cons**: No built-in async support, manual API documentation, less type safety
- **Decision**: FastAPI chosen for better performance and automatic documentation

### Alternative 2: Django REST Framework
- **Pros**: Mature, feature-rich, excellent admin interface
- **Cons**: Heavy framework, slower performance, overkill for our use case
- **Decision**: FastAPI chosen for lighter weight and better performance

### Alternative 3: Starlette
- **Pros**: Lightweight, fast, async-first
- **Cons**: Less features out-of-the-box, more manual setup required
- **Decision**: FastAPI chosen for better developer experience and built-in features