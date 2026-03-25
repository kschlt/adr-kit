---
name: close
description: Finalize an atomic step — distill context, commit, and (on final step) update tracking and suggest next
allowed-tools: Read, Bash, Edit, Write, Glob, Skill
---

Finalize a completed atomic step. May be called **multiple times per session** — once per step. On the final step, also updates tracking and suggests next steps.

**Universal session close capability**: Works for task workflow sessions, exploration sessions, mid-task pauses, and handles idempotency. Detects session state and takes appropriate action.

**Context**: $ARGUMENTS
(May contain: summary of what was implemented and why, passed from the conversational workflow)
(May also contain mode hints: "final", "step", "pause" to guide session state detection)

## 0. Detect Session State

Before proceeding, determine what kind of session this is by checking **observable artifacts** (files, git state) rather than conversation history. Skills don't have access to prior conversation context, so we rely on external state.

### Check 1: Is the working tree clean?

```bash
git status --porcelain
```

**If empty output** (working tree clean):
→ **Likely already closed** - Proceed to Step 0e to confirm

**If has output** (changes exist):
→ Continue to Check 2

### Check 2: Is there task context?

Check for task workflow artifacts:

```bash
# Check current branch first
git branch --show-current
```

**If branch is main**:
→ Not actively working on a task (either task complete or exploration) → Continue to Check 3

**If branch is NOT main** (feature/task branch):
→ Check for task tracking:

```bash
test -f .agent/task-tracking.md && grep -A 5 "Priority Queue" .agent/task-tracking.md
```

**If task-tracking exists**:
→ This is likely a **task workflow session** → Continue to Step 1 (normal flow)

**If no task-tracking**:
→ Continue to Check 3

### Check 3: Is there uncommitted work?

From Check 1, we know if there are changes. Now determine context:

**If changes exist but no task context found**:
→ **Route to: Dirty Tree (Step 0d)** - Changes without clear task context

**If no changes and no task context**:
→ **Route to: Exploration Session (Step 0c)** - Session without committed work

---

## 0c. Exploration Session (No Task Context)

This session wasn't working on a tracked task from `.agent/task-tracking.md`. This is an exploration, research, or question-answering session.

Ask user: "This session wasn't working on a tracked task. Would you like to save any notes or findings from this session?"

