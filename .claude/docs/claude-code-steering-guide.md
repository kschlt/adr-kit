## 1) The mental model: 3 steering layers

Claude Code behavior is shaped by three complementary mechanisms:

1. **Instruction text** (persistent or conditional)
    

- `CLAUDE*.md` memory and `.claude/rules/*.md` rules become _system-level instruction text_ for the session.
    
    Claude Code Artifacts Guide
    

2. **Declarative policy/config**
    

- `settings.json` controls permissions, sandboxing, hooks wiring, plugins, model defaults, etc. This is the deterministic enforcement layer (block/allow/ask).
    
    Claude Code Repo Artifacts - Co…
    

3. **Executable policy / dynamic context**
    

- **Hooks** run scripts on events (before/after tools, session start, prompt submit, stop, etc.), can **block actions**, and can inject **additionalContext** dynamically.
    
    Claude Code Repo Artifacts - Co…
    

A practical takeaway: **Use instruction text for “how to do work”, settings for “what is allowed”, hooks for “guardrails + automation + dynamic context”.**

Claude Code Repo Artifacts - Co…

---

## 2) Lifecycle: from disk → “what the model sees”

On session start, Claude Code roughly does:

1. Merge settings by precedence (managed → CLI → local → project → user).
    
    Claude Code Repo Artifacts - Co…
    
2. Load memory & rules:
    
    - `CLAUDE*.md` from relevant scopes, plus `.claude/rules/*.md` and `~/.claude/rules/*.md` (path-scoped rules activate only when relevant files are in play).
        
        Claude Code Repo Artifacts - Co…
        
3. Discover subagents (`.claude/agents`, `~/.claude/agents`, plugins, CLI `--agents`).
    
    Claude Code Repo Artifacts - Co…
    
4. Discover Skills (initially **only name + description**, bodies lazy-loaded).
    
    Claude Code Repo Artifacts - Co…
    
5. Discover slash commands (`.claude/commands`, `~/.claude/commands`, plugin commands).
    
    Claude Code Repo Artifacts - Co…
    
6. Register hooks from settings + component frontmatter + plugins.
    
    Claude Code Repo Artifacts - Co…
    
7. Apply permissions & permission mode (IAM) rules (allow/ask/deny, sandboxing, etc.).
    
    Claude Code Repo Artifacts - Co…
    

For each model invocation, “context” is assembled from:

- Internal system prompt (not published / not editable)
    
    Claude Code Artifacts Guide
    
- Memory text + applicable rules
    
    Claude Code Artifacts Guide
    
- Any active Skill bodies or subagent prompts
    
    Claude Code Artifacts Guide
    
- Conversation history (possibly compacted)
    
    Claude Code Artifacts Guide
    
- Selected file contents and tool outputs, plus hook-injected `additionalContext`
    
    Claude Code Repo Artifacts - Co…
    

---

## 3) Memory & rules: always-on vs conditional instruction text

### 3.1 What counts as “memory”

Memory is plain Markdown instruction text that becomes system-level guidance:

**Scopes & typical locations** (conceptual precedence: org → project → local → user):

Claude Code Artifacts Guide

- Org/managed policies (if your org uses managed configuration).
    
- Project memory: `CLAUDE.md` committed to repo (often repo root; `.claude/CLAUDE.md` is also supported).
    
    Claude Code Artifacts Guide
    
- Project local memory: `CLAUDE.local.md` (gitignored; often root or `.claude/`).
    
    Claude Code Artifacts Guide
    
- User global memory: `~/.claude/CLAUDE.md` (applies to all projects).
    
    Claude Code Artifacts Guide
    

**Discovery behavior (important):**

- Starting from your current working directory, Claude Code searches upward for `CLAUDE.md` / `CLAUDE.local.md` up to repo root, and loads all it finds on that upward path.
    
    Claude Code Artifacts Guide
    
- It can also _detect_ deeper child-directory `CLAUDE.md` files but will **lazy-load** them only when you start working in those subtrees.
    
    Claude Code Artifacts Guide
    
    Claude Code Repo Artifacts - Co…
    

