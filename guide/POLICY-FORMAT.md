# ADR Policy Block Format Guide

**Last Updated**: 2026-02-07

This guide clarifies the correct format for structured policy blocks in ADR frontmatter, addressing common misconceptions and providing clear examples.

---

## Issue Background

**Issue #2** from production feedback reported that `adr_preflight` seemed to return generic responses instead of using specific ADR policies. Investigation revealed this was primarily a **documentation gap** rather than a bug.

### Key Findings

1. ✅ **Policy extraction DOES work** from structured frontmatter blocks
2. ✅ **Pattern matching fallback works** when no structured policy exists
3. ✅ **Preflight checking works** and correctly identifies conflicts
4. ❌ **Users were using incorrect policy format** due to lack of clear documentation

---

## Correct Policy Format

### Schema Structure

The policy block in ADR frontmatter must follow this structure:

```yaml
policy:
  imports:           # For general import/library policies
    disallow:        # List of disallowed libraries
      - library1
      - library2
    prefer:          # List of preferred libraries
      - library3
  python:            # For Python-specific policies
    disallow_imports:  # List of disallowed Python modules
      - module1
      - module2
  boundaries:        # For architectural boundary rules
    layers:          # Optional layer definitions
      - name: ui
        path: src/ui
    rules:           # Boundary violation rules
      - forbid: "ui -> database"
  rationales:        # Reasons for the policies
    - "Rationale 1"
    - "Rationale 2"
```

### Complete Example

```yaml
---
id: ADR-0001
title: Use FastAPI for Backend
status: accepted
date: 2025-01-15
deciders:
  - backend-team
tags:
  - backend
  - framework
  - python
policy:
  imports:
    disallow:
      - flask          # Don't use Flask
      - django         # Don't use Django
      - bottle         # Don't use Bottle
    prefer:
      - fastapi        # Use FastAPI
  python:
    disallow_imports:
      - urllib         # Don't use urllib
      - requests       # Don't use requests (use httpx)
  rationales:
    - "FastAPI provides native async support required for our I/O-heavy workloads"
    - "Automatic OpenAPI documentation reduces maintenance burden"
    - "Better type safety with Pydantic integration"
---

## Context

We need a modern Python web framework...
```

---

## Common Mistakes

### ❌ Mistake 1: Using `prefer_imports` in `python` block

**Incorrect**:
```yaml
policy:
  python:
    disallow_imports: [flask, django]
    prefer_imports: [fastapi]  # ❌ WRONG - no such field
```

**Correct**:
```yaml
policy:
  imports:
    prefer: [fastapi]  # ✅ Preferences go in 'imports' block
  python:
    disallow_imports: [flask, django]  # ✅ Only disallow_imports in python block
```

### ❌ Mistake 2: Adding unsupported fields

**Incorrect**:
```yaml
policy:
  python:
    disallow_imports: [flask]
    patterns:  # ❌ Not supported
      async_handlers: {...}
  typescript:  # ❌ Not supported
    strict: true
  files:  # ❌ Not supported
    require: [config.json]
```

**Correct**:
```yaml
policy:
  imports:
    disallow: [flask]
  rationales:
    - "Use async handlers for all routes"  # Document patterns in rationales or content
```

### ❌ Mistake 3: Mixing general and Python-specific imports

**Incorrect**:
```yaml
policy:
  python:
    disallow_imports: [axios, jquery]  # ❌ These are JS libraries, not Python
```

**Correct**:
```yaml
policy:
  imports:
    disallow: [axios, jquery]  # ✅ General imports (JS/TS libraries)
  python:
    disallow_imports: [urllib, requests]  # ✅ Python-specific modules
```

---

## Supported Fields

### `imports` Block

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `disallow` | list[str] | Libraries/packages to avoid | `["axios", "moment"]` |
| `prefer` | list[str] | Preferred alternatives | `["fetch", "date-fns"]` |

**Usage**: For general technology choices (JavaScript libraries, frameworks, tools).

### `python` Block

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `disallow_imports` | list[str] | Python modules to avoid | `["urllib", "requests"]` |

**Usage**: For Python-specific import restrictions.

**Note**: Python preferences go in the `imports.prefer` field, not in the `python` block.

### `boundaries` Block

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `layers` | list[Layer] | Layer definitions | `[{name: "ui", path: "src/ui"}]` |
| `rules` | list[Rule] | Boundary rules | `[{forbid: "ui -> database"}]` |

**Usage**: For architectural boundary enforcement.

### `rationales` Field

| Type | Description | Example |
|------|-------------|---------|
| list[str] | Reasons for policies | `["Better performance", "Smaller bundle"]` |

**Usage**: Document why these policies exist.

---

