"""Policy merger with conflict resolution and topological sorting.

This module implements the "deny beats allow" rule and handles conflicts between
ADRs in a deterministic way. It also respects supersede relationships to ensure
that newer decisions override older ones appropriately.
"""

from dataclasses import dataclass
from datetime import datetime

from ..core.model import ADR, BoundaryPolicy, ImportPolicy, PythonPolicy
from .models import MergedConstraints, PolicyProvenance


@dataclass
class PolicyConflict:
    """Represents a conflict between two ADR policies."""

    rule_type: str  # "import_disallow_vs_prefer", "boundary_conflict", etc.
    adr1_id: str
    adr1_title: str
    adr2_id: str
    adr2_title: str
    conflicting_item: str
    description: str
    resolution: str | None = None  # How the conflict was resolved


@dataclass
class MergeResult:
    """Result of merging multiple ADR policies."""

    constraints: MergedConstraints
    provenance: dict[str, PolicyProvenance]
    conflicts: list[PolicyConflict]
    success: bool

    @property
    def has_unresolved_conflicts(self) -> bool:
        """Check if there are conflicts that couldn't be resolved."""
        return any(c.resolution is None for c in self.conflicts)


class PolicyMerger:
    """Merges policies from multiple accepted ADRs with conflict resolution."""

    def __init__(self) -> None:
        self.conflicts: list[PolicyConflict] = []

    def merge_policies(self, accepted_adrs: list[ADR]) -> MergeResult:
        """Merge policies from all accepted ADRs into unified constraints.

        Uses topological sorting based on supersede relationships, then applies
        "deny beats allow" rule for conflict resolution.
        """
        self.conflicts = []

        # Sort ADRs topologically based on supersede relationships
        sorted_adrs = self._topological_sort(accepted_adrs)

        # Merge policies in order (later ADRs can override earlier ones)
        # Explicit None values for mypy - Pydantic fields are optional
        merged_imports = ImportPolicy(disallow=None, prefer=None)
        merged_boundaries = BoundaryPolicy(layers=None, rules=None)
        merged_python = PythonPolicy(disallow_imports=None)
        provenance = {}

        for adr in sorted_adrs:
            if not adr.front_matter.policy:
                continue

            policy = adr.front_matter.policy
            adr_id = adr.front_matter.id
            adr_title = adr.front_matter.title
            effective_date = datetime.combine(
                adr.front_matter.date, datetime.min.time()
            )

            # Merge import policies
            if policy.imports:
                merged_imports, import_provenance = self._merge_import_policy(
                    merged_imports, policy.imports, adr_id, adr_title, effective_date
                )
                provenance.update(import_provenance)

            # Merge boundary policies
            if policy.boundaries:
                merged_boundaries, boundary_provenance = self._merge_boundary_policy(
                    merged_boundaries,
                    policy.boundaries,
                    adr_id,
                    adr_title,
                    effective_date,
                )
                provenance.update(boundary_provenance)

            # Merge Python policies
            if policy.python:
                merged_python, python_provenance = self._merge_python_policy(
                    merged_python, policy.python, adr_id, adr_title, effective_date
                )
                provenance.update(python_provenance)

        # Create final constraints
        constraints = MergedConstraints(
            imports=(
                merged_imports
                if (merged_imports.disallow or merged_imports.prefer)
                else None
            ),
            boundaries=(
                merged_boundaries
                if (merged_boundaries.layers or merged_boundaries.rules)
                else None
            ),
            python=merged_python if merged_python.disallow_imports else None,
        )

        return MergeResult(
            constraints=constraints,
            provenance=provenance,
            conflicts=self.conflicts.copy(),
            success=not any(c.resolution is None for c in self.conflicts),
        )

    def _topological_sort(self, adrs: list[ADR]) -> list[ADR]:
        """Sort ADRs topologically based on supersede relationships.

        ADRs that supersede others come later in the list, so they can override.
        """
        # For now, simple sort by date (older first)
        # TODO: Implement proper topological sort based on supersedes relationships
        return sorted(adrs, key=lambda adr: adr.front_matter.date)

    def _merge_import_policy(
        self,
        existing: ImportPolicy,
        new: ImportPolicy,
        adr_id: str,
        adr_title: str,
        effective_date: datetime,
    ) -> tuple[ImportPolicy, dict[str, PolicyProvenance]]:
        """Merge import policies with conflict detection."""
        provenance = {}

        # Start with existing lists
        merged_disallow = set(existing.disallow or [])
        merged_prefer = set(existing.prefer or [])

        # Add new disallow items
        if new.disallow:
            for item in new.disallow:
                # Check for conflicts with existing prefer
                if item in merged_prefer:
                    conflict = PolicyConflict(
                        rule_type="import_disallow_vs_prefer",
                        adr1_id=adr_id,
                        adr1_title=adr_title,
                        adr2_id="previous",  # TODO: Track specific source
                        adr2_title="previous ADR",
                        conflicting_item=item,
                        description=f"ADR {adr_id} wants to disallow '{item}' but previous ADR prefers it",
                        resolution="disallow wins (deny beats allow)",
                    )
                    self.conflicts.append(conflict)

                    # Apply "deny beats allow" rule
                    merged_prefer.discard(item)

                merged_disallow.add(item)
                provenance[f"imports.disallow.{item}"] = PolicyProvenance(
                    adr_id=adr_id,
                    adr_title=adr_title,
                    rule_path=f"imports.disallow.{item}",
                    effective_date=effective_date,
                )

        # Add new prefer items
        if new.prefer:
            for item in new.prefer:
                # Check for conflicts with existing disallow
                if item in merged_disallow:
                    conflict = PolicyConflict(
                        rule_type="import_prefer_vs_disallow",
                        adr1_id=adr_id,
                        adr1_title=adr_title,
                        adr2_id="previous",
                        adr2_title="previous ADR",
                        conflicting_item=item,
                        description=f"ADR {adr_id} wants to prefer '{item}' but previous ADR disallows it",
                        resolution="disallow wins (deny beats allow)",
                    )
                    self.conflicts.append(conflict)

                    # Don't add to prefer if disallowed
                    continue

                merged_prefer.add(item)
                provenance[f"imports.prefer.{item}"] = PolicyProvenance(
                    adr_id=adr_id,
                    adr_title=adr_title,
                    rule_path=f"imports.prefer.{item}",
                    effective_date=effective_date,
                )

        return (
            ImportPolicy(
                disallow=list(merged_disallow) if merged_disallow else None,
                prefer=list(merged_prefer) if merged_prefer else None,
            ),
            provenance,
        )

    def _merge_boundary_policy(
        self,
        existing: BoundaryPolicy,
        new: BoundaryPolicy,
        adr_id: str,
        adr_title: str,
        effective_date: datetime,
    ) -> tuple[BoundaryPolicy, dict[str, PolicyProvenance]]:
        """Merge boundary policies (for now, just combine them)."""
        provenance = {}

        # Combine layers (later ADRs can override)
        merged_layers = list(existing.layers or [])
        if new.layers:
            # Simple append for now - TODO: implement proper merging with conflict detection
            merged_layers.extend(new.layers)

            for _i, layer in enumerate(new.layers):
                provenance[f"boundaries.layers.{layer.name}"] = PolicyProvenance(
                    adr_id=adr_id,
                    adr_title=adr_title,
                    rule_path=f"boundaries.layers.{layer.name}",
                    effective_date=effective_date,
                )

        # Combine rules
        merged_rules = list(existing.rules or [])
        if new.rules:
            merged_rules.extend(new.rules)

            for _i, rule in enumerate(new.rules):
                provenance[f"boundaries.rules.{rule.forbid}"] = PolicyProvenance(
                    adr_id=adr_id,
                    adr_title=adr_title,
                    rule_path=f"boundaries.rules.{rule.forbid}",
                    effective_date=effective_date,
                )

        return (
            BoundaryPolicy(
                layers=merged_layers if merged_layers else None,
                rules=merged_rules if merged_rules else None,
            ),
            provenance,
        )

    def _merge_python_policy(
        self,
        existing: PythonPolicy,
        new: PythonPolicy,
        adr_id: str,
        adr_title: str,
        effective_date: datetime,
    ) -> tuple[PythonPolicy, dict[str, PolicyProvenance]]:
        """Merge Python-specific policies."""
        provenance = {}

        # Combine disallow imports
        merged_disallow = set(existing.disallow_imports or [])
        if new.disallow_imports:
            merged_disallow.update(new.disallow_imports)

            for item in new.disallow_imports:
                provenance[f"python.disallow_imports.{item}"] = PolicyProvenance(
                    adr_id=adr_id,
                    adr_title=adr_title,
                    rule_path=f"python.disallow_imports.{item}",
                    effective_date=effective_date,
                )

        return (
            PythonPolicy(
                disallow_imports=list(merged_disallow) if merged_disallow else None
            ),
            provenance,
        )