**Conflict handling:** there’s no formal override system beyond “the model reads text”; avoid contradictory instructions. More specific/project text tends to win in practice because of how it’s injected later in the composite prompt.

Claude Code Artifacts Guide

### 3.2 Rules files: `.claude/rules/*.md` (+ user rules)

Rules are also Markdown instructions, but can be **path-scoped**.

- Project rules: `.claude/rules/**/*.md` (recursive).
    
    Claude Code Artifacts Guide
    
- User rules: `~/.claude/rules/**/*.md` (recursive), loaded before project rules (so project can override/extend).
    
    Claude Code Artifacts Guide
    
- Rules are “same priority” as project memory; they’re mainly for organization + conditional scoping.
    
    Claude Code Artifacts Guide
    

**Frontmatter schema for rules (`paths` only):**

Claude Code Repo Artifacts - Co…

- `paths` is a list of glob patterns; rule applies only when Claude is working with matching files.
    
- Globs support `**`, `*`, and brace expansion:
    
    - `**/*.ts`, `src/**/*`, `src/**/*.{ts,tsx}`, `{src,lib}/**/*.ts`
        
        Claude Code Artifacts Guide
        
- No `paths` → rule is global/always applicable.
    
    Claude Code Artifacts Guide
    

**Optimization detail:** path-scoped rules may be excluded from immediate context until relevant (exact filtering not fully documented), which helps reduce context bloat.

Claude Code Artifacts Guide

### 3.3 `@` imports inside memory/rules (static include)

Inside `CLAUDE*.md` or rules you can include other files via `@path`. This is a _preprocessing include_ that inserts the referenced file content into memory context.

Claude Code Artifacts Guide

Key mechanics:

Claude Code Artifacts Guide

- Relative + absolute paths supported; can import from home (e.g. `@~/.claude/...`).
    
- Imports can be nested, but **max depth is 5** (prevents recursion).
    
- Imports inside inline code / code blocks are ignored (so `` `@file` `` won’t import).
    

**Practical guidance:** keep `CLAUDE.md` concise and import only what must be “always on”. Put large references in separate files and link/import strategically.

Claude Code Repo Artifacts - Co…

---

## 4) Settings (`settings.json`): deterministic control of tools, scope, safety

`settings.json` is the declarative configuration layer for:

- permissions / IAM defaults (allow/ask/deny, modes)
    
- sandboxing for Bash
    
- hooks
    
- environment variables for tool runs
    
- plugins / marketplaces
    
- model-ish defaults, status line, file suggestions, “thinking” toggles, etc.
    
    Claude Code Repo Artifacts - Co…
    

### 4.1 Locations & precedence

Canonical locations and precedence: **Managed > CLI args > Local > Project > User**.

Claude Code Repo Artifacts - Co…

- Managed: OS-specific paths (highest precedence; enterprise policy).
    
    Claude Code Repo Artifacts - Co…
    
- User: `~/.claude/settings.json`
    
    Claude Code Repo Artifacts - Co…
    
- Project: `.claude/settings.json`
    
    Claude Code Repo Artifacts - Co…
    
- Local project: `.claude/settings.local.json` (personal override, gitignored)
    
    Claude Code Repo Artifacts - Co…
    

### 4.2 Permissions structure: allow / ask / deny

Permissions rules decide what Claude can do without prompting, what always requires confirmation, and what is blocked:

- `allow`: auto-approved tool patterns (notably, **Bash patterns are prefix matches, not regex**).
    
    Claude Code Repo Artifacts - Co…
    
- `ask`: always require confirmation; **ask overrides allow** if both match.
    
    Claude Code Repo Artifacts - Co…
    
- `deny`: hard blocks; **deny wins over allow/ask**.
    
    Claude Code Repo Artifacts - Co…
    
- `additionalDirectories`: expands Claude’s accessible workspace beyond the working directory (useful in monorepos).
    
    Claude Code Repo Artifacts - Co…
    

**Security posture tip:** deny reads of `.env` and secret directories to prevent leaking sensitive data into model context.

Claude Code Repo Artifacts - Co…

