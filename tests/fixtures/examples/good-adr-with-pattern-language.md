---
id: "ADR-0002"
title: "Use React Query for Server State Management"
status: proposed
date: 2026-02-06
deciders: ["frontend-team", "architect"]
tags: ["frontend", "react", "state-management", "data-fetching"]
---

## Context

Our React application needs a robust solution for managing server state (API data, caching, synchronization). Currently using ad-hoc fetch calls with useState, leading to:
- Duplicated loading/error states across components
- No caching strategy - redundant API calls
- Stale data issues when data changes on server
- Complex synchronization logic scattered throughout codebase

Team has experience with Redux but finds it too verbose for simple data fetching.

## Decision

Use **React Query (TanStack Query)** for all server state management in the application.

**Don't use Redux** for server state - Redux should only handle UI state (modals, form state, etc). **Avoid** manual fetch + useState patterns. **Prefer React Query over custom data fetching hooks** for consistency.

All components fetching API data MUST use React Query's useQuery/useMutation hooks. Existing fetch calls **should be migrated** to React Query during regular development (no dedicated migration sprint needed).

## Consequences

### Positive

- **Automatic Caching**: Eliminates redundant API calls, improves performance
- **Simplified Components**: No more manual loading/error state management
- **Background Refetching**: Data stays fresh automatically
- **Optimistic Updates**: Better UX for mutations
- **DevTools**: Excellent debugging experience with React Query DevTools
- **Reduced Bundle Size**: Removes need for Redux Toolkit for data fetching

### Negative

- **Learning Curve**: Team needs to understand stale-while-revalidate patterns
- **Different Mental Model**: Declarative data fetching vs imperative fetch calls
- **Cache Invalidation Complexity**: Need to plan cache keys and invalidation strategies
- **Testing Changes**: Need to mock React Query in tests differently than fetch

### Risks

- Improper cache key design could lead to stale data bugs
- Team might overuse optimistic updates causing race conditions

### Mitigation

- Create React Query wrapper with sensible defaults
- Document cache key naming conventions
- Provide training on stale-time and cache-time configuration
- Add lint rules to prevent direct fetch usage

## Alternatives

### Redux + RTK Query

**Rejected**: Too heavyweight when we don't need global UI state management.

- Pros: Integrated with Redux, good caching, TypeScript support
- Cons: Requires full Redux setup, more boilerplate, **avoid** for simple use cases
- Why not: We don't need Redux's complexity for our current application

### SWR (Vercel)

**Rejected**: Less feature-complete than React Query.

- Pros: Lightweight, simple API, good caching
- Cons: Fewer features, less active development, smaller community
- Why not: React Query has better mutation support and more features

### Apollo Client

**Rejected**: GraphQL-specific, we use REST APIs.

- Pros: Excellent for GraphQL, mature, good caching
- Cons: Overkill for REST APIs, large bundle size
- Why not: We use REST APIs, **don't use** Apollo for REST

### Custom Hooks

**Rejected**: Reinventing the wheel, hard to maintain.

- Pros: Full control, no dependencies
- Cons: Need to implement caching, refetching, error handling, etc.
- Why not: React Query is battle-tested, **avoid custom fetch abstractions**

## Implementation Notes

- Install @tanstack/react-query v5
- Create `src/lib/react-query.ts` with default configuration
- Add React Query DevTools in development mode
- Update component library docs with data fetching patterns
- Migrate high-traffic components first (dashboard, list views)

## References

- [React Query Documentation](https://tanstack.com/query/latest)
- [Practical React Query](https://tkdodo.eu/blog/practical-react-query)
- Internal: Frontend Architecture Guidelines (Notion)