## Pattern Matching Fallback

If you **don't** provide structured policy blocks, ADR Kit will attempt pattern matching from your ADR content.

### Supported Patterns

**Disallow patterns**:
- "Don't use X"
- "Avoid X"
- "X is deprecated"
- "No longer use X"

**Preference patterns**:
- "Use Y instead of X"
- "Replace X with Y"
- "Prefer Y over X"

### Example

```markdown
## Decision

Use React for the frontend. **Don't use Vue or Angular** as they don't fit our
component model. **Prefer React over** other frameworks for consistency.
```

This will extract:
- `disallow`: ["Vue", "Angular"]
- `prefer`: ["React"]

**Note**: Structured policy blocks take priority over pattern matching.

---

## How Preflight Uses Policies

### 1. Load Constraints Contract

```python
# Preflight loads all approved ADRs and merges their policies
contract = ConstraintsContractBuilder(adr_dir=adr_dir).build()
```

### 2. Check for Conflicts

```python
# Check if choice is in disallow list
if "flask" in contract.constraints.python.disallow_imports:
    return PreflightDecision(status="BLOCKED", ...)
```

### 3. Return Decision

- `BLOCKED`: Choice conflicts with existing ADR policies
- `REQUIRES_ADR`: Significant choice not yet documented
- `ALLOWED`: Choice is compatible or pre-approved

---

## Testing Your Policy Format

Use these tests to verify your policy format:

```bash
# Test 1: Check if policy is extracted
adr-kit index --adr-dir docs/adr --no-validate
# Look for your ADR in the output - no errors = valid format

# Test 2: Build constraints contract
adr-kit contract-build
adr-kit contract-status
# Should show your constraints if format is correct

# Test 3: Test preflight with a disallowed choice
adr-kit preflight "flask" --context "backend framework"
# Should return BLOCKED if you disallowed flask
```

---

## Migration Guide

If you used the incorrect format (like in Issue #2), here's how to migrate:

### Before (Incorrect)

```yaml
policy:
  python:
    disallow_imports: [flask, django]
    prefer_imports: [fastapi]  # ❌ Wrong field
    patterns:  # ❌ Not supported
      async_handlers: true
```

### After (Correct)

```yaml
policy:
  imports:
    disallow: [flask, django]
    prefer: [fastapi]  # ✅ Moved to imports block
  python:
    disallow_imports: [flask, django]  # ✅ Python-specific
  rationales:
    - "FastAPI provides async support"  # ✅ Document patterns here
    - "All route handlers should be async functions"
```

---

## Validation

ADR Kit validates policy blocks during:

1. **ADR creation** (`adr_create`) - Pydantic validates frontmatter schema
2. **Index generation** (`adr-kit index`) - Skips malformed ADRs with errors
3. **Contract building** (`adr-kit contract-build`) - Only includes valid policies

### Common Validation Errors

**Error**: `Unknown field 'prefer_imports' in python policy`
- **Fix**: Move to `imports.prefer`

**Error**: `Unknown field 'patterns' in policy`
- **Fix**: Document patterns in `rationales` or ADR content

**Error**: `Unknown field 'typescript' in policy`
- **Fix**: Use `imports.disallow` for TS library restrictions

---

## FAQ

### Q: Can I restrict TypeScript-specific imports?

**A**: Use the general `imports` block. There's no separate `typescript` policy block.

```yaml
policy:
  imports:
    disallow: ["vite", "gatsby"]  # TypeScript/JavaScript libraries
    prefer: ["webpack", "next.js"]
```

### Q: Where do I document coding patterns?

**A**: Use `rationales` or ADR content. The `policy` block is for enforceable constraints only.

```yaml
policy:
  rationales:
    - "All async handlers must use try/except blocks"
    - "Use Pydantic models for all API request/response types"
```

### Q: Can I have both structured policy AND pattern matching?

**A**: Yes! Structured policy takes priority. Patterns are used as fallback.

```yaml
policy:
  imports:
    disallow: [axios]  # Explicit
# Content: "Don't use jQuery" -> Also extracted
```

Result: `disallow: ["axios", "jQuery"]` (merged)

---

## See Also

- [JSON Schema](../adr_kit/schemas/adr.schema.json) - Full technical specification
- [Test Examples](../tests/test_policy_extraction.py) - Comprehensive test cases
- [Policy Extractor](../adr_kit/core/policy_extractor.py) - Implementation details

---

**Questions or Issues?**

If you encounter policy extraction issues:

1. Validate your format against this guide
2. Check ADR Kit version (`adr-kit --version`)
3. Run tests: `pytest tests/test_policy_extraction.py -v`
4. Report issues at: https://github.com/anthropics/adr-kit/issues