### 4.3 Default permission modes (IAM)

`defaultMode` sets the baseline permission behavior:

Claude Code Repo Artifacts - Co…

- `default`: prompt on first use of each tool
    
- `acceptEdits`: auto-accept file edits/filesystem ops; still prompts for other tools
    
- `plan`: analyze-only; no modifications or command execution
    
    Claude Code Repo Artifacts - Co…
    
- `dontAsk`: auto-deny tools unless pre-approved (very restrictive)
    
    Claude Code Repo Artifacts - Co…
    
- `bypassPermissions`: no prompts; only safe in strong sandbox environments
    
    Claude Code Repo Artifacts - Co…
    

Managed settings can disable bypass mode (`disableBypassPermissionsMode`) and block the CLI flag for skipping permissions.

Claude Code Repo Artifacts - Co…

### 4.4 Sandboxing (Bash execution environment)

Settings can enforce Bash sandboxing, with options like `autoAllowBashIfSandboxed`, `excludedCommands`, and network constraints.

Claude Code Repo Artifacts - Co…

Important nuance: sandboxing controls **where** Bash runs, but filesystem/network restrictions still fundamentally depend on the permission system (`Read`, `Edit`, `WebFetch`, etc.).

Claude Code Repo Artifacts - Co…

### 4.5 Other notable settings keys that influence behavior/context

Commonly relevant keys include:

Claude Code Repo Artifacts - Co…

- `model` (default model)
    
- `statusLine` (can show context usage)
    
- `fileSuggestion` (customizes `@`-autocomplete discovery)
    
- `alwaysThinkingEnabled` / `MAX_THINKING_TOKENS`
    
- `enabledPlugins`, `extraKnownMarketplaces`, `strictKnownMarketplaces` (plugin sources + enablement)
    
    Claude Code Artifacts Guide
    
- `env` (env vars applied to Bash tool executions; handle secrets carefully)
    
    Claude Code Artifacts Guide
    
- `cleanupPeriodDays` (session cleanup)
    
    Claude Code Artifacts Guide
    
- `companyAnnouncements`, telemetry/metrics toggles (less direct steering)
    
    Claude Code Artifacts Guide
    

---

## 5) Hooks: executable guardrails + dynamic context injection

Hooks can:

- run commands before/after tools
    
- block tool executions
    
- mutate tool input
    
- inject additional context at key points
    
- shape stopping/resume behavior
    

They are a major “automation and policy” surface.

Claude Code Repo Artifacts - Co…

### 5.1 Where hooks can be defined

- In `settings.json` (`"hooks": { ... }`)
    
    Claude Code Artifacts Guide
    
- In Skill frontmatter (active only during Skill execution)
    
    Claude Code Artifacts Guide
    
- In subagent frontmatter (agent-scoped)
    
    Claude Code Repo Artifacts - Co…
    
- In command frontmatter (command-scoped)
    
    Claude Code Repo Artifacts - Co…
    
- In plugins (e.g., `hooks.json`)
    
    Claude Code Repo Artifacts - Co…
    

### 5.2 Blocking semantics & control via exit codes

Exit code behavior:

Claude Code Repo Artifacts - Co…

- `0`: success; stdout may be consumed (and for some events, JSON in stdout can control behavior)
    
- `2`: **blocking error** (action blocked; stderr becomes error message; stdout JSON ignored)
    
- other non-zero: non-blocking error (primarily for logs/debug)
    

### 5.3 JSON control protocol (stdout)

Hooks can emit structured JSON to influence Claude Code behavior:

Claude Code Repo Artifacts - Co…

  
Common fields include:

- `continue` (false stops further processing)
    
- `stopReason`
    
- `suppressOutput`
    
- `systemMessage`
    
- `hookSpecificOutput` (event-specific payload)
    

Event-specific examples:

Claude Code Repo Artifacts - Co…

- **PreToolUse**: set `permissionDecision` (`allow|deny|ask`), mutate `updatedInput`, inject `additionalContext`
    
- **PermissionRequest**: allow/deny + updatedInput + message; can interrupt
    
