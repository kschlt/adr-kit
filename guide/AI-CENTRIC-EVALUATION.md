# AI-Centric ADR Evaluation Guide

**Purpose**: Understanding how ADR Kit approaches architectural decisions for AI-driven development

**Last Updated**: 2026-02-08

---

## Philosophy: AI-Centric vs Team-Centric ADRs

Traditional ADRs evaluate technical choices based on **human team dynamics**: familiarity, learning curve, hiring availability, developer preferences.

**ADR Kit optimizes for AI agents** that will implement and maintain the architecture. This means focusing on:

1. **Direct feedback loops** - Can the AI get immediate, reliable, actionable feedback?
2. **Interpretability** - Can the AI understand what went wrong and why?
3. **Verifiability** - Can errors be caught automatically, both statically and at runtime?
4. **Documentation accessibility** - Is knowledge machine-readable and available at implementation time?
5. **Scope isolation** - Can the AI work within bounded context without understanding the entire system?
6. **Safety and reversibility** - Are mistakes cheap to recover from?
7. **Multi-agent compatibility** - Can multiple agents work on the codebase in parallel?

Every architectural decision should be evaluated through two lenses:

- **Does it serve the purpose of what we're building?** (functional requirements)
- **Is it agent-friendly for implementation?** (if a more agent-friendly alternative exists that equally serves the purpose, prefer it)

This represents a fundamental shift in how we evaluate and document architectural decisions.

---

## Core Assumptions: What Actually Helps AI?

These are the assumptions we built ADR Kit on. Understanding these helps you evaluate technologies for AI-driven development.

### Assumption 1: Direct Feedback Loops Enable Self-Correction

AI agents improve dramatically when they can test, fail, and iterate quickly. But the feedback must be **fast**, **reliable**, and **actionable** — and the AI must be able to **execute** the system to get runtime feedback.

**What this means for tech choices**:
- ✅ **Type safety** - Errors caught at compile/build time, not production
- ✅ **Descriptive error messages** - AI can understand and fix issues autonomously
- ✅ **Fast test cycles** - Quick validation of changes
- ✅ **Deterministic behavior** - Same input always produces same output; AI can trust results
- ✅ **Easy local execution** - AI can run the system and see live results
- ❌ **Runtime-only errors** - AI discovers problems too late to fix efficiently
- ❌ **Non-deterministic failures** - AI can't distinguish "my code is wrong" from "the test is flaky"

#### Determinism matters as much as speed

Non-deterministic failures (flaky tests, race conditions, environment-dependent behavior) are particularly damaging for AI agents. A human can recognize "that's probably just a timing issue" — an AI agent will chase it, attempt a fix, break something else, and loop.

**Example**: Test database strategy
- ✅ SQLite in-memory for tests: Each test run gets isolated state. Tests are deterministic — the AI can trust that a failing test means its code is wrong.
- ❌ Shared PostgreSQL for tests: Parallel tests with shared state can produce intermittent failures. The AI "fixes" a passing test, but the real issue was a race condition.

**Example**: Event-driven vs synchronous architecture
- ✅ Synchronous REST: AI calls endpoint, gets response, knows immediately if it worked.
- 🟡 Async message queue: AI publishes a message, then must poll or wait for a consumer to process it. Timing-dependent tests are notoriously flaky. **Mitigation**: Use in-memory message broker for tests, add deterministic test helpers.

#### Executability: Can the AI actually run it?

Some technology choices are easy for an AI agent to execute locally and get live feedback, while others are not:

- ✅ **Python FastAPI app** - `pip install`, `uvicorn main:app`, hit endpoint, see response or error immediately.
- ✅ **Node.js CLI tool** - `npm install`, `node index.js`, immediate output.
- ✅ **Docker Compose setup** - `docker compose up`, entire system running with one command. Reproducible, isolated, easy to tear down and restart.
- 🟡 **System requiring multiple interconnected services** - Harder to spin up, but manageable with good Docker Compose or dev scripts.
- ❌ **Mobile app** - Needs simulator/emulator, device-specific behavior. AI can't easily run and test.
- ❌ **System requiring manual setup** - Environment-specific configuration, physical hardware, or complex provisioning locks the AI out of the feedback loop.

