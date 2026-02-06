# ADR‑Kit — Vision & Architectural Blueprint
_Last updated: 2025-09-05 10:41:12Z_

This document captures the **vision**, **why it matters**, and a **high‑level architecture** for ADR‑Kit. It is intentionally **implementation‑agnostic**: it describes behaviors, contracts, and workflows rather than folder layouts or specific technologies. Use it to align design discussions, evaluate current implementations, and plan evolutions.

---

## 1) Purpose & Outcomes
**Goal:** Keep the human architect in control while agents implement code.  
**Outcomes we want:**
- Decisions are **explicit** (ADR), **approved by a human**, and **discoverable** by agents.
- Agents **follow** accepted decisions, **pause** to propose new ones when needed, and **never drift** silently.
- Enforcement is **deterministic** (policy + checks) and visible in **automation** (CI).
- Guidance to agents is **contextual and minimal** (tool‑local promptlets), not via giant system prompts.

**Primary users:** human architects/maintainers, IDE‑embedded agents, CI pipelines.  

---

## 2) Capabilities (what the system must do)
- **ADR Management:** Create, view, update, relate, and change the lifecycle state of ADRs (draft → proposed → accepted → deprecated/superseded).
- **Constraints Contract:** Produce a compact, machine‑readable summary of all **accepted** rules (“the contract”) for agents to obey.
- **Policy Gate for New Choices:** Deterministic gating for major technical choices (e.g., runtime deps, frameworks). Default: **require ADR** before proceeding.
- **Planning Context:** Provide agents a small planning packet: hard constraints + most relevant decisions for the current task.
- **Guardrails:** Generate/maintain configuration fragments (lint, dependency rules, CI checks) that reflect accepted decisions; validate the repo for violations.
- **Guided Interactions:** Return short, imperative guidance (“promptlets”) with tool responses to steer agents at the moment of action.
- **Lifecycle Hooks:** When a decision’s status changes, automatically update the contract and guardrails accordingly.
- **Observability & Audit:** Record key events (proposals, acceptances, violations, guardrail changes) to enable review and learning.

---

## 3) Architectural Tenets
- **Human‑first + Machine‑first:** ADRs remain human‑legible; their enforcement rules are machine‑readable.
- **Deterministic & Idempotent:** Same inputs → same outputs; merges and validations are rule‑based, not heuristic.
- **Local, Contextual Steering:** Guidance is attached to tool responses that need it; keep prompts small and specific.
- **Minimal Token Footprint:** Share IDs, summaries, and contracts, not full documents, unless specifically requested.
- **Composable & Extensible:** New languages/policies integrate via adapters; storage/retrieval strategies are pluggable.
- **Fail Loud & Early:** Clear error codes and “next steps” for agents; CI fails fast on violations.

---

## 4) High‑Level Architecture (conceptual components)
- **ADR Store:** Human‑legible decision records with lifecycle fields and links (supersedes/superseded‑by/relates‑to).
- **Constraints Builder:** Merges enforcement rules from all **accepted** decisions into a single, small **contract** object. Detects and blocks conflicts.
- **Policy Engine:** Deterministic gate for new or changed technical choices. Supports default “require ADR”, allow/deny lists, categories, and simple keyword/alias maps.
- **Planning Context Service:** Produces a **planning packet**: the contract + a shortlist of relevant ADRs (via simple filtering and lexical ranking).
- **Guardrail Manager:** Calculates and applies **configuration fragments** (e.g., lint/import/dep rules, CI checks). Writes only inside clearly marked, tool‑owned blocks.
- **Validator:** Scans manifests, imports, and configs to detect violations; emits precise findings and suggested remedies.
- **MCP Interface:** Exposes these capabilities as tools with a **uniform response envelope** that can include short, imperative guidance for the agent.

> Each component can be implemented with technologies that fit your stack; the design does not prescribe specific storage formats or folder structures.

---

