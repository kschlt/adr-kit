"""Data models for the Planning Context Service."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..core.model import ADRStatus

# ---------------------------------------------------------------------------
# Scenario taxonomy (SCN)
# ---------------------------------------------------------------------------


class ContextScenario(str, Enum):
    """Supported context retrieval scenarios for v1."""

    STRATEGIC_PLANNING = "strategic_planning"
    """Feature planning, spec writing, architectural exploration."""

    FOCUSED_IMPLEMENTATION = "focused_implementation"
    """Coding in a specific area or bounded task."""

    PRE_DECISION = "pre_decision"
    """Before committing to a direction — evaluate whether a new ADR is needed."""

    SUPERSESSION_IMPACT = "supersession_impact"
    """When an existing decision may change — assess downstream implications."""


class ChangeMode(str, Enum):
    """How the caller intends to change the codebase."""

    NONE = "none"
    """Reading or exploring — no changes planned."""

    ADDITIVE = "additive"
    """Adding new code or features without changing existing behaviour."""

    MODIFYING = "modifying"
    """Changing existing code or behaviour."""

    REPLACING = "replacing"
    """Superseding or replacing a decision or component."""


class DetailLevel(str, Enum):
    """How much detail to include in the response packet."""

    MINIMAL = "minimal"
    """Constraints only, no explanations."""

    STANDARD = "standard"
    """Constraints with brief rationale (default)."""

    DETAILED = "detailed"
    """Full context including history and tradeoffs."""


class ScopeHint(BaseModel):
    """Typed scope signal so the kit doesn't have to guess what a string means."""

    hint_type: str = Field(
        ...,
        description=("Signal type: 'file_path', 'module', 'domain', 'stack', or 'tag'"),
    )
    value: str = Field(
        ...,
        description="The signal value, e.g. 'src/auth/', 'authentication', 'backend'",
    )


class TargetRef(BaseModel):
    """Typed reference to a known ADR or clause the caller wants included."""

    ref_type: str = Field(
        ...,
        description="Reference type: 'adr_id' or 'clause_id'",
    )
    ref_id: str = Field(
        ...,
        description="The identifier, e.g. 'ADR-003' or a clause UUID",
    )


class ContextRequest(BaseModel):
    """Structured request contract for adr_planning_context callers."""

    scenario: ContextScenario = Field(
        ContextScenario.STRATEGIC_PLANNING,
        description="Which scenario this request falls under",
    )
    task_summary: str = Field(
        ...,
        description="What the caller is trying to accomplish",
    )
    scope_hints: list[ScopeHint] = Field(
        default_factory=list,
        description="Typed scope signals (file paths, domains, stack tags, etc.)",
    )
    change_mode: ChangeMode = Field(
        ChangeMode.NONE,
        description="How the caller intends to modify the codebase",
    )
    focus: str = Field(
        "",
        description="Specific area of concern (free text, feeds semantic retrieval)",
    )
    known_targets: list[TargetRef] = Field(
        default_factory=list,
        description="Typed references to ADRs or clauses to include unconditionally",
    )
    detail_level: DetailLevel = Field(
        DetailLevel.STANDARD,
        description="How much detail to include in the response",
    )


# ---------------------------------------------------------------------------
# Response-side models (SCN)
# ---------------------------------------------------------------------------


class ConstraintSummary(BaseModel):
    """A single enforced constraint derived from an approved ADR."""

    clause_id: str | None = Field(
        None,
        description="Clause identifier (None until clause IDs land in a future item)",
    )
    source_adr: str = Field(..., description="ADR that produced this constraint")
    summary: str = Field(..., description="One-line constraint description")
    relevance_score: float = Field(
        ...,
        description="How relevant this constraint is to the request (0.0-1.0)",
    )
    domain: str | None = Field(
        None,
        description="Architectural domain this constraint belongs to",
    )


class InspectReference(BaseModel):
    """A reference returned so callers can inspect further detail on demand."""

    ref_type: str = Field(
        ...,
        description="Reference type: 'adr', 'clause', or 'resource'",
    )
    ref_id: str = Field(
        ...,
        description="Identifier: ADR-003, clause UUID, or resource URI",
    )
    label: str = Field(..., description="Human-readable label for display")