**ADR question**: Does this technology choice allow the AI agent to execute the system, see live results, and trust the feedback it receives?

### Assumption 2: Documentation Accessibility Enables Autonomous Implementation

New or unfamiliar technology is manageable if AI can access current, **machine-readable** documentation at implementation time.

**Nuanced view on "LLM training data"**:
- ❌ **Problem**: Brand new framework (no docs, experimental API)
- 🟡 **Manageable**: New version of established framework (docs exist, patterns familiar)
- ✅ **Ideal**: Mature framework (extensive training data + docs)

#### Documentation quality for AI consumption

Not all documentation is equally useful to AI agents. The format and structure matter:

- ✅ **Reference-grade documentation** - Structured, each pattern shown with complete code, input/output types explicit, copy-pasteable examples. AI can extract the exact pattern it needs. (Example: FastAPI docs, Rust std docs)
- 🟡 **Tutorial-grade documentation** - Long narrative that assumes sequential reading and builds on previous sections. AI struggles with "refer to the setup we did in chapter 3."
- ❌ **Sparse or outdated docs** - AI generates code based on stale patterns or guesses.

#### Evaluating documentation accessibility

When assessing a technology choice, the evaluating agent should determine:

1. **Is official documentation available in a text-based, structured format?**
2. **Can the agent access and query this documentation at implementation time?** (e.g., through documentation retrieval tools, project-local docs, or reference implementations)
3. **Is the documentation detailed enough for AI to extract specific, actionable patterns?**
4. **If documentation is limited, are there reference implementations in the project that demonstrate the patterns?**

**How to document this in ADRs**:
```markdown
## Consequences

### Negative

- **Limited Training Data**: Next.js 15 App Router is recent
  - Official documentation available at vercel.com/docs (structured, reference-grade)
  - Reference patterns in examples/nextjs-app-router/
  - Agent should verify documentation accessibility before implementation
  - Server/client boundary requires understanding of RSC model
```

Document **what the limitation is**, **where knowledge exists**, and **how accessible it is for AI consumption**. The AI will use this context when implementing.

### Assumption 3: Verifiable Contracts and Runtime Observability Reduce Iteration Cycles

If contracts can be validated automatically, AI wastes less time on integration bugs. But verification doesn't stop at build time — **runtime observability** is equally critical for AI agents debugging live behavior.

#### Static verification (build-time / compile-time)

- ✅ **Strong typing** (TypeScript, Pydantic, Rust) - Contracts enforced statically
- ✅ **Schema validation** (JSON Schema, OpenAPI) - APIs self-document
- ✅ **Property-based testing** - AI can verify invariants hold
- ❌ **Implicit contracts** - AI guesses behavior, often incorrectly

**Example**: FastAPI with Pydantic v2
- Request/response models are automatically validated
- AI gets precise error: "field 'email' is required, got null"
- Can fix immediately without manual debugging

#### Runtime observability (when things go wrong in execution)

When an AI agent runs the system and something fails, the quality of runtime feedback determines whether it can self-correct:

- ✅ **Structured error logging** - AI can programmatically understand what happened. (Example: structlog in Python produces parseable, structured log output)
- ✅ **Framework dev-mode overlays** - Exact file, line, and suggested fix shown. (Example: Next.js error overlay)
- ✅ **Detailed runtime validation errors** - Specific field, constraint, and value reported. (Example: Pydantic, Zod)
- ❌ **Generic error responses** - "500 Internal Server Error" with no context. AI has no idea what went wrong.
- ❌ **Errors logged to external monitoring only** - If the AI can't query the monitoring system, it can't debug.

**ADR question**: Does this technology provide clear, structured, actionable feedback at both build time *and* runtime? If runtime feedback is weak, what mitigation exists (structured logging, dev tools, debug modes)?

### Assumption 4: Decision Space Reduction Beats Flexibility

