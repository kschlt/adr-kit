"""Contextual guidance generator for planning context packets."""

from enum import Enum

from ..contract.models import ConstraintsContract
from .analyzer import TaskContext
from .models import ContextualADR, PlanningGuidance, RelevanceScore


class GuidanceType(str, Enum):
    """Types of guidance that can be provided to agents."""

    CONSTRAINT = "constraint"  # Hard constraints that must be followed
    RECOMMENDATION = "recommendation"  # Suggested approaches or libraries
    WARNING = "warning"  # Things to be careful about
    PATTERN = "pattern"  # Architectural patterns to follow
    PREFLIGHT = "preflight"  # Remind about preflight checks
    APPROVAL = "approval"  # Things that need approval
    REFERENCE = "reference"  # Reference to specific ADRs for details


class ContextualPromptlet:
    """A small, contextual piece of guidance for agents."""

    def __init__(
        self, message: str, guidance_type: GuidanceType, priority: str = "medium"
    ):
        self.message = message
        self.guidance_type = guidance_type
        self.priority = priority

    def to_guidance(self, source_adrs: list[str] | None = None) -> PlanningGuidance:
        """Convert to a PlanningGuidance object."""
        return PlanningGuidance(
            guidance_type=self.guidance_type.value,
            priority=self.priority,
            message=self.message,
            source_adrs=source_adrs or [],
            actionable=True,
        )