- **PostToolUse**: can block (decision) or inject context after completion
    
- **UserPromptSubmit**: block prompt or inject context
    
- **Stop / SubagentStop**: block stop + provide `reason` to guide continuation
    
- **SessionStart**: inject initial `additionalContext`
    

### 5.4 High-value hook patterns

- **Policy enforcement**: deny dangerous commands, enforce “no secrets”, prevent writes to protected paths.
    
    Claude Code Repo Artifacts - Co…
    
- **Quality automation**: auto-format/lint after edits, run unit tests after writes.
    
    Claude Code Artifacts Guide
    
- **Dynamic context**: inject `git diff`, open tickets, branch status at SessionStart or before tools.
    
    Claude Code Repo Artifacts - Co…
    
- **Compaction support**: run logic before compaction using a PreCompact hook.
    
    Claude Code Artifacts Guide
    

---

## 6) Skills: auto-discovered, reusable “capabilities” with progressive disclosure

Skills are best for **automatic** or “always available” expertise and workflows that should trigger from intent keywords.

### 6.1 Discovery → activation → execution

- At startup, only **name + description** for each Skill are loaded for discovery.
    
    Claude Code Repo Artifacts - Co…
    
- When a request matches, Claude proposes using the Skill (often requiring confirmation).
    
    Claude Code Artifacts Guide
    
- On activation, the full `SKILL.md` is loaded into context for that run, plus any on-demand linked files/scripts as needed.
    
    Claude Code Artifacts Guide
    

### 6.2 Progressive disclosure inside Skills

Skills can keep their core file lean and link out to supporting docs/scripts:

Claude Code Artifacts Guide

- Markdown links like `[Reference](reference.md)` are discovered; linked docs are typically loaded **on demand**.
    
- Default behavior is often “one hop” of link-following; keep critical content one link away.
    
- Scripts (e.g., `scripts/validate_form.py`) can be executed via Bash; only output enters context (saves tokens).
    
- Recommendation: keep `SKILL.md` under ~500 lines; move bulk into linked files.
    
    Claude Code Artifacts Guide
    

### 6.3 Skill schema (`SKILL.md` frontmatter)

Officially documented fields include:

Claude Code Repo Artifacts - Co…

- `name` (required; lowercase letters/numbers/hyphens; ≤64 chars)
    
- `description` (required; ≤1024 chars)
    
- `allowed-tools` (allowlist; tools usable without asking while Skill active)
    
- `model` (override model while active)
    
- `context: fork` (run Skill in separate subagent context)
    
    Claude Code Artifacts Guide
    
- `agent` (when forking, choose agent profile)
    
    Claude Code Artifacts Guide
    
- `hooks` (skill-scoped; PreToolUse/PostToolUse/Stop; supports `once: true`)
    
    Claude Code Artifacts Guide
    
- `user-invocable` (default true; if false, hides from slash menu but still eligible for auto-discovery)
    
    Claude Code Artifacts Guide
    
- `disable-model-invocation` (blocks programmatic invocation via Skill tool; auto-discovery may still exist depending on environment)
    
    Claude Code Repo Artifacts - Co…
    

**Visibility/control matrix (important):**

Claude Code Repo Artifacts - Co…

- default (`user-invocable: true`): visible in slash menu; Skill tool allowed; auto-discovery yes
    
- `user-invocable: false`: hidden; Skill tool allowed; auto-discovery yes
    
- `disable-model-invocation: true`: visible; Skill tool blocked; auto-discovery yes (unless further restricted)
    

### 6.4 Where Skills can be discovered (including monorepos)

- Skills exist in `.claude/skills/` (project), `~/.claude/skills/` (user), plugin packages, and can also be discovered from nested `.claude/skills/` directories in monorepos near the active file path.
    
    Claude Code Repo Artifacts - Co…
    

---

## 7) Slash commands: explicit prompt templates (+ pre-executed context)

Slash commands are best for “do this exact flow now” — one-shot or repeatable user-triggered procedures.

### 7.1 Locations & scope

- Project: `.claude/commands/*.md`
    
    Claude Code Repo Artifacts - Co…
    
