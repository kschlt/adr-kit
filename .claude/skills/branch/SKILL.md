---
name: branch
description: Autonomous branching strategy — evaluate fit, create, continue, or escalate
allowed-tools: Bash
---

Manage branch strategy autonomously. Make routine decisions silently; only escalate to the human when genuinely uncertain.

**Task context**: $ARGUMENTS
(May contain: task description, theme, or area of work)

---

## Phase 1: Gather Context

### Step 1: Gather Branch Landscape

```bash
bash scripts/branch-context.sh
```

Parse the structured output: `cleaned-up`, `branch`, `clean`, `status`, `pushed`, `commit-count`, `commits`, `files-changed`, `wip-branches`.

**If dirty working tree** (`clean: no`): STOP. Ask the user what to do (commit or stash). Never make branching decisions with uncommitted changes.

### Step 2: Gather Task Theme

**Context contract** — to make a branching decision, the agent needs: (1) the branch landscape (from step 1) and (2) the task theme. The task theme is where the tiers apply. Stop at the earliest tier that fulfills the contract.

**Tier 1 — Mechanical**: `$ARGUMENTS` provides the task theme directly. Contract complete. Proceed to Phase 2.

**Tier 2 — Agent reasoning**: No `$ARGUMENTS` (empty or literal `"$ARGUMENTS"`). Derive the task theme from what's already available, in this order:

1. **Branch landscape** — if WIP branches exist, their names, commit subjects, and changed files suggest the thematic area. If there's only one WIP branch, it's likely where work should continue.
2. **Conversation context** — what the human said earlier in this session may indicate what they want to work on.
3. **Task tracking** — `.agent/task-tracking.md` lists the current priority queue, which may indicate the next task's theme.

If the agent can confidently determine the theme from these sources, the contract is complete. Proceed to Phase 2.

**Tier 3 — Human input**: The agent has partial information but isn't confident. Present what it knows — "I see [WIP branch X] with commits about [topic], and the next task in the queue is [Y]" — and ask specifically for what's missing. Do NOT create a branch without knowing the theme.

---

## Phase 2: Decide and Act

Only proceed once the contract is complete — branch landscape + task theme are both known.

### Step 3: On Main

If `status: on-main`:

#### No WIP branches, has task theme

Create a thematic branch silently.

1. Update main first:
   ```bash
   git pull origin main
   ```
2. Choose a branch name:
   - **Broad enough** to accommodate related follow-up tasks — name the chapter, not one task
   - Prefixes: `feat/`, `fix/`, `docs/`, `chore/`
   - Kebab-case, descriptive of the thematic area
   - Good: `feat/ai-steering-enhancements`, `fix/schema-validation-edge-cases`
   - Bad: `feat/cra-create-analyze` (too narrow, one task ID)
3. Create:
   ```bash
   git checkout -b <branch-name>
   ```
4. Report: "Created branch `<branch-name>`"

#### One WIP branch fits task theme

The WIP branch's name, commits, and changed files align with the task theme. Switch to it silently:

```bash
git checkout <wip-branch>
```

Report: "Switched to `<wip-branch>` — task fits the existing work."

#### One WIP branch doesn't fit task theme

The WIP branch exists but covers a different area. Escalate:

"There's an existing branch `<wip-branch>` with [N] commits about [topic]. The new task is about [new theme]. I recommend running `/pr` to close that branch first, then starting fresh on main. New branches should always start from the latest main."

#### Multiple WIP branches

Escalate — present the landscape and let the human decide:

"There are multiple WIP branches:
- `<branch-1>`: [N] commits about [topic]
- `<branch-2>`: [N] commits about [topic]

Which branch should we continue on, or should we `/pr` one or more of them first?"

### Step 4: On Feature Branch

If `status: on-feature`:

Compare the task theme against the branch's theme (name + existing commits + files changed).

**Clearly fits** — the task is in the same thematic area:
→ Continue silently. Report: "Continuing on `<branch-name>` — task fits the current theme."

**Branch name is too narrow** — the task fits thematically but the branch name is task-specific rather than thematic:
→ Check if branch is pushed to remote.
- **Not pushed**: Rename automatically:
  ```bash
  git branch -m <new-thematic-name>
  ```
  Report: "Renamed branch to `<new-thematic-name>` to better reflect the scope."
- **Already pushed**: Keep current name. Report that the name is narrower than ideal but renaming a pushed branch is disruptive.

**Clearly doesn't fit** — different topic, unrelated area, or branch already has 5+ commits:
→ Escalate to human with specific guidance:
"This branch covers [current theme — based on name + commits]. The new task is about [new task theme]. I recommend running `/pr` to close this branch first, then starting fresh on main."

**Genuinely ambiguous** — could go either way:
→ Ask the human. Present what's on the branch and what the new task is. Let them decide.

---

## Decision Summary

| Situation | Action |
|-----------|--------|
| On main, no WIP branches, has theme | Create branch silently |
| On main, one WIP branch fits theme | Switch to it silently |
| On main, one WIP branch doesn't fit | Escalate: recommend `/pr` first |
| On main, multiple WIP branches | Escalate: present landscape, let human decide |
| On feature, task fits | Continue silently |
| On feature, name too narrow (unpushed) | Auto-rename, continue |
| On feature, name too narrow (pushed) | Note it, continue |
| On feature, doesn't fit | Recommend `/pr` first |
| On feature, ambiguous | Ask the human |