"One obvious way" beats "many flexible options" for AI agents. The fewer valid approaches to accomplish a task, the more likely the AI picks the right one on the first attempt.

**Why this matters**:
- ✅ **Django** - Convention over configuration. One way to define models, one ORM, one URL routing pattern. AI knows exactly what to do.
- ✅ **Next.js App Router** - File-based routing, one pattern for data fetching (`async` server components). Minimal decision space.
- 🟡 **Flask** - Flexible, but AI must choose from many valid approaches (Flask-RESTful? Marshmallow? Raw Flask? Class-based or function-based?). Each valid, but different.
- ❌ **Inconsistent codebase** - Three different patterns for the same thing. AI sees all three, might pick any, or introduce a fourth. Inconsistency propagates over time.

#### Consistency enforcement matters more than conventions alone

AI agents mimic what they see. If the codebase has inconsistent patterns, that inconsistency will propagate and compound. Technology choices that **enforce consistency automatically** are more valuable than those that merely suggest it:

- ✅ **Linters with auto-fix** (ESLint with strict rules, Ruff for Python) - AI output gets normalized automatically
- ✅ **Code formatters** (Prettier, Black) - Style is never a question
- ✅ **Framework conventions that are linter-enforceable** - Not just "we suggest this" but "the linter fails if you don't"
- 🟡 **Documented conventions without enforcement** - Better than nothing, but AI may not always follow them

**Note**: Consistency benefits both AI implementation *and* human review. If AI always produces code following the same patterns, humans can review it faster because they know what to expect.

**ADR question**: Does this technology choice minimize the number of valid ways to accomplish common tasks? Does it provide tooling to enforce conventions automatically?

### Assumption 5: Scope Isolation and Modularity Enable Effective Context Use

AI agents work within **limited context windows**. An architecture where the AI must understand the entire system to make a small change is significantly harder than one where changes are localized.

**Why this matters**:
- AI agents load relevant code into their context to work on a task. If a small feature change requires touching 15 files across 6 directories, the agent's context fills with tangentially related code, increasing the chance of wrong assumptions and unintended side effects.
- Well-bounded modules with clear interfaces allow the AI to focus on the relevant scope, understand the boundaries, and make changes without accidentally breaking unrelated functionality.

**What this means for tech choices**:
- ✅ **Well-structured modules with clear interfaces** - AI loads only what's relevant. Change to "user authentication" only requires understanding `src/auth/`.
- ✅ **File-based routing** (Next.js, Nuxt) - AI knows exactly where to add a new page. One file = one route.
- ✅ **Focused libraries with narrow APIs** (e.g., `bcrypt` — one job, small surface) - AI doesn't need to figure out which subset of a swiss-army-knife library to use.
- 🟡 **Monolith with internal boundaries** - Can work well if modules have clear interfaces and don't leak implementation details.
- ❌ **Tangled architecture** - Every feature touches everything. AI must load the entire codebase to understand any change.
- ❌ **Centralized configuration files** - One giant `routes.ts` or single monolithic schema file means every agent touches the same file.

**Example**: Adding a new API endpoint
- ✅ File-per-route structure (`src/routes/users.ts`, `src/routes/orders.ts`): AI creates one new file, references one interface. Bounded scope.
- ❌ Single routes file with all endpoints: AI must understand the entire routing structure, risk of accidentally modifying existing routes.

**ADR question**: Does this technology choice lead to bounded, isolated modules where changes are localized? Or does it create deep coupling where touching one thing requires understanding everything?

### Assumption 6: Reversibility and Safety Reduce Cost of AI Mistakes

AI agents make mistakes — that's the entire premise of the feedback loop assumption. The architecture should make mistakes **cheap to recover from**, **safe by default**, and **resilient to retries**.

#### Cost of mistakes and reversibility

For pure code changes, Git handles reversibility. But many architectural decisions involve **state changes that Git can't reverse**:

