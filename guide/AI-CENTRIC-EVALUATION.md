# AI-Centric ADR Evaluation Guide

**Purpose**: Guide for evaluating architectural decisions in AI-driven development environments

**Last Updated**: 2026-02-08

---

## Overview

Traditional ADR evaluation criteria focus on human team dynamics (familiarity, learning curve, hiring). In AI-driven development, we need different criteria focused on **how well AI can understand, implement, and maintain** the technology.

---

## AI-Centric Evaluation Criteria

### 1. LLM Training Data Coverage

**What to evaluate:**
- Is this technology well-represented in LLM training corpora?
- Are there extensive official docs and examples available?
- How recent is the documentation (newer = better training data)?

**Examples:**
- ✅ **Excellent**: React, FastAPI, PostgreSQL (extensive docs, widely used)
- 🟡 **Moderate**: Newer frameworks (Next.js 15, Astro 4)
- ❌ **Limited**: Proprietary tools, internal company frameworks

### 2. Type Safety & Static Analysis

**What to evaluate:**
- Can errors be caught at compile/build time vs runtime?
- Does it support strong typing (TypeScript, Pydantic, etc.)?
- Are contracts validated automatically?

**Examples:**
- ✅ **Strong**: TypeScript strict mode, Pydantic v2, Rust
- 🟡 **Partial**: Python with type hints (optional), JavaScript with JSDoc
- ❌ **Weak**: Plain JavaScript, Ruby, shell scripts

### 3. Error Message Quality

**What to evaluate:**
- Are error messages descriptive and actionable?
- Can AI diagnose issues from stack traces?
- Do errors include suggestions for fixes?

**Examples:**
- ✅ **Excellent**: Rust compiler, Next.js error overlay, Pydantic validation errors
- 🟡 **Adequate**: Python tracebacks, TypeScript errors
- ❌ **Poor**: "Something went wrong", generic 500 errors

### 4. Documentation Quality

**What to evaluate:**
- Is documentation comprehensive and up-to-date?
- Are there clear getting-started guides?
- Is API reference complete with examples?

**Examples:**
- ✅ **Comprehensive**: Django, React, FastAPI
- 🟡 **Good**: Most mainstream frameworks
- ❌ **Sparse**: Legacy libraries, abandoned projects

### 5. Convention Clarity

**What to evaluate:**
- Are there standard, well-documented patterns?
- Is there "one clear way" to do things?
- Does it avoid "magic" behavior that's hard to reason about?

**Examples:**
- ✅ **Clear**: Django (conventions over configuration), Next.js App Router
- 🟡 **Flexible**: Flask (multiple ways to organize)
- ❌ **Inconsistent**: Legacy codebases with mixed patterns

### 6. Reference Implementation Availability

**What to evaluate:**
- Are there abundant open-source examples?
- Do official sources provide starter templates?
- Can AI find working code examples easily?

**Examples:**
- ✅ **Abundant**: React (thousands of examples), FastAPI (official examples)
- 🟡 **Some**: Newer frameworks with growing ecosystems
- ❌ **Rare**: Proprietary solutions, niche libraries

### 7. Debugging Ease

**What to evaluate:**
- Can issues be traced through clear stack traces?
- Are debugging tools available (DevTools, inspectors)?
- Can AI understand error sources?

**Examples:**
- ✅ **Easy**: React DevTools, Django Debug Toolbar, browser DevTools
- 🟡 **Moderate**: Basic logging and tracebacks
- ❌ **Difficult**: Black-box systems, minified code

### 8. Testability

**What to evaluate:**
- Is it easy to write unit/integration tests?
- Are there clear testing patterns?
- Can components be tested in isolation?

**Examples:**
- ✅ **High**: Pure functions, React components, FastAPI endpoints
- 🟡 **Medium**: Some coupling but testable
- ❌ **Low**: Tightly coupled, requires full system setup

---

## ADR Consequences Template

Use this template when documenting consequences in your ADRs:

```markdown
## Consequences

### Positive

- **LLM Training Data**: [Extensive | Moderate | Limited]
  - Description: [Why this matters for AI understanding]

- **Type Safety**: [Strong | Partial | Weak]
  - Description: [What errors are caught statically]

- **Error Quality**: [Descriptive | Adequate | Poor]
  - Description: [Examples of error messages]

- **Documentation**: [Comprehensive | Good | Sparse]
  - Description: [Quality of official docs and examples]

- **Conventions**: [Clear | Flexible | Inconsistent]
  - Description: [Standard patterns or multiple approaches]

- **Reference Code**: [Abundant | Some | Rare]
  - Description: [Availability of working examples]

- **Debugging**: [Easy | Moderate | Difficult]
  - Description: [Tools and clarity of errors]

- **Testability**: [High | Medium | Low]
  - Description: [Ease of writing and running tests]

### Negative

- **[Specific concern]**: Description
- **[Runtime-only errors]**: Description if applicable
- **[Magic behavior]**: Description if applicable
- **[Limited documentation]**: Description if applicable
```

