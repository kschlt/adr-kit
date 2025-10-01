"""Data models for the Planning Context Service."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..core.model import ADRStatus


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
