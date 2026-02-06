---
id: "ADR-0003"
title: "Use PostgreSQL for Primary Database"
status: proposed
date: 2026-02-06
deciders: ["backend-team", "architect"]
tags: ["database", "postgresql", "storage"]
---

## Context

Our application needs a reliable, scalable database solution for storing:
- User accounts and profiles
- Transaction records
- Product catalog
- Analytics data

Current state: Using SQLite for development, need production database.

Requirements:
- ACID compliance for financial transactions
- Support for complex queries and joins
- Good performance at scale (100k+ users)
- Strong community and ecosystem
- Team has SQL experience

## Decision

Use PostgreSQL as the primary database for the application.

We will deploy PostgreSQL 15 on managed cloud infrastructure (AWS RDS) for production. Development environments will use PostgreSQL via Docker Compose.

## Consequences

### Positive

- **ACID Compliance**: Guarantees data consistency for financial transactions
- **Feature Rich**: Supports JSON, full-text search, arrays, and advanced indexing
- **Performance**: Handles complex queries efficiently with query planner
- **Ecosystem**: Mature tooling, extensions (PostGIS, pg_stat_statements)
- **Team Familiarity**: Team has experience with SQL databases
- **Cost Effective**: Open source, no licensing fees

### Negative

- **Operational Complexity**: Requires proper configuration and maintenance
- **Vertical Scaling Limits**: Eventually hits single-server limits
- **Backup Strategy**: Need to implement robust backup and recovery
- **Resource Usage**: Higher memory/CPU requirements than simpler databases

### Risks

- Improper indexing could lead to performance issues at scale
- Need to monitor connection pooling to prevent exhaustion
- Query performance degrades without proper vacuuming

### Mitigation

- Use connection pooling (PgBouncer) from day one
- Implement automated backups with point-in-time recovery
- Set up monitoring (pg_stat_statements, slow query log)
- Regular database maintenance schedule (VACUUM, ANALYZE)
- Load testing before production launch

## Alternatives

### MySQL

Considered but PostgreSQL chosen for better JSON support and extensibility.

- Pros: Very popular, good performance, wide adoption
- Cons: Less feature-rich, weaker JSON support, Oracle ownership concerns
- Why not chosen: PostgreSQL's advanced features align better with our needs

### MongoDB

Considered but relational model better fits our data structure.

- Pros: Flexible schema, horizontal scaling, good for unstructured data
- Cons: Eventual consistency, less mature transactions, learning curve
- Why not chosen: Our data is highly relational (users, orders, products)

### SQLite

Currently used in development, not suitable for production.

- Pros: Zero configuration, embedded, perfect for development
- Cons: No concurrency, single file, limited scalability
- Why not chosen: Not designed for multi-user production applications

## Implementation Notes

- Set up PostgreSQL 15 on AWS RDS with Multi-AZ deployment
- Configure automated daily backups with 30-day retention
- Install pgBouncer for connection pooling
- Set up monitoring with DataDog + pg_stat_statements
- Create database migration strategy using Alembic (Python) or Flyway (Java)
- Document common queries and indexing strategies

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [High Performance PostgreSQL](https://www.postgresql.org/docs/current/performance-tips.html)
- Internal: Database Standards (Confluence)
