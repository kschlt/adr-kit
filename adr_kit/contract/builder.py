"""Constraints contract builder - the keystone component.

This module builds the unified constraints_accepted.json file that serves as the
single source of truth for all architectural decisions that agents must follow.
"""

from pathlib import Path

from ..core.model import ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from .cache import ContractCache
from .merger import PolicyMerger
from .models import ConstraintsContract, ContractMetadata, ContractRelations


class ConstraintsContractBuilder:
    """Builds the unified constraints contract from accepted ADRs.

    This is the keystone component that transforms individual ADR policies
    into the single definitive contract that agents use for all decisions.
    """

    def __init__(self, adr_dir: Path, cache_dir: Path | None = None):
        self.adr_dir = Path(adr_dir)
        self.cache_dir = cache_dir or (self.adr_dir / ".adr" / "cache")
        self.cache = ContractCache(self.cache_dir)
        self.merger = PolicyMerger()

    def build_contract(self, force_rebuild: bool = False) -> ConstraintsContract:
        """Build the constraints contract from all accepted ADRs.

        Args:
            force_rebuild: If True, ignore cache and rebuild from scratch

        Returns:
            ConstraintsContract: The unified contract
        """
        # Try to load from cache first (unless force rebuild)
        if not force_rebuild:
            cached_contract = self.cache.get_cached_contract(self.adr_dir)
            if cached_contract:
                return cached_contract

        # Load all ADRs from directory
        adr_files = find_adr_files(self.adr_dir)
        if not adr_files:
            # No ADRs found, return empty contract
            empty_contract = ConstraintsContract.create_empty(self.adr_dir)
            self.cache.save_contract(empty_contract, self.adr_dir)
            return empty_contract

        # Parse and filter to only accepted ADRs
        all_adrs = []
        accepted_adrs = []
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr:
                    all_adrs.append(adr)
                    if adr.front_matter.status == ADRStatus.ACCEPTED:
                        accepted_adrs.append(adr)
            except ParseError as e:
                print(f"Warning: Skipping malformed ADR {file_path}: {e}")
                continue

        # Warn on depends_on/related_to references that don't resolve
        all_ids = {a.front_matter.id for a in all_adrs}
        for warning in self._validate_relation_references(accepted_adrs, all_ids):
            print(f"Warning: {warning}")

        if not accepted_adrs:
            # No accepted ADRs, return empty contract
            empty_contract = ConstraintsContract.create_empty(self.adr_dir)
            self.cache.save_contract(empty_contract, self.adr_dir)
            return empty_contract

        # Merge policies from all accepted ADRs
        merge_result = self.merger.merge_policies(accepted_adrs)

        if not merge_result.success:
            raise ContractBuildError(
                f"Failed to merge policies due to unresolvable conflicts: "
                f"{[c.description for c in merge_result.conflicts if c.resolution is None]}"
            )

        # Compute relationship indexes from all parsed ADRs
        relations = self._compute_relations(all_adrs, merge_result.provenance)

        # Create contract metadata
        metadata = ContractMetadata(
            version="1.0",  # Explicit default for mypy
            hash="",  # Will be calculated when contract is finalized
            source_adrs=[adr.id for adr in accepted_adrs],
            adr_directory=str(self.adr_dir),
        )

        # Build final contract
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=merge_result.constraints,
            provenance=merge_result.provenance,
            approved_adrs=accepted_adrs,
            relations=relations,
        )

        # Cache the contract
        self.cache.save_contract(contract, self.adr_dir)

        return contract

    def build(self, force_rebuild: bool = False) -> ConstraintsContract:
        """Alias for build_contract() for compatibility with existing workflows."""
        return self.build_contract(force_rebuild=force_rebuild)

    def _validate_relation_references(self, adrs: list, all_ids: set) -> list:
        """Return warning strings for depends_on/related_to refs to unknown ADR IDs."""
        warnings = []
        for adr in adrs:
            fm = adr.front_matter
            for field_name, refs in [
                ("depends_on", fm.depends_on or []),
                ("related_to", fm.related_to or []),
            ]:
                for ref in refs:
                    if ref not in all_ids:
                        warnings.append(
                            f"{fm.id}: {field_name} references unknown ADR '{ref}'"
                        )
        return warnings

    def _compute_relations(self, all_adrs: list, provenance: dict) -> ContractRelations:
        """Compute forward and reverse relationship indexes from ADR frontmatter.

        Uses all parsed ADRs (not only accepted) so that edges to proposed or
        deprecated ADRs are still recorded. Unresolved references are silently
        dropped — they have already been warned about by _validate_relation_references.

        Also derives clause lookup tables from the contract provenance mapping.
        """
        all_ids: set[str] = {a.front_matter.id for a in all_adrs}

        depends_on: dict[str, list[str]] = {}
        related_to: dict[str, list[str]] = {}
        supersedes_fwd: dict[str, list[str]] = {}
        required_by: dict[str, list[str]] = {}
        related_from: dict[str, list[str]] = {}
        superseded_by_rev: dict[str, list[str]] = {}

        for adr in all_adrs:
            src = adr.front_matter.id
            fm = adr.front_matter

            # depends_on / required_by (reverse)
            resolved_deps = [r for r in (fm.depends_on or []) if r in all_ids]
            if resolved_deps:
                depends_on[src] = resolved_deps
                for dep in resolved_deps:
                    if src not in required_by.setdefault(dep, []):
                        required_by[dep].append(src)

            # related_to / related_from (reverse, symmetric)
            resolved_rel = [r for r in (fm.related_to or []) if r in all_ids]
            if resolved_rel:
                related_to[src] = resolved_rel
                for rel in resolved_rel:
                    if src not in related_from.setdefault(rel, []):
                        related_from[rel].append(src)

            # supersedes / superseded_by (reverse)
            resolved_sup = [r for r in (fm.supersedes or []) if r in all_ids]
            if resolved_sup:
                supersedes_fwd[src] = resolved_sup
                for old in resolved_sup:
                    if src not in superseded_by_rev.setdefault(old, []):
                        superseded_by_rev[old].append(src)

        chains = self._build_supersession_chains(supersedes_fwd, superseded_by_rev)

        # Build clause lookup tables from provenance
        clause_to_adr: dict[str, str] = {}
        adr_to_clauses: dict[str, list[str]] = {}
        for prov in provenance.values():
            clause_to_adr[prov.clause_id] = prov.adr_id
            if prov.clause_id not in adr_to_clauses.setdefault(prov.adr_id, []):
                adr_to_clauses[prov.adr_id].append(prov.clause_id)

        return ContractRelations(
            depends_on=depends_on,
            related_to=related_to,
            supersedes=supersedes_fwd,
            required_by=required_by,
            related_from=related_from,
            superseded_by=superseded_by_rev,
            supersession_chains=chains,
            clause_to_adr=clause_to_adr,
            adr_to_clauses=adr_to_clauses,
        )

    def _build_supersession_chains(
        self,
        supersedes_fwd: dict[str, list[str]],
        superseded_by_rev: dict[str, list[str]],
    ) -> list[list[str]]:
        """Walk supersession edges to build full lineage chains (oldest → newest).

        A chain starts at the newest ADR in a lineage (one that supersedes something
        but is not itself superseded) and follows the supersedes edges backward to the
        oldest. The chain is then reversed so it reads oldest-to-newest.

        Circular references are broken by a visited set — nodes in a cycle produce
        a truncated chain rather than an infinite loop.
        """
        # Roots: ADRs that supersede something but are not themselves superseded
        all_superseding = set(supersedes_fwd.keys())
        has_predecessor = set(superseded_by_rev.keys())
        roots = all_superseding - has_predecessor

        chains: list[list[str]] = []
        for root in sorted(roots):
            chain: list[str] = []
            visited: set[str] = set()
            current: str | None = root
            while current and current not in visited:
                visited.add(current)
                chain.append(current)
                nexts = supersedes_fwd.get(current, [])
                if len(nexts) == 1:
                    current = nexts[0]
                else:
                    # Fan-out: append all unvisited targets and stop
                    chain.extend(n for n in nexts if n not in visited)
                    break
            # Reverse so chain reads oldest → newest
            chain.reverse()
            if len(chain) > 1:
                chains.append(chain)

        return chains

    def get_contract_summary(self) -> dict:
        """Get a summary of the current contract state."""
        try:
            contract = self.build_contract()
            cache_info = self.cache.get_cache_info()

            # Count constraints
            constraint_counts = {
                "import_disallow": (
                    len(contract.constraints.imports.disallow)
                    if contract.constraints.imports
                    and contract.constraints.imports.disallow
                    else 0
                ),
                "import_prefer": (
                    len(contract.constraints.imports.prefer)
                    if contract.constraints.imports
                    and contract.constraints.imports.prefer
                    else 0
                ),
                "architecture_boundaries": (
                    len(contract.constraints.architecture.layer_boundaries)
                    if contract.constraints.architecture
                    and contract.constraints.architecture.layer_boundaries
                    else 0
                ),
                "architecture_structures": (
                    len(contract.constraints.architecture.required_structure)
                    if contract.constraints.architecture
                    and contract.constraints.architecture.required_structure
                    else 0
                ),
                "pattern_rules": (
                    len(contract.constraints.patterns.patterns)
                    if contract.constraints.patterns
                    and contract.constraints.patterns.patterns
                    else 0
                ),
                "config_requirements": (
                    (
                        1
                        if contract.constraints.config_enforcement.typescript
                        and contract.constraints.config_enforcement.typescript.tsconfig
                        else 0
                    )
                    + (
                        1
                        if contract.constraints.config_enforcement.python
                        and (
                            contract.constraints.config_enforcement.python.ruff
                            or contract.constraints.config_enforcement.python.mypy
                        )
                        else 0
                    )
                    if contract.constraints.config_enforcement
                    else 0
                ),
                "python_disallow": (
                    len(contract.constraints.python.disallow_imports)
                    if contract.constraints.python
                    and contract.constraints.python.disallow_imports
                    else 0
                ),
            }

            return {
                "success": True,
                "contract_hash": contract.metadata.hash,
                "generated_at": contract.metadata.generated_at.isoformat(),
                "source_adrs": contract.metadata.source_adrs,
                "constraint_counts": constraint_counts,
                "total_constraints": sum(constraint_counts.values()),
                "cache_info": cache_info,
                "provenance_entries": len(contract.provenance),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "cache_info": self.cache.get_cache_info(),
            }

    def validate_new_policy(self, policy_dict: dict, adr_id: str) -> dict:
        """Validate that a new policy wouldn't conflict with existing constraints.

        Args:
            policy_dict: Policy data as dict (from ADR front-matter)
            adr_id: ID of the ADR being validated

        Returns:
            dict with validation results
        """
        try:
            from ..core.model import PolicyModel

            # Parse policy
            policy = PolicyModel.model_validate(policy_dict)

            # Get current contract
            current_contract = self.build_contract()

            # Check for conflicts
            conflicts = current_contract.has_conflicts_with_policy(policy, adr_id)

            return {
                "valid": len(conflicts) == 0,
                "conflicts": conflicts,
                "contract_hash": current_contract.metadata.hash,
            }

        except Exception as e:
            return {"valid": False, "error": str(e), "conflicts": []}

    def rebuild_contract(self) -> dict:
        """Force rebuild the contract and return status."""
        try:
            # Invalidate cache first
            self.cache.invalidate()

            # Rebuild contract
            contract = self.build_contract(force_rebuild=True)

            return {
                "success": True,
                "contract_hash": contract.metadata.hash,
                "generated_at": contract.metadata.generated_at.isoformat(),
                "source_adrs": contract.metadata.source_adrs,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_contract_file_path(self) -> Path:
        """Get the path where the contract file is stored."""
        return self.cache.contract_file


class ContractBuildError(Exception):
    """Raised when contract building fails due to conflicts or other issues."""

    pass
