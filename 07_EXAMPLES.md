# ADR Kit — Example ADRs

## ADR-0007
```markdown
---
id: ADR-0007
title: Use React Query for data fetching
status: accepted
date: 2025-09-03
deciders: [frontend-arch]
tags: [frontend,data]
supersedes: [ADR-0003]
superseded_by: []
---

# Context
Fetching strategies were inconsistent...

# Decision
Adopt React Query across frontend for API calls.

# Consequences
- ✅ Cache and background updates standardized
- ❌ Adds dependency
```

## ADR-0008
```markdown
---
id: ADR-0008
title: Use PostgreSQL as the system database
status: accepted
date: 2025-09-03
deciders: [backend-arch]
tags: [database,infra]
supersedes: []
superseded_by: []
---

# Context
We needed a relational DB with strong community support.

# Decision
Adopt PostgreSQL.

# Consequences
- ✅ Strong support
- ✅ Scalable
- ❌ Requires managed hosting
```