- User: `~/.claude/commands/*.md`
    
    Claude Code Repo Artifacts - Co…
    
- Plugin commands: namespaced like `/pluginName:commandName`.
    
    Claude Code Artifacts Guide
    

Name collisions between user and project commands are not cleanly specified; avoid duplicates.

Claude Code Artifacts Guide

### 7.2 Command file schema (documented)

From the Agent SDK slash-commands doc, frontmatter fields include:

Claude Code Repo Artifacts - Co…

- `description` (recommended; used in help and for metadata exposure)
    
- `allowed-tools` (temporary allowlist while running the command)
    
- `model` (model override for this command)
    
- `argument-hint` (help text for args)
    
- `hooks` (command-scoped hooks; same schema; supports `once: true`)
    

### 7.3 Body syntax (power features)

Slash command bodies can include:

Claude Code Repo Artifacts - Co…

- **Bash pre-execution:** `!` + backticked shell command, e.g. `!`git diff``
    
    - Claude Code executes these _before_ prompting the model and inserts outputs into context.
        
- **File references:** `@path/to/file` to inject file contents into context for that command run.
    
    Claude Code Repo Artifacts - Co…
    
- **Arguments templating:** `$ARGUMENTS` or `$1`, `$2`, … substituted from `/command arg1 arg2`.
    
    Claude Code Artifacts Guide
    
    - If you don’t use placeholders, args are appended as `ARGUMENTS: ...` by default.
        
        Claude Code Artifacts Guide
        

### 7.4 Model-initiated invocation + metadata budget

- Commands (and Skills) are surfaced to the model via an internal “tool listing” mechanism; there’s a **~15k character budget** for names/descriptions/metadata. If exceeded, only a subset is included; `/context` warns.
    
    Claude Code Artifacts Guide
    
- You can adjust the budget via `SLASH_COMMAND_TOOL_CHAR_BUDGET`.
    
    Claude Code Artifacts Guide
    

### 7.5 Restricting whether the model can invoke commands

There are two relevant control planes:

1. **Deterministic enforcement via permissions**
    

- You can globally deny the Skill-like invocation mechanism by denying the `Skill` pseudo-tool in settings (prevents model-initiated invocation of commands/skills through that mechanism).
    
    Claude Code Artifacts Guide
    

2. **Per-command metadata suppression**
    

- Some environments support `disable-model-invocation: true` for commands (intended to keep it user-only by removing it from model-visible listings).
    
    Claude Code Artifacts Guide
    
- However, official SDK documentation does **not** list `disable-model-invocation` for commands (it _is_ a Skill field). Treat command support for this as **environment/version-dependent** and verify in your build.
    
    Claude Code Repo Artifacts - Co…
    

### 7.6 Forked execution for commands (verify in your build)

Some guides describe `context: fork` (and `agent`) for commands to run them in an isolated subagent context (like Skills).

Claude Code Artifacts Guide

  
Official slash-command docs emphasize the core schema above and do not clearly standardize `context/agent` for commands; treat this as **not guaranteed** unless you’ve confirmed your Claude Code version supports it.

Claude Code Repo Artifacts - Co…

---

## 8) Subagents: specialized Claude instances with separate context + constraints

Subagents are for compartmentalized work (exploration, reviews, risky tasks with stricter permissions, etc.).

### 8.1 Purpose & key properties

- Each subagent has its own system prompt, tool set, permission mode, optional preloaded Skills, and a **separate context window** with its own compaction lifecycle.
    
    Claude Code Repo Artifacts - Co…
    
- Subagents help keep the main conversation clean: only the result/summary returns to the main context, not the entire subagent transcript.
    
    Claude Code Artifacts Guide
    
- Subagents cannot spawn other subagents (no nesting).
    
    Claude Code Artifacts Guide
    

### 8.2 Locations & discovery precedence

Precedence: CLI-defined > project > user > plugin.

Claude Code Repo Artifacts - Co…

- `.claude/agents/*.md` (project)
    
    Claude Code Artifacts Guide
    
- `~/.claude/agents/*.md` (user)
    
    Claude Code Artifacts Guide
    