- ✅ **ORM with reversible migrations** (Django generates both `forward` and `backward` operations by default) - AI can roll back a bad migration.
- ✅ **Infrastructure as Code** (Terraform, Pulumi) - Changes are declarative, reviewable, and reversible. `terraform plan` before apply. AI can propose a change and preview the impact.
- ✅ **Feature flags** - AI ships code behind a flag. If broken, flag is turned off. No full rollback deployment needed.
- ✅ **Event sourcing** - Store events, derive state. Can always replay from a known good state.
- ❌ **Raw SQL migrations without rollback** - A migration that drops a column loses data irreversibly.
- ❌ **Mutable state without audit trail** - Direct DB updates with no way to reconstruct what changed.
- ❌ **Imperative infrastructure scripts** - A mistake might be hard to undo without manual intervention.

#### Security by default

AI agents don't reason about security the way a security-conscious human does. They will use insecure patterns unless the technology actively prevents them. Technologies with **secure-by-default** patterns are materially better for AI-driven development:

- ✅ **ORM with parameterized queries** (SQLAlchemy, Django ORM) - SQL injection is physically impossible through the standard API. AI can't create this vulnerability even if it tries.
- ✅ **Framework with built-in CSRF/XSS protection** (Django CSRF middleware, React JSX auto-escaping) - Security is on by default, not opt-in.
- ✅ **Authentication libraries** (`bcrypt`, `argon2`) - Secure password hashing by design. AI doesn't need to make security decisions.
- ✅ **Environment variable validation** (`python-dotenv` with schema validation, `@t3-oss/env-nextjs`) - Required vars validated at startup, types checked.
- ❌ **Raw SQL string concatenation** - AI will build queries with string formatting, creating injection vulnerabilities.
- ❌ **Security as opt-in middleware** - AI may forget to add it. Manual setup means manual mistakes.
- ❌ **Rolling your own authentication** - AI will produce subtly insecure implementations.

#### Idempotency: safe to retry

If an AI agent's operation is interrupted or it's unsure whether something succeeded, idempotent operations can be safely re-run:

- ✅ **Upsert patterns** (`INSERT ... ON CONFLICT DO NOTHING`) - Running twice produces the same result.
- ✅ **Declarative infrastructure** (`terraform apply`) - Running twice produces the same state.
- ✅ **PUT endpoints** (idempotent by design) - Same request, same result.
- ❌ **INSERT without deduplication** - Running a seed script twice creates duplicate records.
- ❌ **Imperative scripts with side effects** - Appending to a config file without checking existing content doubles entries.

**ADR question**: If the AI agent makes a mistake with this technology, how costly is it to recover? Does the technology make the insecure path harder than the secure path? Are key operations safe to retry?

### Assumption 7: Multi-Agent Compatibility Enables Parallel Development

In AI-driven development, multiple agents often work on the same codebase simultaneously — planning, implementing, reviewing, testing. The architecture should support this.

**What this means for tech choices**:

#### Minimizing merge conflict likelihood

- ✅ **File-per-route, file-per-model, module-per-feature** - Two agents working on different features rarely touch the same file.
- ❌ **Single centralized files** (one giant `routes.ts`, one monolithic `schema.prisma`) - Multiple agents working in parallel will create merge conflicts constantly.

#### Stable contracts between agents

If one agent builds the API and another builds the frontend, they need a stable, shared contract:

- ✅ **Auto-generated contracts** (OpenAPI from FastAPI, GraphQL schema, tRPC) - Both agents work against the same source of truth. Changes to the contract are explicit and detectable.
- ❌ **Implicit contracts** - Agent A changes a response shape, Agent B's code breaks without either realizing until integration.

#### Independent testability

- ✅ **Well-defined module boundaries with interfaces** - Agent A can test its module without Agent B's module being in a working state. Both work in parallel.
- ❌ **Tightly coupled modules** - One agent's half-finished work breaks another agent's ability to test.

#### Clear ownership boundaries

- ✅ **Clear module boundaries** (auth, billing, UI, API) - Different agents own different modules without stepping on each other.
- ❌ **Every feature touches everything** - Agent coordination becomes a bottleneck. Changes cascade unpredictably.