class PacketMetadata(BaseModel):
    """Metadata describing how a ScenarioContextPacket was assembled."""

    token_estimate: int = Field(
        ...,
        description="Rough token count for the full packet",
    )
    candidate_count: int = Field(
        ...,
        description="Number of candidates evaluated before ranking",
    )
    ranking_strategy: str = Field(
        "",
        description="Strategy used to rank candidates (e.g. 'semantic', 'exact')",
    )


class ScenarioContextPacket(BaseModel):
    """Scenario-aware response packet (v2).

    Coexists with the legacy ContextPacket.  New tool paths return this shape;
    the legacy ContextPacket remains in place for existing callers.
    """

    scenario: ContextScenario = Field(
        ...,
        description="Scenario this packet was assembled for",
    )
    overview: str = Field(
        ...,
        description="1-3 sentence architectural orientation for the scenario",
    )
    constraints: list[ConstraintSummary] = Field(
        default_factory=list,
        description="Relevant constraints, ranked by relevance",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="AI warnings and tradeoff notes",
    )
    inspect_deeper: list[InspectReference] = Field(
        default_factory=list,
        description="References to ADRs, clauses, or resources for further inspection",
    )
    metadata: PacketMetadata | None = Field(
        None,
        description="Assembly metadata (token estimate, candidate count, etc.)",
    )


class TaskHint(BaseModel):
    """Hints about the task that help determine relevant context."""

    task_description: str = Field(
        ..., description="Description of what the agent is trying to accomplish"
    )
    changed_files: list[str] | None = Field(None, description="Files being modified")
    technologies_mentioned: list[str] | None = Field(
        None, description="Technologies mentioned in the task"
    )
    task_type: str | None = Field(
        None, description="Type of task: feature, bugfix, refactor, etc."
    )
    priority: str | None = Field(
        "medium", description="Task priority: low, medium, high, critical"
    )


class ContextualADR(BaseModel):
    """A lightweight ADR representation for context packets."""

    id: str = Field(..., description="ADR identifier")
    title: str = Field(..., description="Human-readable title")
    status: ADRStatus = Field(..., description="Current status")
    summary: str | None = Field(None, description="Brief summary of the decision")
    relevance_score: float = Field(
        ..., description="Relevance score for this task (0.0-1.0)"
    )
    relevance_reason: str = Field(..., description="Why this ADR is relevant")
    key_constraints: list[str] = Field(
        default_factory=list, description="Key constraints from this ADR"
    )
    related_technologies: list[str] = Field(
        default_factory=list, description="Technologies mentioned in this ADR"
    )
    ai_warnings: list[str] = Field(
        default_factory=list,
        description="AI-centric warnings extracted from ADR consequences",
    )
    resource_uri: str | None = Field(
        None,
        description="MCP resource URI for fetching full ADR content on demand (e.g. adr://ADR-0001)",
    )


class PlanningGuidance(BaseModel):
    """Contextual guidance for agents based on the current task and constraints."""

    guidance_type: str = Field(
        ..., description="Type of guidance: constraint, recommendation, warning, etc."
    )
    priority: str = Field(
        ..., description="Priority level: low, medium, high, critical"
    )
    message: str = Field(..., description="The guidance message")
    source_adrs: list[str] = Field(
        default_factory=list, description="ADRs that contributed to this guidance"
    )
    actionable: bool = Field(
        True, description="Whether this guidance requires specific action"
    )


