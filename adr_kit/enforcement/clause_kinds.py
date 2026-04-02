"""Clause kind taxonomy for the enforcement plane.

Defines the canonical set of enforceable clause families that sit between
policy authoring and adapter routing. Adapters declare which kinds they
support; the router uses these declarations as a secondary routing signal.
"""

from __future__ import annotations

from enum import Enum


class ClauseKind(str, Enum):
    """Canonical clause families for architectural enforcement.

    Each value represents a stable semantic target that adapters can declare
    support for, independently of specific policy key paths.
    """

    FORBIDDEN_IMPORT = "forbidden_import"
    ALLOWED_IMPORT_SURFACE = "allowed_import_surface"
    PUBLIC_API_ONLY = "public_api_only"
    LAYER_BOUNDARY = "layer_boundary"
    FORBIDDEN_PATTERN = "forbidden_pattern"
    REQUIRED_STRUCTURE = "required_structure"
    CONFIG_INVARIANT = "config_invariant"
    WORKFLOW_POLICY = "workflow_policy"
    IAC_POLICY = "iac_policy"


# Prefix-based mapping from granular rule paths to clause kinds.
# Checked in order; first match wins.
_PREFIX_MAP: list[tuple[str, ClauseKind]] = [
    ("imports.disallow.", ClauseKind.FORBIDDEN_IMPORT),
    ("imports.prefer.", ClauseKind.ALLOWED_IMPORT_SURFACE),
    ("architecture.layer_boundaries.", ClauseKind.LAYER_BOUNDARY),
    ("architecture.required_structure.", ClauseKind.REQUIRED_STRUCTURE),
    ("patterns.", ClauseKind.FORBIDDEN_PATTERN),
    ("config_enforcement.", ClauseKind.CONFIG_INVARIANT),
    ("python.disallow_imports.", ClauseKind.FORBIDDEN_IMPORT),
]


def classify_policy_rule(rule_path: str) -> ClauseKind | None:
    """Classify a granular rule path to a canonical ClauseKind.

    Args:
        rule_path: A dot-separated rule path, e.g. 'imports.disallow.axios'.

    Returns:
        The matching ClauseKind, or None if the path cannot be classified.
    """
    for prefix, kind in _PREFIX_MAP:
        if rule_path.startswith(prefix):
            return kind
    return None