**ADR question**: Does this architecture support parallel development by multiple agents? Are change boundaries clear enough that two agents working on different features won't conflict? Are contracts between components explicit and auto-validated?

---

## Evaluation Criteria

When documenting architectural decisions, evaluate technologies on these dimensions:

### 1. Error Quality (Direct Feedback)

**What matters**:
- Descriptive error messages with file/line numbers
- Suggestions for fixes (like Rust compiler)
- Stack traces and error output AI can parse
- Structured error format (not just human-readable prose)

**Examples**:
- ✅ Next.js error overlay: "You're importing a client component in a server component. Add 'use client' directive."
- ✅ Pydantic validation: "field 'age' must be >= 0, got -5"
- ✅ Rust compiler: Shows exact location + suggests the fix
- ❌ Generic 500 error with no context
- ❌ Errors that only appear in a separate monitoring dashboard

### 2. Type Safety & Static Analysis

**What matters**:
- Errors caught before runtime
- Contracts validated automatically
- IDE/editor support for autocomplete

**ADR consideration if weak**:
- Document requirement for runtime validation (e.g., Zod, Joi)
- Specify linting requirements (ESLint, Ruff)
- Define testing standards in ADR

### 3. Executability & Runtime Feedback

**What matters**:
- Can the AI run the system locally with minimal setup?
- Does the technology support a fast dev/watch mode?
- Are runtime errors structured and actionable?
- Is logging structured and parseable (not just print statements)?

**ADR consideration if hard to execute**:
- Document Docker Compose setup for local execution
- Specify dev scripts that simplify startup
- Note any external dependencies that must be mocked/stubbed for local development

### 4. Documentation Accessibility

**What matters**:
- Official docs are comprehensive, current, and structured
- Documentation is machine-readable (text-based, not video-only)
- Examples cover common use cases with complete, copy-pasteable code
- Migration guides for version changes

**How to document in ADRs when docs are limited**:
```markdown
### Negative

- **Limited Documentation**: [Technology] docs are sparse/incomplete
  - Official docs at [URL] (format: [structured reference / tutorial / sparse])
  - Reference implementation in [path/to/code]
  - Agent should verify documentation accessibility before implementation
  - [Specific pattern/approach] documented below
```

Document the limitation, where knowledge exists, and how accessible it is for AI consumption.

### 5. Decision Space & Conventions

**What matters**:
- Few valid ways to accomplish common tasks
- Enforceable conventions (linters, formatters, framework structure)
- Consistent patterns that reduce ambiguity

**Mitigation if ambiguous**:
- Document chosen patterns explicitly in ADRs
- Use linters to enforce conventions automatically (ADR Kit generates configs from policies)
- Provide reference implementations for non-obvious patterns

### 6. Determinism & Testability

**What matters**:
- Easy to write unit/integration tests
- Fast test execution
- Deterministic test results (no flaky tests from shared state or timing)
- Isolated test environments

**ADR consideration if non-deterministic**:
- Document test isolation strategy
- Specify in-memory alternatives for external dependencies (e.g., SQLite for tests)
- Note any known sources of non-determinism and their mitigations

### 7. Scope & Modularity

**What matters**:
- Changes are localized to a bounded module
- Clear interfaces between components
- AI doesn't need to load the entire codebase to make a small change
- File structure supports focused context

**ADR consideration if tightly coupled**:
- Document module boundaries explicitly
- Specify interface contracts between modules
- Note which changes require cross-module coordination

### 8. Reversibility & Safety

**What matters**:
- Mistakes are cheap to reverse (especially state changes beyond code)
- Secure-by-default patterns (SQL injection, XSS, CSRF protection built-in)
- Key operations are idempotent (safe to retry)
- Migration strategy supports rollback

**ADR consideration if risky**:
- Document rollback procedures for state-changing operations
- Specify security measures that must be manually applied
- Note any irreversible operations and their safeguards

### 9. Multi-Agent Compatibility

