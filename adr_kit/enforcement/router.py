"""Policy router for the enforcement pipeline.

The router matches contract policy keys to registered adapters, taking into
account both the adapter's declared capabilities and the detected technology
stack of the project. It produces a list of RoutingDecisions (adapter + keys
to handle) and a list of unroutable policy keys (no adapter matched).
"""

from dataclasses import dataclass, field

from ..contract.models import ConstraintsContract, MergedConstraints
from .adapters.base import BaseAdapter
from .clause_kinds import classify_policy_rule


@dataclass
class RoutingDecision:
    """A single routing outcome: one adapter selected to handle specific policy keys."""

    adapter: BaseAdapter
    """The adapter that will be called."""

    policy_keys: list[str] = field(default_factory=list)
    """Contract policy keys (e.g. 'imports.disallow.axios') assigned to this adapter."""

    clause_kinds: list[str] = field(default_factory=list)
    """Clause kinds the adapter supports (reflected from adapter.supported_clause_kinds)."""

    output_modes: list[str] = field(default_factory=list)
    """Output modes the adapter emits (reflected from adapter.output_modes)."""

    supported_stages: list[str] = field(default_factory=list)
    """Enforcement stages the adapter targets (reflected from adapter.supported_stages)."""


class PolicyRouter:
    """Match contract policy keys to registered adapters.

    Selection criteria (both must pass):
    1. The adapter declares at least one of the active constraint fields as a
       supported_policy_key.
    2. The adapter's supported_languages intersects with the detected_stack.

    Adapters that pass both criteria are included in the routing decisions.
    Policy keys for which no adapter passes are reported as unroutable.
    """

    def __init__(self, adapters: list[BaseAdapter]) -> None:
        self.adapters = adapters

    def route(
        self,
        contract: ConstraintsContract,
        detected_stack: list[str],
    ) -> tuple[list[RoutingDecision], list[str]]:
        """Route contract policy keys to adapters.

        Args:
            contract: The compiled ConstraintsContract to route from.
            detected_stack: Language identifiers present in the project,
                as returned by StackDetector.detect().

        Returns:
            A tuple of:
            - decisions: list of RoutingDecision, one per selected adapter.
            - unroutable_keys: policy keys that no adapter can handle.
        """
        active_keys = self._active_policy_keys(contract.constraints)
        stack_set = set(detected_stack)

        decisions: list[RoutingDecision] = []
        routed_keys: set[str] = set()

        for adapter in self.adapters:
            # Check language match
            if not set(adapter.supported_languages) & stack_set:
                continue

            # Check policy key match — at least one active key must be supported
            matched_keys = [
                k for k in active_keys if k in adapter.supported_policy_keys
            ]
            if not matched_keys:
                continue

            # Expand matched policy keys to granular rule paths from provenance
            granular_keys = self._expand_policy_keys(matched_keys, contract)

            # Secondary filter: if adapter declares clause kinds, only keep granular
            # keys whose classify_policy_rule result is in the declared set.
            # Adapters with empty supported_clause_kinds skip this filter (backward-compatible).
            clause_kinds = list(adapter.supported_clause_kinds)
            if clause_kinds:
                filtered = [
                    k
                    for k in granular_keys
                    if (ck := classify_policy_rule(k)) is not None
                    and ck.value in clause_kinds
                ]
                # Fall back to unfiltered if nothing matched (e.g. top-level key fallback)
                if filtered:
                    granular_keys = filtered

            decisions.append(
                RoutingDecision(
                    adapter=adapter,
                    policy_keys=granular_keys,
                    clause_kinds=clause_kinds,
                    output_modes=list(adapter.output_modes),
                    supported_stages=list(adapter.supported_stages),
                )
            )
            routed_keys.update(matched_keys)

        unroutable = [k for k in active_keys if k not in routed_keys]
        return decisions, unroutable

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_policy_keys(self, constraints: MergedConstraints) -> list[str]:
        """Return the constraint field names that have non-empty data."""
        active: list[str] = []
        if constraints.imports and (
            constraints.imports.disallow or constraints.imports.prefer
        ):
            active.append("imports")
        if constraints.python and constraints.python.disallow_imports:
            active.append("python")
        if constraints.patterns and constraints.patterns.patterns:
            active.append("patterns")
        if constraints.architecture and (
            constraints.architecture.layer_boundaries
            or constraints.architecture.required_structure
        ):
            active.append("architecture")
        if constraints.config_enforcement and (
            (
                constraints.config_enforcement.typescript
                and constraints.config_enforcement.typescript.tsconfig
            )
            or (
                constraints.config_enforcement.python
                and (
                    constraints.config_enforcement.python.ruff
                    or constraints.config_enforcement.python.mypy
                )
            )
        ):
            active.append("config_enforcement")
        return active

    def _expand_policy_keys(
        self, matched_keys: list[str], contract: ConstraintsContract
    ) -> list[str]:
        """Return granular rule paths from contract provenance for matched keys.

        Falls back to the top-level key name if no provenance entries exist.
        """
        granular: list[str] = []
        for key in matched_keys:
            entries = [
                rule_path
                for rule_path in contract.provenance
                if rule_path.startswith(key + ".")
            ]
            if entries:
                granular.extend(entries)
            else:
                granular.append(key)
        return granular
