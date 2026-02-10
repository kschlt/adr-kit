# Task Workflow — Design & Architecture

This document captures the *why* and *how* of the agent-driven task workflow used in this project. It covers how work is loaded, how sessions are bounded, how persistent state bridges the gap between stateless sessions, and how the workflow integrates with other workflows.

> **Implementation note**: This workflow is built around [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and its skills system (`.claude/skills/`). Throughout this document, Claude Code is referred to as *the agent*. The *principles* — structured task loading, bounded sessions, context passing — are adaptable to any AI-assisted development tool. The specific implementation uses Claude Code's skills, `$ARGUMENTS` passing, and `Skill()` invocations.

> **Status**: This workflow is being established as the standard going forward.

## The Problem

Agent sessions are stateless. Each new conversation starts with a blank context — the agent doesn't know what you were working on, what's done, what's next, or what decisions were made in previous sessions. Without structure, every session begins with the human re-explaining context, and the agent has no sense of priority or progress.

This creates three problems:

1. **No direction**: The agent doesn't know what to work on, in what order, or how to break a large goal into actionable steps. Without orchestration, the human becomes the project manager on every single session.
2. **No continuity**: Decisions made in session 1 (design choices, trade-offs, things tried and rejected) are lost by session 2. The agent may revisit rejected approaches or make contradictory choices.
3. **No accountability**: Without tracking what's done and what's left, work falls through the cracks. Completed work isn't documented properly because the agent doesn't know it's about to finish.

## The Solution

The task workflow solves this by owning the two boundaries of every session: a **clean start** and a **clean finish**, connected by persistent state that lives outside the agent's context window.

**Clean start** (`/next`): Load the right task from a prioritized queue, provide the relevant context, and confirm direction with the human — so the agent begins every session knowing exactly what to work on and why.

**Clean finish** (`/close`): Capture the session's accumulated knowledge, update the persistent state, and hand off to any integrated workflows — so nothing is lost and the next session can pick up seamlessly.

The [persistent state](#persistent-state--the-core-mechanism) (files in `.agent/`) is what makes both possible. It's the memory that bridges sessions.

What happens *before* the session (creating and prioritizing backlog tasks) and what happens *during* (the actual implementation) are not the task workflow's core concern. Currently, backlog files are written manually and `/next` includes basic task decomposition. Both are areas where additional tooling may be built. But the core value — ensuring every session starts clean and ends clean — is what the task workflow guarantees.

The task workflow operates independently. It can also [integrate](#integrations) with other workflows that benefit from structured task context. The [Git Workflow](./git-workflow.md) is the first such integration, receiving session context at commit time.

## Persistent State — The Core Mechanism

The agent's context window is ephemeral — it exists only during a session. Everything that needs to survive across sessions lives in `.agent/`:

```
.agent/
├── task-tracking.md      # Priority queue + done history
├── backlog/              # Task specifications (one file per task)
├── archive/              # Completed task specs (moved from backlog/)
├── architecture.md       # System-level design guidance
└── vision.md             # Project goals and direction
```

**`task-tracking.md`** is the priority queue. It contains a table of tasks ordered by priority, each with a status, a link to its backlog file, and a "Depends On" column. `/next` reads it to find the next unblocked task. `/close` updates it when work completes — marking tasks done and unblocking dependents. It also has a "Done" section serving as a chronological record of completed tasks.

**`backlog/*.md`** files are task specifications — one file per task. Each describes what needs to happen, why it matters, acceptance criteria, and any relevant context. These are typically written by the human, though the agent may create them when decomposing larger goals. A backlog file is the primary input to `/next` — it's what the agent reads to understand what to do and why.

**`archive/*.md`** is where completed backlog files go. `/close` moves them here on task completion. This preserves the specification and any notes added during implementation, so future sessions can reference past decisions.

**`architecture.md`** and **`vision.md`** are long-lived context files. They don't change per-task — they provide the broader design guidance and project direction that `/next` reads alongside the task spec. The agent uses these to make implementation decisions that align with the project's overall direction.

### The Task Lifecycle

A task flows through a defined lifecycle across sessions:

```
Human writes task spec
  → backlog/task-name.md (with requirements, acceptance criteria, context)
    → task-tracking.md (added to priority queue with dependencies)

/next picks up highest-priority unblocked task
  → reads backlog file, loads context, decomposes into steps
    → agent implements step by step

/close after each step
  → captures session knowledge, delegates to integrations (e.g. /commit)
  → on final step: moves backlog file to archive/, updates tracking, unblocks dependents
```

This lifecycle is the backbone of the workflow. Every session starts by reading the persistent state, every session ends by updating it. The files *are* the continuity.

### Handover Notes — Bridging Sessions

When a session ends before the task is fully complete (context window running low, or the task is too large for one session), the workflow must write a handover note. This goes into `task-tracking.md` or the backlog file and captures:

- What has been done so far
- What remains to be done
- Key decisions made and why
- What was tried and didn't work
- The human's guidance and preferences from this session
- Concerns or risks identified

This handover note is the next session's starting context. Without it, the next session starts from scratch and may redo work, make contradictory decisions, or miss context that only existed in the dying session's conversation. The most important thing to preserve is the *reasoning* — code changes are in the working tree, but the reasoning exists only in the conversation and must be written down.

## Design Principles

### One Task Per Session

Each session (= one chat with the agent) focuses on one task. This is deliberate:

- **Context window efficiency**: Agents work best when their context is focused. Loading multiple tasks creates noise and increases the chance of the agent mixing concerns.
- **Clear boundaries**: The session has a defined start (load task) and end (update tracking).
- **Fresh context**: Each task gets a new chat. Accumulated context from previous tasks creates noise and risks assumptions carrying over.

One task may involve several steps, each completed and handed off separately. The task workflow breaks a task into **atomic steps** — self-contained chunks that each deliver standalone value with implementation, tests, and documentation. This serves session safety (each step must fit the remaining context window) and, when a git integration is active, [git quality](./git-workflow.md#commit--one-task-atomic-unit-of-work) (each step maps to an atomic commit).

**Example**: The task "Add caching to KnowledgeLoader" might break into:
1. Step 1: Add LRU cache data structure with unit tests
2. Step 2: Integrate cache into KnowledgeLoader with integration tests
3. Step 3: Add cache invalidation and graceful degradation

Each step is self-contained. Together they form a coherent body of work for the task.

### Context Window Awareness

A session has a finite context window. The workflow plans for this at two points:

**During decomposition** (`/next` step 4): Steps are sized so each can be completed within the remaining context budget. If a task is too large for one session, `/next` plans only the steps that fit and notes remaining work for the next session.

**During implementation**: If the session approaches its context limit mid-step, the agent must not silently let the session end with unfinished work. Instead:

1. **Complete what's possible** — If the current step is in a good state, finalize it via `/close`.
2. **If mid-step, write a handover** — Capture the session's knowledge in a [handover note](#handover-notes--bridging-sessions) so the next session can continue seamlessly.

**The principle**: Never start an atomic step that can't be finished in the remaining context. If the session must end mid-work, the handover must be rich enough for the next session to continue as if it had been there all along.

## The Task Skills

Two skills manage the session boundaries:

| Skill | Boundary | Responsibility |
|-------|----------|---------------|
| `/next` | **Start** | Load task, provide context, confirm direction, set up the session |
| `/close` | **Finish** | Capture knowledge, update tracking, hand off to integrations |

### `/next` — Clean Start

1. **Check for uncommitted work** — If the working tree is dirty, address it first. Never start a new task with leftover changes.
2. **Load the next task** — Read `.agent/task-tracking.md`, find the highest-priority unblocked task (first row where "Depends On" = "—"). Read the linked backlog file for the full specification. Display the task summary and wait for confirmation before proceeding — the human may reprioritize or choose a different task. (Priorities change — a quick confirmation prevents wasting a session on the wrong task.)
3. **Delegate to integrations** — Hand off to any integrated workflows that need to act at session start. Currently: invoke `/branch` with the task title and thematic area. (See [Git Workflow integration](#git-workflow).)
4. **Research, plan, and decompose** — Read architectural context (`.agent/architecture.md`, `.agent/vision.md`, relevant source files). Break the task into atomic steps using TodoWrite — each step designed upfront as one concern with implementation + tests + docs, so the agent knows what each step contains and when to pause before moving on. Each step should be self-contained and [completable in the remaining context](#context-window-awareness). If the task is too large for one session, plan only the steps that fit and note remaining work in the backlog file.
5. **Implement step by step** — After each step is complete (implementation + tests passing), invoke `/close` to finalize with context. If more steps remain and context allows, continue. If context is running low, prioritize finalizing cleanly and writing a [handover note](#handover-notes--bridging-sessions) over rushing into the next step.

### `/close` — Clean Finish

`/close` has two jobs: (1) capture the session's knowledge before it's lost, and (2) maintain the persistent state so the next session can pick up cleanly.

It may be called **multiple times per session** — once per atomic step. On the final invocation, it also updates tracking and suggests next steps.

1. **Identify the task** — Match the current work to the task tracking entry.
2. **Distill context** — Review what happened during this step and construct a summary: what was the goal, what approach was taken and why, what alternatives were considered, what was tested, what risks remain. This doesn't need to be exhaustive — a few sentences covering the key points. But it must be *real*, derived from the actual session, not generic filler. Each step gets its *own* context — don't bundle reasoning from step 1 into step 3.

   **Example** — what a good summary looks like:
   ```
   "Added LRU caching to KnowledgeLoader because loading evaluation criteria
   from disk on every preflight call was adding ~200ms. Chose LRU over TTL
   because the data files are static within a session. Tested with empty cache,
   full cache, and cache invalidation on file change. Risk: cache is not
   invalidated if data files are edited mid-session, but this is acceptable
   since data files only change between releases."
   ```

3. **Delegate to integrations** — Hand off the distilled context to any integrated workflows that act at step completion. Currently: invoke `/commit` with the summary as `$ARGUMENTS`. (See [Git Workflow integration](#git-workflow).)
4. **If more steps remain** — Return to implementation.
5. **If final step** — Update the persistent state:
   - Move the backlog file to `archive/`
   - Remove the task from the priority queue
   - Add it to the "Done" section in `task-tracking.md`
   - Unblock any dependent tasks
6. **Suggest next step** — Based on the priority queue and current state, recommend what to do next. (When git integration is active, also consider branch state via `scripts/branch-context.sh` to suggest whether to continue on the branch or open a PR first.)

## Integrations

The task workflow operates standalone but is designed to integrate with other workflows that benefit from structured task context and session knowledge. Each integration hooks into the task lifecycle at defined points — typically at session start (`/next`) and step completion (`/close`) — receiving context that the integrated workflow cannot derive on its own.

The pattern is always the same: the task workflow captures knowledge during the session (the "why" — motivation, decisions, trade-offs) and hands it to the integrated workflow, which can only derive the "what" (diffs, outputs, artifacts) mechanically. This handover is what makes integrated workflows produce richer output than they could in isolation.

### Git Workflow

The [Git Workflow](./git-workflow.md) is the first integration. It handles branching, commits, and PRs as a standalone workflow with its own skills (`/branch`, `/commit`, `/pr`). The task workflow enhances it by providing the reasoning context that git operations cannot derive from diffs and logs alone.

**Hook: `/next` → `/branch`** — When `/next` loads a task (step 3), it invokes `/branch` with the task title and thematic area as `$ARGUMENTS`, so `/branch` can decide autonomously whether to create a new branch, continue on the current one, or escalate.

Good: `Skill(skill="branch", args="Add LRU caching to KnowledgeLoader — performance optimization in the knowledge module")`
Avoid: `Skill(skill="branch", args="CRA-007")` — a task ID tells `/branch` nothing about the theme.

**Hook: `/close` → `/commit`** — When `/close` finalizes a step (step 3), it invokes `/commit` with the distilled session context as `$ARGUMENTS`: the goal, approach and reasoning, alternatives considered, what was tested, and known risks. This is what makes commit messages explain *why*, not just *what*.

**Hook: `/close` → `/pr` (suggested)** — `/close` doesn't invoke `/pr` directly. On the final step, it reads the branch state and may suggest running `/pr` if the branch is ready for review.

For the full context contracts and tier system, see [Git Workflow — The Git Skills](./git-workflow.md#the-git-skills).

## See Also

- [Git Workflow](./git-workflow.md) — The standalone git workflow (branching, commits, PRs, quality gates)
- `.claude/skills/next/SKILL.md` — Operational details for `/next`
- `.claude/skills/close/SKILL.md` — Operational details for `/close`