- CLI `--agents '{...}'` (session only)
    
    Claude Code Repo Artifacts - Co…
    
- Plugins can package agents.
    
    Claude Code Repo Artifacts - Co…
    

Agents are listed via `/agents`; edits may require restart or reload.

Claude Code Repo Artifacts - Co…

### 8.3 Subagent file schema (YAML frontmatter)

Required: `name`, `description`.

Claude Code Artifacts Guide

  
Common fields:

Claude Code Repo Artifacts - Co…

- `tools` (allowlist; if omitted, inherits all tools from main)
    
- `disallowedTools` (denylist applied atop inherited/specified tools)
    
- `model` (`sonnet`, `opus`, `haiku`, `inherit`)
    
- `permissionMode` (`default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, `plan`)
    
- `skills` (Skills to inject into subagent at startup; subagents don’t inherit Skills by default)
    
- `hooks` (agent-scoped hooks; supports PreToolUse/PostToolUse/Stop)
    

The markdown body after frontmatter is the subagent’s system prompt; internal main prompt isn’t shared to subagents.

Claude Code Repo Artifacts - Co…

### 8.4 Context management, compaction, resuming

- Subagents compact independently from the main conversation; compaction events are logged in transcripts.
    
    Claude Code Artifacts Guide
    
- You can resume a prior subagent run; Claude Code tracks agent IDs and stores logs under something like `~/.claude/projects/{project}/{sessionId}/subagents/agent-<ID>.jsonl`.
    
    Claude Code Artifacts Guide
    
- Subagent state can persist across session restarts if you reopen the same session; old sessions may be cleaned after a retention period (e.g., controlled by `cleanupPeriodDays`).
    
    Claude Code Artifacts Guide
    

---

## 9) File referencing: three different mechanisms (don’t mix them up)

### 9.1 `@` in memory/rules = static include (preprocessing)

- Happens when memory file is loaded; literally inserts file text into memory context at that point. Not “dynamic per prompt”.
    
    Claude Code Artifacts Guide
    
- Depth limit 5; ignores code blocks/inline code.
    
    Claude Code Artifacts Guide
    

### 9.2 `@` in prompts/commands = on-demand file injection

- Typing `@` in Claude Code input triggers a file picker; selecting inserts a reference that causes Claude to read file contents into context.
    
    Claude Code Repo Artifacts - Co…
    
- In commands, `@file` can be included directly in the body to pull file contents into that command run’s context.
    
    Claude Code Repo Artifacts - Co…
    

### 9.3 Skill links = progressive disclosure

- Markdown links in `SKILL.md` advertise supporting files; Claude loads them only if needed. One-hop default is common.
    
    Claude Code Artifacts Guide
    

### 9.4 `!` backticks in commands = pre-executed Bash → output to context

- The command body can run shell snippets `!`like this``; outputs become part of the prompt context.
    
    Claude Code Repo Artifacts - Co…
    

---

## 10) Context limits, compaction, and budgets

Claude models have finite context windows; Claude Code manages this via lazy-loading and compaction.

Claude Code Artifacts Guide

Key behaviors:

Claude Code Artifacts Guide

- **Auto-compaction** summarizes older history when usage crosses a threshold; logged in transcripts.
    
- `/compact` can be user-invoked (optionally with instructions about what to preserve).
    
- A **PreCompact hook** exists for “do something before compaction.”
    
- Skill bodies load only when activated; subagent work stays isolated.
    
    Claude Code Artifacts Guide
    

**Metadata budget for commands/skills list:** ~15k characters (names/descriptions); can be tuned via `SLASH_COMMAND_TOOL_CHAR_BUDGET`.

Claude Code Artifacts Guide

**Tool-search heuristic (behavioral nuance):**

- There is an internal “tool search” tendency that may proactively fetch project files when context usage is low (e.g., <10% usage), but will be more conservative as context fills.
    
    Claude Code Artifacts Guide
    

---

## 11) Plugins & MCP: extending tool surface (and therefore context)

### 11.1 Plugins

- Plugins can bring their own Skills, agents, commands, and hooks; plugin commands are namespaced (e.g. `/pluginName:commandName`).
    
    Claude Code Artifacts Guide
    
- Plugin enablement and marketplaces are controlled via settings keys like `enabledPlugins`, `extraKnownMarketplaces`, `strictKnownMarketplaces`.
    
    Claude Code Repo Artifacts - Co…
    

### 11.2 MCP (Model Context Protocol)

- MCP servers add external tools (doc stores, databases, APIs), expanding what Claude can do and what content can be pulled into context.
    
    Claude Code Repo Artifacts - Co…
    
- MCP state/preferences and project MCP servers are associated with `~/.claude.json` and `.mcp.json`.
    
    Claude Code Repo Artifacts - Co…
    
- MCP tools can pull in large content when invoked; some MCP-generated slash commands are dynamically discovered (and may not persist unless reconnected, depending on setup).
    
    Claude Code Artifacts Guide
    

---

## 12) Recommended repo layout (high-signal, scalable, low-bloat)

A strong baseline pattern:

`your-repo/   CLAUDE.md                 # short, high-signal project guidance   CLAUDE.local.md           # personal overrides (gitignored)   .claude/     settings.json           # shared project policy + hooks wiring     settings.local.json     # personal override (gitignored)     rules/       testing.md            # always-on testing rules       backend.md            # path-scoped backend rules       security.md           # safe-by-default rules     commands/       review.md             # git-diff driven review flow       commit.md             # conventional commit helper     skills/       explaining-code/         SKILL.md         reference.md        # large doc, linked from SKILL.md         scripts/            # heavy logic run via Bash     agents/       safe-researcher.md    # read-only exploration agent       code-reviewer.md     hooks/       check-style.sh       validate-command.sh`

Why this works:

- `CLAUDE.md` stays lean; large docs are imported/linked only when needed.
    
    Claude Code Repo Artifacts - Co…
    
- Rules allow language/subsystem-specific guidance without polluting all sessions.
    
    Claude Code Artifacts Guide
    
- Settings enforce safety and prevent instruction drift.
    
    Claude Code Artifacts Guide
    
- Hooks make policies executable and consistent.
    
    Claude Code Repo Artifacts - Co…
    
- Skills provide reusable auto-capabilities; commands provide explicit repeatable flows.
    
    Claude Code Artifacts Guide
    

---

## 13) Practical steering recipes (copy/paste patterns)

### A) “Safe-by-default, productive” permissions

- Deny `.env` and secrets paths, allow common read/search tools, make Bash sandboxed.
    
    Claude Code Repo Artifacts - Co…
    
    Claude Code Repo Artifacts - Co…
    

### B) Auto-quality gates

- PostToolUse hook on `Edit`/`Write` runs formatter/linter; exit code 2 blocks if violations.
    
    Claude Code Artifacts Guide
    
    Claude Code Repo Artifacts - Co…
    

### C) Git-diff review command

- Slash command body pre-runs `git diff` via `!` backticks and feeds output to a structured review rubric.
    
    Claude Code Repo Artifacts - Co…
    

### D) Keep heavy analysis out of main context

- Use subagents for log spelunking, repo-wide scanning; main chat receives only result summary.
    
    Claude Code Artifacts Guide
    

### E) Skills for “always follow our standards”

- Put evergreen standards (review checklist, architecture heuristics) into Skills or rules, not into ad-hoc prompts.
    
    Claude Code Artifacts Guide
    
    Claude Code Artifacts Guide
    

---

## 14) Known “gray areas” you should treat as version-dependent

These are important because they affect how you design your steering stack:

- **Slash command frontmatter beyond the SDK schema** (notably `disable-model-invocation`, `context`, `agent`) may exist in some environments and guides, but is not consistently specified as part of the official slash-commands frontmatter spec. The safest, most portable approach is to enforce behavior via **permissions** (deny Skill pseudo-tool / restrict tool access) and use hooks.
    
    Claude Code Repo Artifacts - Co…
    
    Claude Code Artifacts Guide
    
    Claude Code Artifacts Guide