**What matters**:
- File and module structure minimizes merge conflict probability
- Contracts between components are auto-generated and shared
- Components can be tested independently
- Clear ownership boundaries for parallel work

**ADR consideration if conflict-prone**:
- Document which files are shared bottlenecks
- Specify coordination requirements for cross-cutting changes
- Note contract generation or synchronization approach

### 10. Reference Implementations

**What matters for evaluation**:
- Working examples AI can learn from
- Open-source projects demonstrating the technology
- Starter templates showing best practices

**ADR consideration if rare**:
- Document requirement for reference implementation
- Specify which patterns need examples
- Link to analogous examples in ADR

### 11. Reviewability

**What matters**:
- Can a human reviewer who didn't write the code (because AI wrote it) quickly understand what it does and whether it's correct?
- Is the technology widely understood enough for effective review?
- Does the framework produce explicit, readable code (vs. implicit "magic" behavior)?

**Examples**:
- ✅ Go code: Explicit, what-you-see-is-what-happens. Easy to review regardless of who wrote it.
- ✅ Python with type hints: Behavior is clear from signatures.
- 🟡 Rails with heavy metaprogramming: Implicit behavior via `method_missing` and dynamic methods. Harder to review because the behavior isn't visible in the code.
- ❌ Heavily macro-based code: Reviewer must mentally expand macros to understand behavior.

---

## ADR Consequences Template

When documenting consequences, focus on AI-relevant factors:

```markdown
## Consequences

### Positive

- **Type Safety**: Strong (TypeScript strict mode)
  - Compile-time error detection reduces runtime bugs
  - AI gets immediate feedback on type mismatches

- **Error Quality**: Descriptive (Pydantic v2 validation)
  - Errors specify exact field and constraint violated
  - AI can fix issues without guessing

- **Documentation**: Comprehensive and machine-readable
  - FastAPI official docs: structured reference format with complete examples
  - Agent can verify doc accessibility at implementation time
  - Mitigates any training data gaps

- **Executability**: High (single-command local setup)
  - `docker compose up` runs entire system
  - Dev mode with hot reload for fast iteration
  - Structured logging via structlog for runtime debugging

- **Conventions**: Clear (REST + OpenAPI)
  - Standard patterns for routes, dependencies
  - OpenAPI schema auto-generated from code
  - Ruff + Black enforce code style automatically

- **Testability**: High and deterministic (TestClient + pytest)
  - Easy to write integration tests
  - SQLite in-memory for test isolation
  - Fast, deterministic test cycles

- **Modularity**: Well-bounded (module-per-domain)
  - Auth, billing, API clearly separated
  - Changes localized to single module

- **Safety**: Secure by default (SQLAlchemy ORM + Pydantic)
  - Parameterized queries prevent SQL injection
  - Input validation automatic on all endpoints
  - Migrations support rollback

- **Multi-Agent**: Compatible (file-per-route + OpenAPI contract)
  - Parallel agents rarely touch same files
  - OpenAPI schema serves as shared contract

### Negative

- **Training Data**: Limited for FastAPI 0.115+ features
  - Official docs at fastapi.tiangolo.com (structured reference format)
  - Reference implementation in src/api/ demonstrates patterns

- **Async Complexity**: Requires understanding of Python async/await
  - Known AI pitfall: forgetting to await coroutines
  - Async patterns for database queries in src/api/routes/
  - Linting rules catch unawaited coroutines
```

---

## Real-World Example: Traditional vs AI-Centric

### Traditional Team-Centric ADR
```markdown
## Consequences

### Positive
- Team already familiar with React patterns
- Fast development once learned
- Good community support

### Negative
- Team must learn Next.js App Router
- Requires understanding of Server Components
- More complex than Vite
```

Team familiarity, learning curve, and developer experience drive the evaluation.

---

