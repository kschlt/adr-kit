"""Main policy gate for intercepting and evaluating technical choices."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import GateDecision
from .policy_engine import PolicyConfig, PolicyEngine
from .technical_choice import TechnicalChoice, create_technical_choice


@dataclass
class GateResult:
    """Result from evaluating a technical choice through the policy gate."""

    choice: TechnicalChoice
    decision: GateDecision
    reasoning: str
    metadata: dict[str, Any]
    evaluated_at: datetime

    @property
    def should_proceed(self) -> bool:
        """Whether the agent should proceed with the choice."""
        return self.decision == GateDecision.ALLOWED

    @property
    def requires_human_approval(self) -> bool:
        """Whether this choice requires human approval via ADR."""
        return self.decision == GateDecision.REQUIRES_ADR

    @property
    def is_blocked(self) -> bool:
        """Whether this choice is blocked and should not proceed."""
        return self.decision in [GateDecision.BLOCKED, GateDecision.CONFLICT]

    def get_agent_guidance(self) -> str:
        """Get guidance message for the agent based on the gate result."""
        if self.decision == GateDecision.ALLOWED:
            return f"✅ Approved: {self.reasoning}. You may proceed with implementing '{self.choice.name}'."

        elif self.decision == GateDecision.REQUIRES_ADR:
            return (
                f"🛑 ADR Required: {self.reasoning}. Please draft an ADR for '{self.choice.name}' "
                f"and request human approval before proceeding with implementation."
            )

        elif self.decision == GateDecision.BLOCKED:
            return (
                f"❌ Blocked: {self.reasoning}. Do not implement '{self.choice.name}'."
            )

        elif self.decision == GateDecision.CONFLICT:
            return (
                f"⚠️ Conflict: {self.reasoning}. Consider using the recommended alternative "
                f"or updating existing ADRs if '{self.choice.name}' is truly needed."
            )

        else:
            return f"Unknown gate decision: {self.decision.value}"

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "choice": {
                "type": self.choice.choice_type.value,
                "name": self.choice.name,
                "context": self.choice.context,
                "alternatives_considered": self.choice.alternatives_considered,
            },
            "decision": self.decision.value,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "evaluated_at": self.evaluated_at.isoformat(),
            "should_proceed": self.should_proceed,
            "requires_human_approval": self.requires_human_approval,
            "is_blocked": self.is_blocked,
            "agent_guidance": self.get_agent_guidance(),
        }


class PolicyGate:
    """Main policy gate for intercepting and evaluating technical choices.

    The PolicyGate is the primary interface for agents to check whether
    a technical choice (dependency, framework, etc.) should proceed or
    requires human approval via an ADR.
    """

    def __init__(self, adr_dir: Path, gate_config_path: Path | None = None):
        self.adr_dir = Path(adr_dir)
        self.config = PolicyConfig(
            adr_dir=self.adr_dir, gate_config_path=gate_config_path
        )
        self.engine = PolicyEngine(self.config)

    def evaluate(self, choice: TechnicalChoice) -> GateResult:
        """Evaluate a technical choice through the policy gate.

        Args:
            choice: The technical choice to evaluate

        Returns:
            GateResult with decision and guidance
        """
        decision, reasoning, metadata = self.engine.evaluate_choice(choice)

        return GateResult(
            choice=choice,
            decision=decision,
            reasoning=reasoning,
            metadata=metadata,
            evaluated_at=datetime.now(timezone.utc),
        )

    def evaluate_dependency(
        self,
        package_name: str,
        context: str,
        ecosystem: str = "npm",
        version_constraint: str | None = None,
        is_dev_dependency: bool = False,
        alternatives_considered: list[str] | None = None,
        **kwargs: Any,
    ) -> GateResult:
        """Convenience method for evaluating dependency choices.

        Args:
            package_name: Name of the package/dependency
            context: Why this dependency is needed
            ecosystem: Package ecosystem (npm, pypi, gem, etc.)
            version_constraint: Version constraint if any
            is_dev_dependency: Whether this is a dev dependency
            alternatives_considered: Other options considered

        Returns:
            GateResult with decision and guidance
        """
        choice = create_technical_choice(
            choice_type="dependency",
            name=package_name,
            context=context,
            package_name=package_name,
            ecosystem=ecosystem,
            version_constraint=version_constraint,
            is_dev_dependency=is_dev_dependency,
            alternatives_considered=alternatives_considered or [],
            **kwargs,
        )

        return self.evaluate(choice)

    def evaluate_framework(
        self,
        framework_name: str,
        context: str,
        use_case: str,
        architectural_impact: str = "To be determined",
        current_solution: str | None = None,
        migration_required: bool = False,
        alternatives_considered: list[str] | None = None,
        **kwargs: Any,
    ) -> GateResult:
        """Convenience method for evaluating framework choices.

        Args:
            framework_name: Name of the framework
            context: Why this framework is needed
            use_case: What the framework will be used for
            architectural_impact: How it affects the architecture
            current_solution: What it replaces (if any)
            migration_required: Whether migration is needed
            alternatives_considered: Other options considered

        Returns:
            GateResult with decision and guidance
        """
        choice = create_technical_choice(
            choice_type="framework",
            name=framework_name,
            context=context,
            framework_name=framework_name,
            use_case=use_case,
            architectural_impact=architectural_impact,
            current_solution=current_solution,
            migration_required=migration_required,
            alternatives_considered=alternatives_considered or [],
            **kwargs,
        )

        return self.evaluate(choice)

    def evaluate_from_text(
        self, description: str, choice_hints: dict[str, Any] | None = None
    ) -> GateResult:
        """Evaluate a technical choice from text description.

        This method attempts to parse a natural language description
        of a technical choice and evaluate it through the gate.

        Args:
            description: Natural language description of the choice
            choice_hints: Optional hints about the choice type and details

        Returns:
            GateResult with decision and guidance
        """
        # Parse the description to extract choice details
        parsed_choice = self._parse_choice_description(description, choice_hints or {})

        return self.evaluate(parsed_choice)

    def _parse_choice_description(
        self, description: str, hints: dict[str, Any]
    ) -> TechnicalChoice:
        """Parse a natural language description into a TechnicalChoice.

        This is a simple heuristic parser. In a production system,
        you might use more sophisticated NLP or LLM-based parsing.
        """
        import re

        description_lower = description.lower()

        # Detect choice type from description
        if any(
            word in description_lower
            for word in ["install", "add", "use package", "import", "require"]
        ):
            choice_type = "dependency"
        elif any(
            word in description_lower
            for word in ["framework", "library", "adopt", "switch to"]
        ):
            choice_type = "framework"
        else:
            choice_type = hints.get("choice_type", "other")

        # Extract package/framework names (simple heuristic)
        # Look for quoted names, npm packages, or known patterns
        quoted_names = re.findall(r"['\"]([^'\"]+)['\"]", description)
        npm_packages = re.findall(
            r"@?[a-zA-Z0-9-_]+/[a-zA-Z0-9-_]+|[a-zA-Z0-9-_]+", description
        )

        # Take the first reasonable match
        name = None
        if quoted_names:
            name = quoted_names[0]
        elif npm_packages:
            # Filter out common words
            common_words = {
                "use",
                "add",
                "install",
                "with",
                "for",
                "from",
                "to",
                "the",
                "a",
                "an",
            }
            for package in npm_packages:
                if package.lower() not in common_words and len(package) > 2:
                    name = package
                    break

        if not name:
            name = hints.get("name", "unknown")

        # Create the choice
        return create_technical_choice(
            choice_type=choice_type, name=name, context=description, **hints
        )

    def get_gate_status(self) -> dict[str, Any]:
        """Get current status of the policy gate."""
        config_summary = self.engine.get_config_summary()

        return {
            "gate_ready": True,
            "adr_directory": str(self.adr_dir),
            "config": config_summary,
            "message": "Policy gate is ready to evaluate technical choices",
        }

    def get_recommendations_for_choice(self, choice_name: str) -> dict[str, Any]:
        """Get recommendations for a specific choice based on existing constraints."""
        try:
            contract = self.engine.contract_builder.build_contract()

            recommendations: dict[str, Any] = {
                "choice_name": choice_name,
                "normalized_name": self.engine.gate_config.normalize_name(choice_name),
                "category": self.engine.gate_config.categorize_choice(choice_name),
                "alternatives": [],
                "conflicts": [],
                "relevant_adrs": [],
            }

            # Check for preferred alternatives
            if contract.constraints.imports and contract.constraints.imports.prefer:
                for preferred in contract.constraints.imports.prefer:
                    if self.engine._are_similar_choices(choice_name, preferred):
                        recommendations["alternatives"].append(
                            {
                                "name": preferred,
                                "reason": "Preferred by existing ADR policy",
                                "source_adr": self._find_source_adr(
                                    contract, f"imports.prefer.{preferred}"
                                ),
                            }
                        )

            # Check for conflicts
            if contract.constraints.imports and contract.constraints.imports.disallow:
                for disallowed in contract.constraints.imports.disallow:
                    if choice_name.lower() == disallowed.lower():
                        recommendations["conflicts"].append(
                            {
                                "name": disallowed,
                                "reason": "Disallowed by existing ADR policy",
                                "source_adr": self._find_source_adr(
                                    contract, f"imports.disallow.{disallowed}"
                                ),
                            }
                        )

            # Add source ADRs
            recommendations["relevant_adrs"] = contract.metadata.source_adrs

            return recommendations

        except Exception as e:
            return {
                "choice_name": choice_name,
                "error": str(e),
                "message": "Unable to get recommendations",
            }

    def _find_source_adr(self, contract: Any, rule_path: str) -> str | None:
        """Find the source ADR for a specific rule path."""
        for path, provenance in contract.provenance.items():
            if path == rule_path:
                return str(provenance.adr_id)
        return None
