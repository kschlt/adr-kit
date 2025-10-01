"""Policy engine for evaluating technical choices against gate rules."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contract import ConstraintsContractBuilder
from .models import GateConfig, GateDecision
from .technical_choice import ChoiceType, TechnicalChoice


@dataclass
class PolicyConfig:
    """Configuration for the policy engine."""

    adr_dir: Path
    gate_config_path: Path | None = None

    def __post_init__(self) -> None:
        if self.gate_config_path is None:
            self.gate_config_path = self.adr_dir / ".adr" / "policy.json"


class PolicyEngine:
    """Engine for evaluating technical choices against policy rules."""

    def __init__(self, config: PolicyConfig):
        self.config = config
        self.gate_config = self._load_gate_config()
        self.contract_builder = ConstraintsContractBuilder(config.adr_dir)

    def _load_gate_config(self) -> GateConfig:
        """Load gate configuration from file or create default."""
        if self.config.gate_config_path and self.config.gate_config_path.exists():
            return GateConfig.from_file(str(self.config.gate_config_path))
        else:
            # Create default config and save it - explicit defaults for mypy
            default_config = GateConfig(
                default_dependency_policy=GateDecision.REQUIRES_ADR,
                default_framework_policy=GateDecision.REQUIRES_ADR,
                default_tool_policy=GateDecision.ALLOWED,
                version="1.0",
                created_by="adr-kit",
            )
            self._save_gate_config(default_config)
            return default_config

    def _save_gate_config(self, config: GateConfig) -> None:
        """Save gate configuration to file."""
        if self.config.gate_config_path:
            # Ensure directory exists
            self.config.gate_config_path.parent.mkdir(parents=True, exist_ok=True)
            config.to_file(str(self.config.gate_config_path))

    def evaluate_choice(
        self, choice: TechnicalChoice
    ) -> tuple[GateDecision, str, dict[str, Any]]:
        """Evaluate a technical choice and return decision with reasoning.

        Returns:
            Tuple of (decision, reasoning, metadata)
        """
        # Normalize the choice name
        normalized_name = self.gate_config.normalize_name(choice.name)
        category = self.gate_config.categorize_choice(normalized_name)

        # Check explicit allow list first
        if normalized_name in [name.lower() for name in self.gate_config.always_allow]:
            return (
                GateDecision.ALLOWED,
                f"'{choice.name}' is in the always-allow list",
                {"category": category, "normalized_name": normalized_name},
            )

        # Check explicit deny list
        if normalized_name in [name.lower() for name in self.gate_config.always_deny]:
            return (
                GateDecision.BLOCKED,
                f"'{choice.name}' is in the always-deny list",
                {"category": category, "normalized_name": normalized_name},
            )

        # Check against existing constraints contract
        conflict_reason = self._check_contract_conflicts(choice, normalized_name)
        if conflict_reason:
            return (
                GateDecision.CONFLICT,
                conflict_reason,
                {"category": category, "normalized_name": normalized_name},
            )

        # Apply default policies based on category and choice type
        decision = self._apply_default_policy(
            choice, category or "general", normalized_name
        )
        reasoning = self._get_default_policy_reasoning(
            choice, category or "general", decision
        )

        return (
            decision,
            reasoning,
            {"category": category, "normalized_name": normalized_name},
        )

    def _check_contract_conflicts(
        self, choice: TechnicalChoice, normalized_name: str
    ) -> str | None:
        """Check if choice conflicts with existing constraints contract."""
        try:
            # Get current constraints contract
            contract = self.contract_builder.build_contract()

            # Check import constraints
            if contract.constraints.imports:
                # Check if choice is disallowed
                if contract.constraints.imports.disallow:
                    for disallowed in contract.constraints.imports.disallow:
                        if normalized_name.lower() == disallowed.lower():
                            # Find which ADR disallows it
                            for rule_path, provenance in contract.provenance.items():
                                if rule_path == f"imports.disallow.{disallowed}":
                                    return f"'{choice.name}' is disallowed by {provenance.adr_id}: {provenance.adr_title}"

                            return (
                                f"'{choice.name}' is disallowed by existing ADR policy"
                            )

                # Check if there's a preferred alternative
                if contract.constraints.imports.prefer:
                    # For dependency choices, suggest preferred alternatives
                    if choice.choice_type in [
                        ChoiceType.DEPENDENCY,
                        ChoiceType.FRAMEWORK,
                    ]:
                        for preferred in contract.constraints.imports.prefer:
                            # If this choice serves similar purpose as a preferred one, suggest conflict
                            if self._are_similar_choices(normalized_name, preferred):
                                # Find which ADR prefers the alternative
                                for (
                                    rule_path,
                                    provenance,
                                ) in contract.provenance.items():
                                    if rule_path == f"imports.prefer.{preferred}":
                                        return f"'{choice.name}' conflicts with preferred choice '{preferred}' from {provenance.adr_id}: {provenance.adr_title}"

            return None

        except Exception:
            # If we can't load the contract, don't block the choice
            return None

    def _are_similar_choices(self, choice1: str, choice2: str) -> bool:
        """Heuristic to determine if two choices serve similar purposes."""
        # Simple heuristic based on common library categories
        similar_groups = [
            ["axios", "fetch", "request", "http-client"],
            ["lodash", "underscore", "ramda", "remeda"],
            ["moment", "dayjs", "date-fns"],
            ["jest", "vitest", "mocha", "jasmine"],
            ["webpack", "vite", "rollup", "esbuild", "parcel"],
            ["react", "vue", "angular", "svelte"],
            ["express", "koa", "fastify", "hapi"],
            ["django", "flask", "fastapi"],
        ]

        choice1_lower = choice1.lower()
        choice2_lower = choice2.lower()

        for group in similar_groups:
            if choice1_lower in group and choice2_lower in group:
                return True

        return False

    def _apply_default_policy(
        self, choice: TechnicalChoice, category: str, normalized_name: str
    ) -> GateDecision:
        """Apply default policy based on choice category."""

        # Development tools are typically allowed by default
        if category == "development_tool":
            return GateDecision.ALLOWED

        # Apply policies based on choice type
        if choice.choice_type == ChoiceType.DEPENDENCY:
            if hasattr(choice, "is_dev_dependency") and choice.is_dev_dependency:
                return self.gate_config.default_tool_policy
            else:
                return self.gate_config.default_dependency_policy

        elif choice.choice_type == ChoiceType.FRAMEWORK:
            return self.gate_config.default_framework_policy

        elif choice.choice_type == ChoiceType.TOOL:
            return self.gate_config.default_tool_policy

        else:
            # For other types (architecture, language, database, etc.)
            # Default to requiring ADR for major decisions
            return GateDecision.REQUIRES_ADR

    def _get_default_policy_reasoning(
        self, choice: TechnicalChoice, category: str, decision: GateDecision
    ) -> str:
        """Get human-readable reasoning for the default policy decision."""

        if decision == GateDecision.ALLOWED:
            if category == "development_tool":
                return f"'{choice.name}' is categorized as a development tool and is allowed by default policy"
            else:
                return f"'{choice.name}' is allowed by default policy for {category}"

        elif decision == GateDecision.REQUIRES_ADR:
            if choice.choice_type == ChoiceType.DEPENDENCY:
                return f"New runtime dependency '{choice.name}' requires ADR approval (default policy)"
            elif choice.choice_type == ChoiceType.FRAMEWORK:
                return f"New framework '{choice.name}' requires ADR approval (default policy)"
            else:
                return f"'{choice.name}' ({choice.choice_type.value}) requires ADR approval (default policy)"

        elif decision == GateDecision.BLOCKED:
            return f"'{choice.name}' is blocked by default policy"

        else:
            return f"Default policy decision: {decision.value}"

    def get_config_summary(self) -> dict[str, Any]:
        """Get summary of current gate configuration."""
        return {
            "config_file": str(self.config.gate_config_path),
            "config_exists": (
                self.config.gate_config_path.exists()
                if self.config.gate_config_path
                else False
            ),
            "default_policies": {
                "dependency": self.gate_config.default_dependency_policy.value,
                "framework": self.gate_config.default_framework_policy.value,
                "tool": self.gate_config.default_tool_policy.value,
            },
            "always_allow": self.gate_config.always_allow,
            "always_deny": self.gate_config.always_deny,
            "development_tools": len(self.gate_config.development_tools),
            "categories": len(self.gate_config.categories),
            "name_mappings": len(self.gate_config.name_mappings),
        }

    def add_to_allow_list(self, choice_name: str) -> None:
        """Add a choice to the always-allow list."""
        normalized = self.gate_config.normalize_name(choice_name)
        if normalized not in self.gate_config.always_allow:
            self.gate_config.always_allow.append(normalized)
            self._save_gate_config(self.gate_config)

    def add_to_deny_list(self, choice_name: str) -> None:
        """Add a choice to the always-deny list."""
        normalized = self.gate_config.normalize_name(choice_name)
        if normalized not in self.gate_config.always_deny:
            self.gate_config.always_deny.append(normalized)
            self._save_gate_config(self.gate_config)

    def update_default_policy(self, choice_type: str, decision: GateDecision) -> None:
        """Update default policy for a choice type."""
        if choice_type == "dependency":
            self.gate_config.default_dependency_policy = decision
        elif choice_type == "framework":
            self.gate_config.default_framework_policy = decision
        elif choice_type == "tool":
            self.gate_config.default_tool_policy = decision

        self._save_gate_config(self.gate_config)