class ContextPacket(BaseModel):
    """Complete context packet delivered to agents for planning tasks.

    This is the key output of the Planning Context Service - a curated,
    token-efficient package of exactly what the agent needs.
    """

    # Task information
    task_description: str = Field(
        ..., description="What the agent is trying to accomplish"
    )
    task_type: str | None = Field(None, description="Categorized task type")

    # Hard constraints (from contract)
    hard_constraints: dict[str, Any] = Field(
        ..., description="Non-negotiable constraints from contract"
    )
    contract_hash: str = Field(..., description="Hash of the constraints contract used")

    # Relevant ADRs (curated shortlist)
    relevant_adrs: list[ContextualADR] = Field(
        ..., description="Most relevant ADRs for this task"
    )

    # Contextual guidance
    guidance: list[PlanningGuidance] = Field(
        default_factory=list, description="Specific guidance for this task"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this packet was generated",
    )
    token_estimate: int = Field(
        ..., description="Estimated token count for this packet"
    )
    adr_directory: str = Field(..., description="Source ADR directory")

    # Summary
    summary: str = Field(..., description="Brief summary of key architectural guidance")

    def to_agent_prompt(self) -> str:
        """Convert context packet to a concise prompt for agents."""
        lines = []

        # Task context
        lines.append(f"## Architectural Context for: {self.task_description}")

        # Hard constraints (most important)
        if self.hard_constraints:
            lines.append("\n### Hard Constraints (Must Follow)")

            # Import constraints
            if self.hard_constraints.get("imports"):
                imports = self.hard_constraints["imports"]
                if imports.get("disallow"):
                    lines.append(
                        f"❌ Disallowed imports: {', '.join(imports['disallow'])}"
                    )
                if imports.get("prefer"):
                    lines.append(
                        f"✅ Preferred imports: {', '.join(imports['prefer'])}"
                    )

            # Boundary constraints
            if self.hard_constraints.get("boundaries", {}).get("rules"):
                lines.append("🏗️ Architectural boundaries:")
                for rule in self.hard_constraints["boundaries"]["rules"][
                    :3
                ]:  # Limit to top 3
                    lines.append(f"  • {rule.get('forbid', 'Boundary rule')}")

        # Relevant decisions (curated shortlist)
        if self.relevant_adrs:
            lines.append(
                f"\n### Relevant Decisions ({len(self.relevant_adrs)} most important)"
            )
            for adr in self.relevant_adrs[:5]:  # Limit to top 5
                lines.append(f"• **{adr.id}**: {adr.title}")
                if adr.summary:
                    lines.append(f"  {adr.summary}")
                if adr.key_constraints:
                    lines.append(f"  Constraints: {', '.join(adr.key_constraints[:3])}")

        # Contextual guidance (prioritized)
        high_priority_guidance = [
            g for g in self.guidance if g.priority in ["high", "critical"]
        ]
        if high_priority_guidance:
            lines.append("\n### Key Guidance")
            for guidance in high_priority_guidance[:3]:  # Limit to top 3
                priority_emoji = "🚨" if guidance.priority == "critical" else "⚠️"
                lines.append(f"{priority_emoji} {guidance.message}")

        # Summary
        lines.append("\n### Summary")
        lines.append(self.summary)

        return "\n".join(lines)

    def get_cited_adrs(self) -> list[str]:
        """Get list of all ADR IDs referenced in this context packet."""
        adr_ids = [adr.id for adr in self.relevant_adrs]

        # Add ADRs from guidance
        for guidance in self.guidance:
            adr_ids.extend(guidance.source_adrs)

        return list(set(adr_ids))  # Remove duplicates

    def estimate_token_count(self) -> int:
        """Estimate token count for this context packet."""
        # Simple heuristic: ~4 characters per token
        prompt_text = self.to_agent_prompt()
        return len(prompt_text) // 4

    def update_token_estimate(self) -> None:
        """Update the token estimate based on current content."""
        self.token_estimate = self.estimate_token_count()


class RelevanceScore(BaseModel):
    """Score indicating how relevant an ADR is to a specific task."""

    adr_id: str = Field(..., description="ADR identifier")
    score: float = Field(..., description="Relevance score (0.0-1.0)")
    reasons: list[str] = Field(
        default_factory=list, description="Reasons for this relevance score"
    )
    factors: dict[str, float] = Field(
        default_factory=dict, description="Individual scoring factors"
    )

    @property
    def is_highly_relevant(self) -> bool:
        """Whether this ADR is highly relevant (score >= 0.7)."""
        return self.score >= 0.7

    @property
    def is_moderately_relevant(self) -> bool:
        """Whether this ADR is moderately relevant (0.4 <= score < 0.7)."""
        return 0.4 <= self.score < 0.7

    @property
    def relevance_category(self) -> str:
        """Categorize relevance level."""
        if self.score >= 0.8:
            return "critical"
        elif self.score >= 0.6:
            return "high"
        elif self.score >= 0.4:
            return "medium"
        elif self.score >= 0.2:
            return "low"
        else:
            return "minimal"
