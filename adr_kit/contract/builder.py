"""Constraints contract builder - the keystone component.

This module builds the unified constraints_accepted.json file that serves as the
single source of truth for all architectural decisions that agents must follow.
"""

from pathlib import Path

from ..core.model import ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from .cache import ContractCache
from .merger import PolicyMerger
from .models import ConstraintsContract, ContractMetadata


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
        accepted_adrs = []
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.status == ADRStatus.ACCEPTED:
                    accepted_adrs.append(adr)
            except ParseError as e:
                print(f"Warning: Skipping malformed ADR {file_path}: {e}")
                continue

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
        )

        # Cache the contract
        self.cache.save_contract(contract, self.adr_dir)

        return contract

    def build(self, force_rebuild: bool = False) -> ConstraintsContract:
        """Alias for build_contract() for compatibility with existing workflows."""
        return self.build_contract(force_rebuild=force_rebuild)

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
                "boundary_layers": (
                    len(contract.constraints.boundaries.layers)
                    if contract.constraints.boundaries
                    and contract.constraints.boundaries.layers
                    else 0
                ),
                "boundary_rules": (
                    len(contract.constraints.boundaries.rules)
                    if contract.constraints.boundaries
                    and contract.constraints.boundaries.rules
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
