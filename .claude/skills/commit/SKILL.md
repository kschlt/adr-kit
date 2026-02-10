---
name: commit
description: Create a conventional commit — with atomic commit gate that checks quality before committing
allowed-tools: Bash
context: fork
---

Create a git commit with conventional commit format. Gathers context first, then validates atomicity and writes the commit.

**Context**: $ARGUMENTS
(May contain: staging instructions, or commit context about what/why changes were made)

## Step 1: Stage

Stage all changes, excluding `.agent/` (local task tracking, never committed):

```bash
git add --all
git reset HEAD .agent/
```

- If context provides specific staging instructions: Follow those instead.

Review what's staged:
```bash
git diff --staged
```

This provides the first piece of the context contract: what changed, which files, which modules. Always mechanical.

## Step 2: Gather Context

**Context contract** — to write a meaningful commit, the agent needs: (1) what changed (the staged diff from step 1) and (2) the full context — why it changed, whether it's one concern, whether it's self-contained. The second part serves double duty: the same context that tells the agent *why* also tells it whether the diff is atomic. Stop at the earliest tier that fulfills the contract.

**Tier 1 — Mechanical**: `$ARGUMENTS` provides the reasoning, `git diff --staged` provides the technical details. Together they typically answer both "is this one concern?" and "why was this done?" Contract complete. Proceed to step 3.

**Tier 2 — Agent reasoning**: No `$ARGUMENTS`. Derive context from what's available:

1. **Staged diff** — what files changed, what code was added/removed/modified.
2. **Git log** — `git log --oneline -5` provides context for what's been happening on this branch.
3. **Session conversation** — if the agent made the changes itself, it has the full reasoning in context.

Self-explanatory changes — clear bug fixes, renames, test additions — resolve here. If the agent can write an accurate commit body and confirm atomicity, the contract is complete. Proceed to step 3.

**Tier 3 — Human input**: Can't confidently determine either atomicity or the "why." Present what the agent *can* see and ask for the gaps:

- "I see [what the diff shows]. This looks like [inference]. Is this correct?"
- "What problem did this solve?" / "Were there alternatives you considered?"

**The threshold**: Would the commit body contain fabricated reasoning if you don't ask? If yes, ask. If you can write something accurate (even if not perfectly detailed), proceed.

## Step 3: Validate Atomicity (Atomic Commit Gate)

With full context gathered, validate the staged diff is atomic. This is a reasoning step over the diff already loaded in step 1 — NOT a separate investigation phase. No extra file reads, no extra tool calls. If any check fails, STOP and report what needs to be fixed.

Validate two constraints:

**Single concern** — Do all changes relate to one logical purpose? Scan the file paths in the staged diff. Do they cluster around one area/module, or are unrelated modules mixed in?
- Red flags: changes in `adr_kit/core/` AND `adr_kit/mcp/` for unrelated reasons; a bug fix mixed with a feature; formatting-only changes alongside logic changes.
- A broad diff isn't a problem by itself (a rename across many files is fine) but is a signal to look closer at whether multiple concerns are mixed.
- How to check: look at the file paths already visible in `git diff --staged`. No extra reads needed.
→ If mixed: report which files don't belong, suggest splitting.

**Self-contained** — Does the commit include everything needed to be complete on its own?

- **Completeness**: Does this commit deliver standalone value, or is it half-finished work that only makes sense with a future commit?
- **Tests**: If behavior was added or changed, are tests included that cover that specific behavior — not just exist alongside it? Check if `tests/` files appear in the staged diff alongside `adr_kit/` implementation changes. Exception: pure refactors that don't change behavior, or changes to non-code files (docs, configs).
  → If missing: report which implementation changes lack tests.
- **Documentation**: If the change introduces something significant — a new architectural pattern, a major design decision, a core abstraction — evaluate whether documentation exists. If not, escalate: surface what you identified as significant, propose where and how to document it, and let the human decide. Don't do a deep documentation audit — if the staged diff includes changes to public APIs (new parameters, changed return types, removed functions), check whether docstrings in those same files were updated. This is visible in the diff you already have. Don't read external doc files to cross-reference.

If both constraints pass, proceed to step 4.

## Step 4: Write the Commit

Once the contract is complete and atomicity is confirmed, create the conventional commit:

Format: `<type>(<scope>): <description>`

Body: Explain WHY (not what — that's visible in diff)

- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Scope: optional (e.g., `mcp`, `cli`, `core`)
- Description: imperative, lowercase, no period
- Body: Explain the reason/motivation for the change

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <description>

Why this change was made: <reasoning>
EOF
)"
```

The pre-commit hook will automatically check format + lint on staged files.
If it fails: inspect the hook output to see what failed and where, fix the issues, re-stage, and retry.

## Step 5: Confirm

```bash
git status
```
