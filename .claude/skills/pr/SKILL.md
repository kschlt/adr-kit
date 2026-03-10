---
name: pr
description: Create a human-readable PR from the current feature branch
allowed-tools: Bash, Read, Glob
context: fork
---

Create a pull request from the current feature branch. The PR is the human review gate — it must be easy for a human to understand with minimal cognitive load.

**Context**: $ARGUMENTS
(May contain: summary of what the branch accomplished, passed from /close or provided directly)

## 1. Verify

```bash
git branch --show-current
```

Must be on a feature branch (not `main`). If on main: STOP. Run `scripts/branch-context.sh` to gather the branch landscape. If feature branches exist, present them and ask which one to PR:

"You're on main — no feature branch to PR from. But I see these feature branches:
- `<branch-1>`: [N] commits about [topic]
- `<branch-2>`: [N] commits about [topic]

Which branch would you like to create a PR from?"

If no feature branches exist: "You're on main and there are no feature branches. Nothing to PR."

## 2. Sync with Main

```bash
git checkout main && git pull origin main && git checkout - && git rebase main
```

If rebase conflicts occur: STOP and help resolve. Do not proceed with unresolved conflicts.

## 3. Run Quality Suite

```bash
make quality
```

This runs format + lint + tests (~37s). It's the final gate before the PR goes out.

If anything fails: fix it, commit the fix, then re-run `make quality` until it passes. Do not proceed with failing quality checks.

## 4. Gather Context

Collect the raw material:
```bash
git log main..HEAD --format="%s%n%n%b" --reverse
```

**Context contract** — the agent needs four pieces: (1) why this work was done, (2) what approach was taken and why, (3) what was tested, and (4) what risks exist. Stop at the earliest tier that fulfills the contract.

**Tier 1 — Mechanical**: `$ARGUMENTS` + `git log main..HEAD` commit bodies have the reasoning. When `$ARGUMENTS` are rich or commit bodies explain *why* — the typical case when `/commit` was used with good context upstream — the contract is fulfilled without needing the full diff. Proceed to write the PR.

**Tier 2 — Agent reasoning**: Tier 1 produces gaps — commit bodies have the *what* but not the *why*, or trade-offs aren't documented. Gather the actual changes:

```bash
git diff main..HEAD
```

Reason over the diff alongside the log. If the agent can fill the gaps confidently without fabricating, it does. Proceed to write the PR.

**Tier 3 — Human input**: The agent would have to fabricate reasoning. Present what it *can* see:
- "This branch has N commits touching [modules]. The changes appear to [summary]."
- Ask for the gaps: "Can you explain the motivation and any key trade-offs, so the PR description is accurate?"

Use the human's response to fill in Why and Approach. Derive What Was Tested from test files in the diff. Assess Risks from the scope of changes.

## 5. Push + Create or Update PR

Once the context contract is complete, push changes:

```bash
git push -u origin HEAD
```

Check if a PR already exists for this branch:

```bash
gh pr list --head $(git branch --show-current) --json number,title
```

**If PR exists**: Update it with new commits (no action needed - commits are already pushed).
Report: "PR #N updated with new commits. Review at [URL]"

**If no PR exists**: Create a new one:

```bash
gh pr create --title "<concise title describing the chapter>" --body "$(cat <<'EOF'
## Why
<2-3 sentences: what problem this solves and why it matters now>

## Approach
<Key design decisions, patterns used, trade-offs made. Not what files
 changed — the reviewer sees that — but the reasoning behind the
 approach so they can evaluate if it's sound.>

## What Was Tested
<Specific scenarios that were verified, not pass counts. E.g.:
 - Tested X with Y conditions
 - Verified Z edge case
 The reviewer reads this and thinks: "they covered X but not Y,
 let me check Y myself.">

## Risks
<What could go wrong. Edge cases. What to pay extra attention to.
 If low risk: "Additive changes only, no existing behavior modified.">
EOF
)"
```

**PR content rules** — only include what GitHub doesn't already show:
- Don't list files changed (GitHub shows that)
- Don't say "N tests passed" (CI shows that)
- Focus on reasoning, approach, test coverage, and risks

## 6. Switch to Main

```bash
git checkout main && git pull origin main
```

## 7. Report

Output the PR URL and:
"PR created. Review and merge in GitHub, then open a new chat and say 'work on next task' to continue."