**If yes**:
- Ask: "Where should I save these notes?"
  1. New file in `.agent/input/session-notes-YYYY-MM-DD.md`
  2. Append to an existing backlog file (ask which one)
  3. Just remember for next session (I'll mention it)
- Write notes as requested, include date and brief session summary

**If no**:
- Confirm: "No notes saved. Session closed cleanly. You can start a new session anytime."

**Check working tree**: If there are uncommitted changes, offer:
"You have uncommitted changes. Would you like to commit them before closing? I'll use Tier 3 escalation to gather context."

Exit skill after handling. No tracking update needed.

---

## 0d. Dirty Tree with No Clear Context

You have staged or unstaged changes, but no clear task context from TodoWrite or task-tracking.

Present options to user:

**Options:**
1. **Commit now** → I'll escalate to Tier 3 (ask for commit message context) and create a commit
2. **Stash for later** → `git stash push -m "Session paused YYYY-MM-DD"`
3. **Continue working** → Don't close yet, keep this session open
4. **Discard changes** → `git restore .` (warning: this is destructive)

Wait for user choice, then execute:

**Choice 1 (Commit)**:
- Use AskUserQuestion tool: "Please provide context for this commit: What was the goal? What approach was taken? What was tested?"
- Once user provides context, invoke: `Skill(skill="commit", args="<user-provided context>")`
- Confirm commit created, session closed

**Choice 2 (Stash)**:
```bash
git stash push -m "Session paused $(date +%Y-%m-%d)"
```
- Confirm: "Changes stashed. Session closed. Run `git stash pop` to resume."

**Choice 3 (Continue)**:
- Confirm: "Session still open. Call `/close` again when ready to close."
- Exit skill, don't close session

**Choice 4 (Discard)**:
```bash
git restore .
git clean -fd
```
- Confirm: "Changes discarded. Session closed."

Exit skill after handling. No tracking update needed.

---

## 0e. Likely Already Closed (Clean Working Tree)

The working tree is clean (no uncommitted changes). This suggests either:
1. The session was already closed with `/close`
2. No work was done this session
3. All work was committed manually

**Check branch and task context**:
```bash
git branch --show-current
test -f .agent/task-tracking.md && echo "Task tracking exists" || echo "No task tracking"
```

**If on main branch with clean tree**:
- Either task was completed and merged/PR'd, or no task was active
- Confirm: "Working tree is clean and on main branch. Session appears complete. Safe to start a new session."
- Exit skill

**If on feature branch with task tracking**:
- This might be mid-task (just committed a step)
- Or task is complete
- Ask user: "Working tree is clean. Is this task complete, or do you want to continue working?"
  - **Complete**: Continue to Step 1 (final close flow)
  - **Continue**: Exit with "Session remains open. Call `/close` when ready."

**If no task tracking**:
- Confirm: "Session appears complete. Working tree is clean, no task in progress. Safe to start a new session."
- Exit skill

---

## 1. Identify the Task

```bash
git branch --show-current
```

Read `.agent/task-tracking.md` to identify which task is being worked on (match by branch theme or current priority).
Read the backlog file for the task title and ID.

## 2. Distill Context

Before committing, review what happened during **this step** and construct a summary. This is a reasoning step — derive the summary from the session's actual work, not generic filler. Each step gets its own context; don't bundle reasoning from earlier steps.

The summary must cover:
- **Goal**: What was this step trying to achieve?
- **Approach and reasoning**: What approach was taken and why?
- **Alternatives considered**: What was rejected and why?
- **What was tested**: Which scenarios were verified?
- **Risks**: What could go wrong or what's left unaddressed?

This doesn't need to be exhaustive — a few sentences covering the key points. But it must be *real*, derived from the actual session.

**Example** — what a good summary looks like:
```
Added LRU caching to KnowledgeLoader because loading evaluation criteria
from disk on every preflight call was adding ~200ms. Chose LRU over TTL
because the data files are static within a session. Tested with empty cache,
full cache, and cache invalidation on file change. Risk: cache is not
invalidated if data files are edited mid-session, but this is acceptable
since data files only change between releases.
```

Use `$ARGUMENTS` if provided — it may already contain this context. If `$ARGUMENTS` is empty or thin, derive the summary from `git diff --staged` or `git diff main..HEAD` and the session conversation.

## 3. Verify Quality (Optional but Recommended)

If you modified implementation code (not just docs/tests), consider running relevant tests before committing. This catches test failures earlier than the `/pr` quality gate.

**When to run tests**:
- ✅ Modified implementation in `adr_kit/`
- ✅ Refactored existing functionality
- ❌ Changed only documentation or comments
- ❌ Changed only test files (tests will run in quality suite)

**How to run tests**:
```bash
# Run tests for specific module
pytest tests/unit/test_foo.py -v

# Or run full unit test suite (fast)
pytest tests/unit/ -x --tb=line
```

**Why this matters**: Catching test failures here is faster than at `/pr` time. The `/pr` quality gate will catch failures eventually, but fixing them earlier means cleaner commit history.

## 4. Commit

Invoke: `Skill(skill="commit", args="<distilled context from step 2>")`

Pass the full distilled summary as `$ARGUMENTS` so `/commit` has real reasoning for the commit message body.

## 5. Intermediate, Final, or Mid-Task Pause?

At this point, a commit has been created. Now determine if the task is complete or if there's more work.

### Check for mode hints in $ARGUMENTS

If `$ARGUMENTS` contains:
- `"final"` → Explicitly marked as final step → Proceed to Step 6
- `"step"` or `"intermediate"` → Explicitly intermediate → Return to workflow (see below)
- `"pause"` → Explicitly pausing → Write handover note, skip to Step 7

### If no explicit hint, infer from state

Read the backlog file for this task (identified in Step 1):

```bash
# Check task status in backlog
grep "^Status:" .agent/backlog/<task-file>.md
```

**If Status is `DONE`**:
→ Task was already marked complete, treat as final → Proceed to Step 6

**If Status is `IN PROGRESS`** or other:
→ Ask user: "Is this the final step for this task, or are there more steps?"
  - **Final**: Proceed to Step 6
  - **Intermediate**: Return to workflow (see below)
  - **Pause**: Write handover note, skip to Step 7

### Route based on determination

**Final step** (all steps in the plan are complete, or this is the only step):
→ Proceed to Step 6 (update tracking, archive)

**Intermediate step** (more steps remain, user wants to continue):
→ Confirm: "Step committed. Continuing work in this session."
→ Return control to conversational workflow
→ Do NOT update tracking, do NOT archive, do NOT suggest next steps

**Mid-task pause** (stopping now, will resume later):
→ Write a [handover note](#handover-notes) into the backlog file
→ Task remains in `backlog/` with status `IN PROGRESS`
→ Proceed to Step 7 (suggest next step) **without archiving**

## 6. Update Tracking (Final Step Only)

**Backlog file**: Set `Status: DONE` and `Completed: <today's date>`
**Move** backlog file to `archive/` (e.g. `backlog/CRA-*.md` → `archive/CRA-*.md`)
**task-tracking.md**:
  - Remove the row from the Priority Queue table
  - Add the task's ID + ✅ to the **Baseline** summary line in the header
  - Remove this task's ID from "Depends On" column of any tasks that depended on it
  - Update test count in header if tests were added
**CHANGELOG.md** (source of truth for what changed):
  - Add user-facing changes to the `[Unreleased]` section under the appropriate heading (Added/Changed/Fixed/Removed)
  - Write from the user's perspective — what the feature does, not implementation details
  - Skip purely internal changes (dev tooling, .agent/ updates, workflow tweaks) unless they affect the installed package

## 7. Smart Next-Step Suggestion (Final Step or Session Ending)

After updating tracking (or after writing a handover note), read the priority queue to see what task comes next.

Run branch-context to understand the current state:
```bash
bash scripts/branch-context.sh
```

**If the next task relates to the current branch's theme** (similar area, branch has few commits):
→ Suggest: "The next task ([task title]) fits this branch's theme. Open a new chat and say 'work on next task' to continue."

**If the next task is a different area, or the branch already has several commits (3+)**:
→ Suggest: "This branch has [N] commits covering [theme]. Consider running `/pr` to close this chapter, then say 'work on next task' in a fresh session."

**Never continue task work in the same session.** Each task = fresh context window. Always recommend opening a new chat.

## Handover Notes

If the session is ending before the task is fully complete, write a handover note in the backlog file. This is the next session's starting context — without it, the next session starts from scratch and may redo work, make contradictory decisions, or miss context that only existed in the conversation.

The handover must capture:
- What has been done so far (which steps completed)
- What remains to be done (which steps are left)
- Key decisions made and why
- What was tried and didn't work
- The human's guidance and preferences from this session
- Concerns or risks identified

The most important thing to preserve is the *reasoning* — code changes are in the working tree, but the reasoning exists only in the conversation and must be written down.
