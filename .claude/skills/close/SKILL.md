---
name: close
description: Finalize an atomic step — distill context, commit, and (on final step) update tracking and suggest next
allowed-tools: Read, Bash, Edit, Write, Glob, Skill
---

Finalize a completed atomic step. May be called **multiple times per session** — once per step. On the final step, also updates tracking and suggests next steps.

**Context**: $ARGUMENTS
(May contain: summary of what was implemented and why, passed from `/next`)

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

## 3. Commit

Invoke: `Skill(skill="commit", args="<distilled context from step 2>")`

Pass the full distilled summary as `$ARGUMENTS` so `/commit` has real reasoning for the commit message body.

## 4. Intermediate or Final?

Check the TodoWrite plan from `/next`:

**Intermediate step** (more steps remain in the plan):
→ Return to implementation. Do NOT update tracking, do NOT archive, do NOT suggest next steps. The calling skill (`/next`) continues with the next step.

**Final step** (all steps in the plan are complete, or this is the only step):
→ Proceed to step 5.

**Session ending early** (context running low, not all steps done):
→ Write a [handover note](#handover-notes) into the backlog file, then proceed to step 6 (suggest next step) without updating tracking or archiving.

## 5. Update Tracking (Final Step Only)

**Backlog file**: Set `Status: DONE` and `Completed: <today's date>`
**Move** backlog file to `archive/` (e.g. `backlog/CRA-*.md` → `archive/CRA-*.md`)
**task-tracking.md**:
  - Remove the row from the Priority Queue table
  - Add entry to "Done" section with date and brief summary
  - Remove this task's ID from "Depends On" column of any tasks that depended on it
  - Update test count in header if tests were added

## 6. Smart Next-Step Suggestion (Final Step or Session Ending)

After updating tracking (or after writing a handover note), read the priority queue to see what task comes next.

Run branch-context to understand the current state:
```bash
bash scripts/branch-context.sh
```

**If the next task relates to the current branch's theme** (similar area, branch has few commits):
→ Suggest: "The next task ([task title]) fits this branch's theme. Open a new chat and run `/next` to continue."

**If the next task is a different area, or the branch already has several commits (3+)**:
→ Suggest: "This branch has [N] commits covering [theme]. Consider running `/pr` to close this chapter, then `/next` in a fresh session."

**Never suggest `/next` in the same session.** Each task = fresh context window. Always recommend opening a new chat.

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
