"""Policy merger with conflict resolution and topological sorting.

This module implements the "deny beats allow" rule and handles conflicts between
ADRs in a deterministic way. It also respects supersede relationships to ensure
that newer decisions override older ones appropriately.
"""

from dataclasses import dataclass
from datetime import datetime

from ..core.model import (
    ADR,
    ArchitecturePolicy,
    ConfigEnforcementPolicy,
    ImportPolicy,
    PatternPolicy,
    PatternRule,
    PythonPolicy,
)
from .models import MergedConstraints, PolicyProvenance


def _make_provenance(
    adr_id: str,
    adr_title: str,
    rule_path: str,
    effective_date: "datetime",
) -> PolicyProvenance:
    """Create a PolicyProvenance with a deterministic clause_id."""
    return PolicyProvenance(
        adr_id=adr_id,
        adr_title=adr_title,
        rule_path=rule_path,
        effective_date=effective_date,
        clause_id=PolicyProvenance.make_clause_id(adr_id, rule_path),
    )


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
        merged_python = PythonPolicy(disallow_imports=None)
        merged_patterns: dict[str, PatternRule] = {}
        merged_architecture = ArchitecturePolicy(
            layer_boundaries=None, required_structure=None
        )
        merged_config = ConfigEnforcementPolicy(typescript=None, python=None)
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

            # Merge Python policies
            if policy.python:
                merged_python, python_provenance = self._merge_python_policy(
                    merged_python, policy.python, adr_id, adr_title, effective_date
                )
                provenance.update(python_provenance)

            # Merge pattern policies
            if policy.patterns:
                merged_patterns, pattern_provenance = self._merge_pattern_policy(
                    merged_patterns, policy.patterns, adr_id, adr_title, effective_date
                )
                provenance.update(pattern_provenance)

            # Merge architecture policies
            if policy.architecture:
                merged_architecture, arch_provenance = self._merge_architecture_policy(
                    merged_architecture,
                    policy.architecture,
                    adr_id,
                    adr_title,
                    effective_date,
                )
                provenance.update(arch_provenance)

            # Merge config enforcement policies
            if policy.config_enforcement:
                merged_config, config_provenance = self._merge_config_policy(
                    merged_config,
                    policy.config_enforcement,
                    adr_id,
                    adr_title,
                    effective_date,
                )
                provenance.update(config_provenance)

        # Create final constraints
        constraints = MergedConstraints(
            imports=(
                merged_imports
                if (merged_imports.disallow or merged_imports.prefer)
                else None
            ),
            python=merged_python if merged_python.disallow_imports else None,
            patterns=(
                PatternPolicy(patterns=merged_patterns) if merged_patterns else None
            ),
            architecture=(
                merged_architecture
                if (
                    merged_architecture.layer_boundaries
                    or merged_architecture.required_structure
                )
                else None
            ),
            config_enforcement=(
                merged_config
                if (
                    (merged_config.typescript and merged_config.typescript.tsconfig)
                    or (
                        merged_config.python
                        and (merged_config.python.ruff or merged_config.python.mypy)
                    )
                )
                else None
            ),
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
        Uses Kahn's algorithm. Falls back to date sort for ADRs with no
        supersession relationships.
        """
        if not adrs:
            return adrs

        # Build index by ID for fast lookup
        by_id = {adr.front_matter.id: adr for adr in adrs}

        # Build adjacency: predecessor → set of successors
        # If B supersedes A, then A must come before B (A → B edge)
        successors: dict[str, set[str]] = {adr.front_matter.id: set() for adr in adrs}
        in_degree: dict[str, int] = {adr.front_matter.id: 0 for adr in adrs}

        for adr in adrs:
            for superseded_id in adr.front_matter.supersedes or []:
                if superseded_id in by_id:
                    # adr supersedes superseded_id → superseded_id must come first
                    successors[superseded_id].add(adr.front_matter.id)
                    in_degree[adr.front_matter.id] += 1

        # Kahn's algorithm — start with nodes that have no predecessors
        # Tie-break with date sort for determinism
        queue = sorted(
            [adr for adr in adrs if in_degree[adr.front_matter.id] == 0],
            key=lambda a: a.front_matter.date,
        )
        result: list[ADR] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for succ_id in sorted(successors[node.front_matter.id]):
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    succ_adr = by_id[succ_id]
                    # Insert in date order among ready nodes
                    inserted = False
                    for i, q in enumerate(queue):
                        if succ_adr.front_matter.date < q.front_matter.date:
                            queue.insert(i, succ_adr)
                            inserted = True
                            break
                    if not inserted:
                        queue.append(succ_adr)

        # If cycle detected (result shorter than input), fall back to date sort
        if len(result) < len(adrs):
            return sorted(adrs, key=lambda adr: adr.front_matter.date)

        return result

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
                provenance[f"imports.disallow.{item}"] = _make_provenance(
                    adr_id, adr_title, f"imports.disallow.{item}", effective_date
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
                provenance[f"imports.prefer.{item}"] = _make_provenance(
                    adr_id, adr_title, f"imports.prefer.{item}", effective_date
                )

        return (
            ImportPolicy(
                disallow=list(merged_disallow) if merged_disallow else None,
                prefer=list(merged_prefer) if merged_prefer else None,
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
                provenance[f"python.disallow_imports.{item}"] = _make_provenance(
                    adr_id, adr_title, f"python.disallow_imports.{item}", effective_date
                )

        return (
            PythonPolicy(
                disallow_imports=list(merged_disallow) if merged_disallow else None
            ),
            provenance,
        )

    def _merge_pattern_policy(
        self,
        existing: dict[str, PatternRule],
        new: PatternPolicy,
        adr_id: str,
        adr_title: str,
        effective_date: datetime,
    ) -> tuple[dict[str, PatternRule], dict[str, PolicyProvenance]]:
        """Merge pattern policies with last-write-wins strategy."""
        provenance = {}

        # Copy existing patterns
        merged_patterns = existing.copy()

        # Add/override with new patterns (last write wins)
        if new.patterns:
            for rule_name, rule in new.patterns.items():
                merged_patterns[rule_name] = rule
                provenance[f"patterns.{rule_name}"] = _make_provenance(
                    adr_id, adr_title, f"patterns.{rule_name}", effective_date
                )

        return merged_patterns, provenance

    def _merge_architecture_policy(
        self,
        existing: ArchitecturePolicy,
        new: ArchitecturePolicy,
        adr_id: str,
        adr_title: str,
        effective_date: datetime,
    ) -> tuple[ArchitecturePolicy, dict[str, PolicyProvenance]]:
        """Merge architecture policies with concatenation and conflict detection."""
        provenance = {}

        # Concatenate layer boundaries
        merged_boundaries = list(existing.layer_boundaries or [])
        if new.layer_boundaries:
            for boundary in new.layer_boundaries:
                merged_boundaries.append(boundary)
                provenance[f"architecture.boundaries.{boundary.rule}"] = (
                    _make_provenance(
                        adr_id,
                        adr_title,
                        f"architecture.boundaries.{boundary.rule}",
                        effective_date,
                    )
                )

        # Concatenate required structures
        merged_structures = list(existing.required_structure or [])
        if new.required_structure:
            for structure in new.required_structure:
                merged_structures.append(structure)
                provenance[f"architecture.structure.{structure.path}"] = (
                    _make_provenance(
                        adr_id,
                        adr_title,
                        f"architecture.structure.{structure.path}",
                        effective_date,
                    )
                )

        return (
            ArchitecturePolicy(
                layer_boundaries=merged_boundaries if merged_boundaries else None,
                required_structure=merged_structures if merged_structures else None,
            ),
            provenance,
        )

    def _merge_config_policy(
        self,
        existing: ConfigEnforcementPolicy,
        new: ConfigEnforcementPolicy,
        adr_id: str,
        adr_title: str,
        effective_date: datetime,
    ) -> tuple[ConfigEnforcementPolicy, dict[str, PolicyProvenance]]:
        """Merge config enforcement policies with union and conflict detection."""
        from typing import Any

        provenance = {}

        # Merge TypeScript config
        merged_ts_config: dict[str, Any] = {}
        if existing.typescript and existing.typescript.tsconfig:
            merged_ts_config.update(existing.typescript.tsconfig)
        if new.typescript and new.typescript.tsconfig:
            merged_ts_config.update(new.typescript.tsconfig)
            provenance["config.typescript"] = _make_provenance(
                adr_id, adr_title, "config.typescript", effective_date
            )

        # Merge Python config
        merged_py_ruff: dict[str, Any] = {}
        merged_py_mypy: dict[str, Any] = {}

        if existing.python:
            if existing.python.ruff:
                merged_py_ruff.update(existing.python.ruff)
            if existing.python.mypy:
                merged_py_mypy.update(existing.python.mypy)

        if new.python:
            if new.python.ruff:
                merged_py_ruff.update(new.python.ruff)
                provenance["config.python.ruff"] = _make_provenance(
                    adr_id, adr_title, "config.python.ruff", effective_date
                )
            if new.python.mypy:
                merged_py_mypy.update(new.python.mypy)
                provenance["config.python.mypy"] = _make_provenance(
                    adr_id, adr_title, "config.python.mypy", effective_date
                )

        # Create merged config models
        from ..core.model import PythonConfig, TypeScriptConfig

        ts_config = (
            TypeScriptConfig(tsconfig=merged_ts_config) if merged_ts_config else None
        )
        py_config = None
        if merged_py_ruff or merged_py_mypy:
            py_config = PythonConfig(
                ruff=merged_py_ruff if merged_py_ruff else None,
                mypy=merged_py_mypy if merged_py_mypy else None,
            )

        return (
            ConfigEnforcementPolicy(typescript=ts_config, python=py_config),
            provenance,
        )