## 5) Key Contracts & Data (format‑agnostic)
- **ADR Record:** id, title, status, tags/scope, effective date, links (supersedes/superseded‑by/relates‑to), rationale sections, short “why” summary, and **optional** machine rules.
- **Constraints Contract:** a compact object derived from all accepted ADRs that agents can obey without reading ADR prose (e.g., allow/deny lists, banned imports, required checks). Includes provenance (which decisions contributed) and a change hash for caching.
- **Policy Definition:** default posture (e.g., require ADR for runtime deps), category hints for “major choices”, allow/deny lists, alias mapping for names.
- **Planning Packet:** hard constraints + shortlist of relevant ADRs for a task + small guidance for how to incorporate them.
- **Response Envelope:** ok/code/data + optional guidance for the agent (priority, next step), provenance, and optional token hints.
- **Error Taxonomy:** stable codes (e.g., NEW_DEP_REQUIRES_ADR, ADR_CONFLICT, VALIDATION_FAILED) with actionable next steps.

---

## 6) Core Workflows (behavioral view)
### 6.1 Cold Start
- Establish default policy (e.g., “require ADR” for new runtime dependencies or frameworks).
- Create a small set of baseline decisions if desired (language/runtime, dependency governance).

### 6.2 Planning a Feature
- Agent requests the **planning packet**.
- Packet returns the contract + a few relevant decisions.
- Agent cites decision IDs in its plan and proceeds in line with the contract.

### 6.3 Introducing a New Major Choice
- Before adding a runtime dependency or framework‑level item, the policy engine evaluates the action.
- Outcomes: **Allowed**, **Requires ADR**, or **Blocked/Conflicts**.
- On **Requires ADR**, the agent drafts a proposal and asks the human to approve; once accepted, the system updates the contract and guardrails.

### 6.4 Superseding a Decision
- Agent or human proposes a new decision that supersedes an existing one.
- On acceptance, the system updates links, refreshes the contract, and adjusts guardrails accordingly.

### 6.5 Validation & Automation
- Validator checks for violations in manifests/imports/configs.
- CI integrates the validator to gate changes; the contract’s hash helps detect drift.

---

## 7) Guidance & Promptlets
- Tool responses can include a **small, imperative instruction** to the agent (“explain conflict; ask for approval to draft ADR; do not proceed until resolved”). 
- Promptlets are reusable snippets referenced by ID; the system ensures they do not contradict accepted decisions. On contradiction, return a specific error and stop.

---

## 8) Extensibility
- **Language/Framework Adapters:** Pluggable modules for different ecosystems to interpret and enforce decisions (e.g., dependency/import checks, lint rules, CI glue).
- **Retrieval Strategy:** Start with simple filtering + lexical ranking for relevant ADRs; add semantics only when the decision set grows large.
- **Storage:** ADRs and contracts can live wherever is convenient (files, DB, etc.); the behavior is the same.
- **Interfaces:** MCP or other interfaces can expose the same capabilities; response envelopes remain consistent.

---

## 9) Success Criteria & Non‑Goals
**Success:** 
- Agents cite decisions in plans, pause for approval on major new choices, and follow the contract.
- Minimal drift: violations are caught early; automation blocks unsafe changes.
- Human effort is focused on **approving decisions**, not policing implementation details.

**Non‑Goals (for v1):** background daemons by default, heavy semantic retrieval, auto‑refactors beyond owned config fragments, deep static analysis across all languages.

---

## 10) Open Design Questions (to drive discussion)
- Decision **granularity**: which choices always need ADRs vs. can be policy‑allowed?
- **Taxonomy** for tags/scope to make retrieval predictable.
- **Authority model**: who approves/supersedes decisions?
- **CI strictness**: hard‑fail vs. warn for specific categories.
- **Observability**: which events are logged, and where?
- **Adapter roadmap**: which ecosystems to prioritize next?

---

## 11) Minimal MVP (implementation‑agnostic)
- ADR management with lifecycle, short summaries, and links.
- Deterministic constraints contract built from **accepted** decisions.
- Policy gate that defaults to **require ADR** for major choices.
- Planning packet with small, relevant context for agents.
- Guardrail generation/validation with clearly marked, tool‑owned fragments.
- CI integration to block violations.
- Uniform response envelopes with optional promptlets and clear error codes.
