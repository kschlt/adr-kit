"""Constraints contract system for ADR-Kit.

The contract system is the keystone component that transforms individual ADR policies
into a unified, machine-readable contract that agents can follow deterministically.

Key components:
- Builder: Merges accepted ADR policies into constraints_accepted.json
- Merger: Handles conflict resolution and topological sorting
- Cache: Hash-based caching for performance
- Models: Data structures for the contract system
"""

from .builder import ConstraintsContractBuilder, ContractBuildError
from .cache import ContractCache
from .merger import MergeResult, PolicyConflict, PolicyMerger
from .models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
    PolicyProvenance,
)

__all__ = [
    "ConstraintsContractBuilder",
    "ContractBuildError",
    "ConstraintsContract",
    "PolicyMerger",
    "PolicyConflict",
    "MergeResult",
    "ContractCache",
    "ContractMetadata",
    "PolicyProvenance",
    "MergedConstraints",
]