---

## Real-World Example

### Before (Team-Centric)

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

### After (AI-Centric)

```markdown
## Consequences

### Positive

- **LLM Training Data**: Extensive
  - Next.js 15 well-documented in official docs and Vercel examples
  - Abundant training data in LLM corpus from documentation and examples

- **Type Safety**: Strong
  - TypeScript strict mode catches errors at compile time
  - React Server Components have clear type definitions

- **Error Quality**: Descriptive
  - Next.js provides detailed stack traces with suggestions
  - Error overlay shows exact file and line number

- **Documentation**: Comprehensive
  - Official Vercel docs are thorough with examples
  - Clear migration guides between versions

- **Conventions**: Clear
  - App Router has well-defined patterns
  - File-based routing is explicit and predictable
  - 'use client' markers make boundaries obvious

- **Reference Code**: Abundant
  - Vercel provides official example apps
  - Large community with open-source projects

- **Debugging**: Easy
  - React DevTools integration
  - Next.js error overlay with actionable suggestions
  - Clear separation of server vs client

- **Testability**: High
  - Server Components can be tested independently
  - Jest and React Testing Library work well
  - Clear boundaries make mocking easier

### Negative

- **Complexity**: More concepts than client-only React
  - Must understand SSR/CSR boundary (but well-documented)
  - Server vs Client Components require careful thought

- **Build-time validation**: Some errors only appear during build
  - Caught by CI, but not immediate in development
  - Type errors in server components appear at build time
```

---

## Evaluation Checklist

When evaluating a technical choice for an ADR, ask:

### Documentation & Training Data
- [ ] Is this technology well-represented in LLM training data?
- [ ] Are there extensive official docs with examples?
- [ ] Are conventions clearly documented?
- [ ] Is documentation up-to-date?

### Error Detection & Debugging
- [ ] Can errors be caught at compile/build time?
- [ ] Are error messages descriptive and actionable?
- [ ] Can AI diagnose issues from stack traces?
- [ ] Are debugging tools available?

### Type Safety & Validation
- [ ] Does it support strong typing?
- [ ] Are contracts validated automatically?
- [ ] Can static analysis catch bugs?
- [ ] Are types well-documented?

### Testing & Maintainability
- [ ] Is it easy to write unit/integration tests?
- [ ] Are there clear testing patterns and examples?
- [ ] Can AI-generated code be easily tested?
- [ ] Can components be tested in isolation?

### Conventions & Patterns
- [ ] Are there standard, well-documented patterns?
- [ ] Is there one clear way to do things?
- [ ] Does it avoid "magic" behavior?
- [ ] Are patterns consistent across the ecosystem?

---

## What NOT to Consider

These criteria are **irrelevant** in AI-driven development:

- ❌ **Team familiarity** - AI has access to all documentation
- ❌ **Learning curve for developers** - AI learns from training data, not experience
- ❌ **Hiring availability** - No human hiring in AI-driven development
- ❌ **Team preference** - AI has no preferences
- ❌ **Developer experience** - Focus on AI interpretability instead
- ❌ **Onboarding time** - AI can immediately access all documentation

---

## Integration with ADR Creation

When creating ADRs, use these criteria in:

1. **Alternatives Analysis**: Compare options using AI-centric metrics
2. **Decision Rationale**: Explain choice based on AI-friendly characteristics
3. **Consequences Section**: Use the template above for structured evaluation

Example decision rationale:

```markdown
## Decision

Use FastAPI for the backend framework.

### Rationale

FastAPI is optimal for AI-driven development:
- **LLM Training Data**: Extensive documentation and examples in training corpus
- **Type Safety**: Pydantic v2 provides automatic validation and clear error messages
- **Documentation**: Comprehensive official docs with interactive examples
- **Error Quality**: Validation errors are descriptive with exact field and reason
- **Testing**: Easy to write tests with TestClient and pytest
- **Conventions**: Clear patterns for routes, dependencies, and async handlers
```

---

## See Also

- [ADR Template](../README.md) - Standard ADR format
- [Policy Format Guide](POLICY-FORMAT.md) - Structured policy blocks
- [Workflows Guide](WORKFLOWS.md) - ADR Kit workflows

---

**Questions or Feedback?**

This guide is based on real-world experience with AI-driven development. If you have suggestions or additional criteria, please share!