### AI-Centric ADR (ADR Kit)
```markdown
## Consequences

### Positive

- **Type Safety**: Strong (TypeScript strict mode + React Server Components)
  - Server/client boundary violations caught at build time
  - AI receives clear error: "Cannot pass function to client component"

- **Error Quality**: Descriptive (Next.js error overlay)
  - Exact file, line, and suggested fix shown
  - AI can self-correct without human intervention

- **Documentation**: Comprehensive and machine-readable
  - Vercel docs: structured reference format with migration guides
  - Agent should verify Next.js 15 doc accessibility before implementation
  - Training data strong for React patterns (transferable)

- **Executability**: High (dev server with hot reload)
  - `npm run dev` starts watch mode with instant feedback
  - Error overlay surfaces runtime issues directly in browser

- **Conventions**: Clear (file-based routing + 'use client')
  - Server vs client boundary explicit and linter-enforceable
  - Standard patterns for data fetching, mutations
  - ESLint + Prettier enforce consistency automatically

- **Modularity**: High (file-based routing + component isolation)
  - One file per route, one file per component
  - AI adds new pages without touching existing routes

- **Multi-Agent**: Compatible (file-per-route reduces conflicts)
  - Parallel agents rarely modify same files
  - Component interfaces serve as natural boundaries

### Negative

- **Training Data Gap**: Next.js 15 App Router recent (limited LLM coverage)
  - Official docs at vercel.com/docs/app (structured, reference-grade)
  - Reference app in examples/ demonstrates common patterns
  - Agent should test doc retrieval before rating coverage

- **Build-Time Errors**: Some errors only surface at build time
  - Slower feedback loop than compile-time (TypeScript)
  - Watch mode available via `npm run dev` for faster iteration

- **AI Learning Curve**: Server Components have patterns AI models commonly get wrong
  - async/await in server components vs useEffect in client
  - Linting rules for 'use client' boundary enforcement
  - Reference examples document correct patterns
```

Feedback loops, error quality, documentation accessibility, executability, modularity, and mitigation strategies drive the evaluation.

---

## What Traditional ADRs Consider (Reinterpreted for AI)

These traditional factors are **not irrelevant** — they are **reinterpreted** in AI-driven development:

| Traditional Factor | Traditional Meaning | AI-Centric Reinterpretation |
|---|---|---|
| **Team familiarity** | Can the team build with this? | **Reviewability**: Can humans review and understand what AI produces? A widely-understood technology is easier to review, even if AI writes all the code. |
| **Learning curve** | How long to become productive? | **AI learning curve**: How many iterations does the AI need to produce correct output? Technologies with subtle gotchas or patterns AI commonly gets wrong have a steep AI learning curve. |
| **Hiring availability** | Can we find developers? | **Reviewer pool**: Can we find humans who can effectively review this technology? Niche technologies limit the reviewer pool. |
| **Developer preferences** | What does the team prefer? | **Training data quality**: AI models produce better code for technologies with abundant, high-quality training data. This functions similarly to a preference — it affects output quality. |
| **Onboarding time** | How long to ramp up? | **Documentation accessibility**: Can the AI access and consume documentation at implementation time? Machine-readable, structured docs beat tribal knowledge. |

---

## Integration with ADR Creation

Use these principles when creating ADRs with `adr_create()`:

1. **Alternatives Analysis**: Compare error quality, type safety, executability, documentation accessibility, modularity, reversibility, and multi-agent compatibility
2. **Decision Rationale**: Explain why the choice is optimal for both the project's purpose *and* AI-driven implementation
3. **Consequences**: Document feedback loops, runtime observability, mitigation strategies, known AI pitfalls, and security posture
4. **Policy Blocks**: Enforce decisions automatically (see POLICY-FORMAT.md)

---

## See Also

- [Policy Format Guide](POLICY-FORMAT.md) - Structured policy enforcement
- [Workflows Guide](WORKFLOWS.md) - ADR Kit workflows
- [ADR Kit README](../README.md) - Getting started

---

**Philosophy in Practice**

ADR Kit doesn't just document decisions - it **enforces them** through:
- Preflight checks (policy gate)
- Automatic lint rule generation
- Contract validation
- Planning context for agents

This guide explains *why* we evaluate technologies differently. The tools enforce those evaluations automatically.
