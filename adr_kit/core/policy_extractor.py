"""Policy extraction engine.

Reads structured policy from ADR front-matter only.
Policies are constructed by the agent via the policy guidance promptlet
during ADR creation — never extracted from natural language.
"""

from .model import (
    ADR,
    PolicyModel,
)


class PolicyExtractor:
    """Extract structured policy from ADR front-matter."""

    def extract_policy(self, adr: ADR) -> PolicyModel:
        """Extract policy from structured front-matter.

        Returns the structured policy if present, otherwise an empty PolicyModel.
        """
        structured_policy = adr.front_matter.policy

        if structured_policy:
            return structured_policy

        return PolicyModel(
            imports=None,
            boundaries=None,
            python=None,
            patterns=None,
            architecture=None,
            config_enforcement=None,
            rationales=None,
        )

    def has_extractable_policy(self, adr: ADR) -> bool:
        """Check if ADR has a structured policy in front-matter.

        Note: Rationales alone don't count as extractable policy since they
        don't provide actionable constraints for adr_planning_context.
        """
        policy = self.extract_policy(adr)

        has_policy = (
            (policy.imports and bool(policy.imports.disallow or policy.imports.prefer))
            or (
                policy.boundaries
                and bool(policy.boundaries.layers or policy.boundaries.rules)
            )
            or (policy.python and bool(policy.python.disallow_imports))
            or (policy.patterns and bool(policy.patterns.patterns))
            or (
                policy.architecture
                and bool(
                    policy.architecture.layer_boundaries
                    or policy.architecture.required_structure
                )
            )
            or (
                policy.config_enforcement
                and bool(
                    (
                        policy.config_enforcement.typescript
                        and policy.config_enforcement.typescript.tsconfig
                    )
                    or (
                        policy.config_enforcement.python
                        and (
                            policy.config_enforcement.python.ruff
                            or policy.config_enforcement.python.mypy
                        )
                    )
                )
            )
            # Note: rationales alone don't count - we need actual constraints
        )

        return bool(has_policy)

    def validate_policy_completeness(self, adr: ADR) -> list[str]:
        """Validate that accepted ADRs have sufficient policy information."""
        from .model import ADRStatus

        errors = []

        if adr.front_matter.status == ADRStatus.ACCEPTED:
            if not self.has_extractable_policy(adr):
                errors.append(
                    f"ADR {adr.front_matter.id} is accepted but has no structured policy. "
                    "Add a structured policy block in front-matter."
                )

        return errors
