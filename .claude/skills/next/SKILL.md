---
name: next
description: Pick up the next priority task — check state, load task, delegate branching, decompose into atomic steps, implement
disable-model-invocation: true
---

Start a task from the priority queue. Delegates all branch decisions to `/branch`.

## 1. Check for Uncommitted Work

```bash
git status
```

If the working tree is dirty: address it first (commit or stash). Do not proceed with uncommitted changes.

## 2. Load Next Task

Read `.agent/task-tracking.md` → find Priority 1 (first row where "Depends On" = "—").
Read the linked backlog file → parse ID, title, requirements.
Display task summary. **Wait for user confirmation before proceeding.**

## 3. Branch

Invoke: `Skill(skill="branch", args="<task summary — title and thematic area>")`

The branch skill decides autonomously: create a new branch, continue on the current one, or escalate if the task doesn't fit. Follow whatever it says.

## 4. Research, Plan & Decompose

Read these in **parallel** (batch all reads in one message):
- `.agent/architecture.md`
- `.agent/vision.md`
- Relevant `adr_kit/` source files
- Relevant `tests/` files

Break the task into **atomic steps** using TodoWrite. Each step must be designed upfront as **one concern** — a self-contained chunk that delivers standalone value with:
- **Implementation** — the code changes for that one concern
- **Tests** — covering the behavior added or changed in this step
- **Documentation** — docstrings or docs if the step introduces something significant

The agent should know what each step contains and when to pause before moving on. Steps are not vague phases ("set up", "finalize") — they are concrete units of work.

**Context window awareness**: Size each step so it can be completed within the remaining context budget. Do not plan more steps than the session can handle. If the task is too large for one session:
- Plan only the steps that fit the current session
- Note remaining work in the backlog file so the next session can pick it up
- Prefer completing fewer steps cleanly over rushing through more steps poorly

## 5. Implement Step by Step

For each atomic step in the TodoWrite plan:

1. **Implement** — Write code in `adr_kit/`, tests in `tests/`.
2. **Verify** — Run `make test-unit` to confirm tests pass.
3. **Close the step** — Invoke `Skill(skill="close")` to commit and finalize.
4. **Evaluate** — After `/close` returns:
   - **More steps remain AND context budget allows?** → Continue to the next step.
   - **Context running low?** → Do NOT start the next step. Write a [handover note](#handover-notes) and end the session cleanly. Prioritize finalizing cleanly over rushing into the next step.
   - **Final step just completed?** → `/close` handles tracking updates and next-step suggestion. Session is done.

### Handover Notes

If the session must end before all steps are complete (context window running low, or the task is too large), write a handover note in the backlog file. This note is the next session's starting context — without it, the next session starts from scratch. The handover must capture:

- What has been done so far (which steps completed)
- What remains to be done (which steps are left)
- Key decisions made and why
- What was tried and didn't work
- The human's guidance and preferences from this session
- Concerns or risks identified

The most important thing to preserve is the *reasoning* — code changes are in the working tree, but the reasoning exists only in the conversation and must be written down.

## File References

- `.agent/task-tracking.md` — Task queue
- `.agent/backlog/*.md` — Task specifications
- `.agent/architecture.md` — Implementation guidance
- `.agent/vision.md` — Project goals