class GuidanceGenerator:
    """Generates contextual guidance for planning context packets."""

    def __init__(self) -> None:
        # Standard promptlet templates
        self.promptlets = {
            "preflight_check": ContextualPromptlet(
                "Use adr_preflight() to check any new dependencies or frameworks before implementing",
                GuidanceType.PREFLIGHT,
                "high",
            ),
            "cite_adrs": ContextualPromptlet(
                "Reference relevant ADR IDs in your implementation plan and code comments",
                GuidanceType.PATTERN,
                "medium",
            ),
            "follow_constraints": ContextualPromptlet(
                "Follow the hard constraints listed above - these are non-negotiable",
                GuidanceType.CONSTRAINT,
                "critical",
            ),
            "get_approval": ContextualPromptlet(
                "Get human approval via ADR before making architectural decisions",
                GuidanceType.APPROVAL,
                "high",
            ),
        }

    def generate_guidance(
        self,
        task_context: TaskContext,
        constraints_contract: ConstraintsContract | None,
        relevant_adrs: list[ContextualADR],
        relevance_scores: list[RelevanceScore],
    ) -> list[PlanningGuidance]:
        """Generate contextual guidance based on task and architectural context."""

        guidance = []

        # 1. Always include preflight check for certain task types
        if task_context.task_type.value in [
            "dependency",
            "feature",
            "refactor",
            "integration",
        ]:
            guidance.append(self.promptlets["preflight_check"].to_guidance())

        # 2. Hard constraints guidance
        if constraints_contract and not constraints_contract.constraints.is_empty():
            guidance.append(self.promptlets["follow_constraints"].to_guidance())

            # Specific constraint guidance
            constraint_guidance = self._generate_constraint_guidance(
                constraints_contract, task_context
            )
            guidance.extend(constraint_guidance)

        # 3. ADR-specific guidance
        adr_guidance = self._generate_adr_guidance(
            relevant_adrs, relevance_scores, task_context
        )
        guidance.extend(adr_guidance)

        # 4. Task-type specific guidance
        task_guidance = self._generate_task_specific_guidance(
            task_context, relevant_adrs
        )
        guidance.extend(task_guidance)

        # 5. Pattern and reference guidance
        if relevant_adrs:
            guidance.append(
                self.promptlets["cite_adrs"].to_guidance(
                    [adr.id for adr in relevant_adrs[:3]]
                )
            )

        # Sort by priority and return top guidance items
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        guidance.sort(key=lambda g: priority_order.get(g.priority, 3))

        return guidance[
            :8
        ]  # Limit to top 8 guidance items to keep token count reasonable

    def _generate_constraint_guidance(
        self, contract: ConstraintsContract, task_context: TaskContext
    ) -> list[PlanningGuidance]:
        """Generate guidance based on specific constraints."""
        guidance = []

        constraints = contract.constraints

        # Import constraint guidance
        if constraints.imports:
            if constraints.imports.disallow and task_context.task_type.value in [
                "dependency",
                "feature",
            ]:
                disallowed = ", ".join(constraints.imports.disallow[:3])  # Show first 3
                guidance.append(
                    PlanningGuidance(
                        guidance_type=GuidanceType.CONSTRAINT.value,
                        priority="high",
                        message=f"Do not use these disallowed imports: {disallowed}",
                        source_adrs=[],
                        actionable=True,
                    )
                )

            if constraints.imports.prefer and task_context.task_type.value in [
                "dependency",
                "feature",
            ]:
                preferred = ", ".join(constraints.imports.prefer[:3])  # Show first 3
                guidance.append(
                    PlanningGuidance(
                        guidance_type=GuidanceType.RECOMMENDATION.value,
                        priority="medium",
                        message=f"Prefer these approved alternatives: {preferred}",
                        source_adrs=[],
                        actionable=True,
                    )
                )

        # Boundary constraint guidance
        if constraints.boundaries and constraints.boundaries.rules:
            if any(
                word in task_context.keywords
                for word in ["architecture", "component", "service"]
            ):
                guidance.append(
                    PlanningGuidance(
                        guidance_type=GuidanceType.PATTERN.value,
                        priority="medium",
                        message="Follow architectural boundaries defined in accepted ADRs",
                        source_adrs=[],
                        actionable=True,
                    )
                )

        return guidance

    def _generate_adr_guidance(
        self,
        relevant_adrs: list[ContextualADR],
        relevance_scores: list[RelevanceScore],
        task_context: TaskContext,
    ) -> list[PlanningGuidance]:
        """Generate guidance based on specific relevant ADRs."""
        guidance = []

        # Focus on most relevant ADRs
        high_relevance_adrs = [
            adr for adr in relevant_adrs if adr.relevance_score >= 0.7
        ]

        for adr in high_relevance_adrs[:3]:  # Top 3 most relevant
            # Generate specific guidance based on ADR content
            if adr.key_constraints:
                constraints_text = ", ".join(
                    adr.key_constraints[:2]
                )  # Top 2 constraints
                guidance.append(
                    PlanningGuidance(
                        guidance_type=GuidanceType.CONSTRAINT.value,
                        priority="high",
                        message=f"Follow {adr.id} constraints: {constraints_text}",
                        source_adrs=[adr.id],
                        actionable=True,
                    )
                )

            # Reference for detailed information
            if adr.summary:
                guidance.append(
                    PlanningGuidance(
                        guidance_type=GuidanceType.REFERENCE.value,
                        priority="medium",
                        message=f"Reference {adr.id} for {adr.summary.lower()}",
                        source_adrs=[adr.id],
                        actionable=False,
                    )
                )

        return guidance

    def _generate_task_specific_guidance(
        self, task_context: TaskContext, relevant_adrs: list[ContextualADR]
    ) -> list[PlanningGuidance]:
        """Generate guidance specific to the task type."""
        guidance = []
        task_type = task_context.task_type.value

        if task_type == "feature":
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.PATTERN.value,
                    priority="medium",
                    message="Consider impact on existing architecture and follow established patterns",
                    source_adrs=[],
                    actionable=True,
                )
            )

        elif task_type == "dependency":
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.PREFLIGHT.value,
                    priority="high",
                    message="Always use preflight check before adding dependencies",
                    source_adrs=[],
                    actionable=True,
                )
            )

        elif task_type == "refactor":
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.WARNING.value,
                    priority="medium",
                    message="Ensure refactoring doesn't violate architectural boundaries",
                    source_adrs=[],
                    actionable=True,
                )
            )

        elif task_type == "integration":
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.APPROVAL.value,
                    priority="high",
                    message="External integrations typically require ADR approval",
                    source_adrs=[],
                    actionable=True,
                )
            )

        elif task_type == "security":
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.WARNING.value,
                    priority="critical",
                    message="Security changes require careful review and approval",
                    source_adrs=[],
                    actionable=True,
                )
            )

        # Add complexity-based guidance
        if task_context.estimated_complexity == "high":
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.PATTERN.value,
                    priority="medium",
                    message="Complex changes should be broken down and reviewed incrementally",
                    source_adrs=[],
                    actionable=True,
                )
            )

        # Add priority-based guidance
        if task_context.estimated_priority in ["critical", "high"]:
            guidance.append(
                PlanningGuidance(
                    guidance_type=GuidanceType.WARNING.value,
                    priority="high",
                    message="High-priority changes require extra attention to architectural compliance",
                    source_adrs=[],
                    actionable=True,
                )
            )

        return guidance

    def generate_summary_guidance(
        self,
        task_context: TaskContext,
        relevant_adrs: list[ContextualADR],
        constraints_contract: ConstraintsContract | None,
    ) -> str:
        """Generate a summary guidance message for the context packet."""

        lines = []

        # Task-specific guidance
        task_type = task_context.task_type.value
        if task_type == "dependency":
            lines.append("Use preflight checks before adding any dependencies.")
        elif task_type == "feature":
            lines.append(
                "Follow established patterns and consider architectural impact."
            )
        elif task_type == "refactor":
            lines.append("Maintain architectural boundaries during restructuring.")
        elif task_type == "integration":
            lines.append("External integrations require approval and careful design.")

        # Constraint summary
        if constraints_contract and not constraints_contract.constraints.is_empty():
            constraint_count = 0
            if constraints_contract.constraints.imports:
                if constraints_contract.constraints.imports.disallow:
                    constraint_count += len(
                        constraints_contract.constraints.imports.disallow
                    )
                if constraints_contract.constraints.imports.prefer:
                    constraint_count += len(
                        constraints_contract.constraints.imports.prefer
                    )

            if constraint_count > 0:
                lines.append(
                    f"Follow {constraint_count} active import/dependency constraints."
                )

        # ADR reference
        if relevant_adrs:
            accepted_adrs = [
                adr for adr in relevant_adrs if adr.status.value == "accepted"
            ]
            if accepted_adrs:
                lines.append(
                    f"Reference {len(accepted_adrs)} accepted ADRs for detailed guidance."
                )

        # Default guidance
        if not lines:
            lines.append(
                "Follow existing architectural decisions and get approval for new ones."
            )

        return " ".join(lines)
