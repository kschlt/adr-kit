# ADR Kit — File Format & Schemas

## Directory Structure
```
/docs/adr/
  ADR-0007-use-react-query.md
  ADR-0008-use-postgres.md
docs/adr/adr-index.json
.project-index/catalog.db
```

## ADR Markdown Template (MADR-like)
```markdown
---
id: ADR-0007
title: Use React Query for data fetching
status: accepted        # proposed | accepted | superseded | deprecated
date: 2025-09-03
deciders: [team-arch, lead-fe]
tags: [frontend, data]
supersedes: [ADR-0003]
superseded_by: []
---

# Context
...

# Decision
...

# Consequences
...

# Alternatives
...
```

## JSON Schema (front-matter)
See `schemas/adr.schema.json`.

## Semantic Rules
- `status=superseded` requires `superseded_by`.
- New ADR must update `supersedes` and target ADR’s `superseded_by`.
