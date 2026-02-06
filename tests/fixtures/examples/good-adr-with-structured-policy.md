---
id: "ADR-0001"
title: "Use FastAPI as Web Framework"
status: proposed
date: 2026-02-06
deciders: ["architect", "backend-team"]
tags: ["backend", "framework", "python", "fastapi"]
policy:
  imports:
    disallow: ["flask", "django", "litestar", "django-rest-framework"]
    prefer: ["fastapi"]
  python:
    disallow_imports: ["flask", "django"]
  rationales:
    - "FastAPI provides native async support required for I/O-heavy operations"
    - "Automatic OpenAPI documentation reduces maintenance burden"
    - "Pydantic integration ensures type safety across the application"
---

## Context

Our backend services require a Python web framework that supports:
- Native async/await for concurrent request handling
- Strong typing and automatic validation
- Automatic API documentation generation
- Modern development experience with good tooling support

Current state: No framework selected for new microservices project.

## Decision

Use **FastAPI** as the standard web framework for all backend API services.

All new backend services MUST use FastAPI. Existing services using Flask or Django can be migrated opportunistically during major refactors.

## Consequences

### Positive

- **Performance**: Native async support enables handling 10x more concurrent connections
- **Type Safety**: Pydantic validation catches errors at API boundaries automatically
- **Documentation**: OpenAPI specs generated automatically, no manual maintenance
- **Developer Experience**: Modern Python features (3.10+), excellent IDE support
- **Ecosystem**: Growing ecosystem with good middleware and extension support

### Negative

- **Team Training**: Team needs to understand async/await patterns in Python
- **Ecosystem Maturity**: Smaller plugin ecosystem compared to Django/Flask
- **Migration Cost**: Existing Flask services will need eventual migration
- **Debugging**: Async code can be harder to debug than synchronous code

### Risks

- Team unfamiliarity with async Python could lead to subtle bugs
- Smaller community means fewer Stack Overflow answers for edge cases

### Mitigation

- Provide async Python training for backend team (scheduled Q1 2026)
- Create internal FastAPI template with best practices
- Document common patterns and anti-patterns in team wiki

## Alternatives

### Django + Django REST Framework

**Rejected**: Too opinionated and heavyweight for microservices architecture.

- Pros: Mature ecosystem, excellent admin interface, ORM included
- Cons: Synchronous by default, heavy for API-only services, opinionated structure
- Why not: We don't need Django's ORM or admin interface for API services

### Flask

**Rejected**: Lacks native async support and integrated type safety.

- Pros: Lightweight, simple, huge ecosystem, team familiarity
- Cons: No native async, manual validation, requires many extensions
- Why not: Async support is bolt-on (ASGI via Quart), no integrated validation

### Litestar

**Rejected**: Too new, smaller community.

- Pros: Similar features to FastAPI, good performance
- Cons: Very small community, less mature ecosystem
- Why not: Risk of insufficient community support and documentation

## Implementation Notes

- Create `fastapi-template` repository with standard project structure
- Add FastAPI to approved dependencies list in package manager
- Update backend onboarding docs to include FastAPI quickstart
- Schedule team training session for async Python patterns

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Async Python Guide](https://docs.python.org/3/library/asyncio.html)
- Internal: Backend Architecture Decision Process (Confluence)
