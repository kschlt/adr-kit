"""Policy extraction engine with hybrid approach.

This module implements the three-tier policy extraction strategy:
1. Structured policy from front-matter (primary)
2. Pattern matching from content (backup)
3. Future AI-assisted extraction (placeholder)

Design decisions:
- Structured policy takes priority over pattern extraction
- Pattern matching handles common ADR language patterns
- Merges multiple sources into unified policy model
- Provides clear rationales for extracted policies
"""

import re

from .model import (
    ADR,
    BoundaryPolicy,
    BoundaryRule,
    ImportPolicy,
    PolicyModel,
    PythonPolicy,
)


class PolicyPatternExtractor:
    """Extract policies from ADR content using pattern matching."""

    def __init__(self) -> None:
        # Common patterns for identifying banned imports/libraries
        self.import_ban_patterns = [
            # "Don't use X", "Avoid X", "Ban X"
            r"(?i)(?:don't\s+use|avoid|ban|deprecated?)\s+([a-zA-Z0-9\-_@/]+)",
            # "No longer use X"
            r"(?i)no\s+longer\s+use\s+([a-zA-Z0-9\-_@/]+)",
            # "X is deprecated"
            r"(?i)([a-zA-Z0-9\-_@/]+)\s+is\s+deprecated",
        ]

        # Patterns for preferred alternatives
        self.preference_patterns = [
            # "Use Y instead of X"
            r"(?i)use\s+([a-zA-Z0-9\-_@/]+)\s+instead\s+of\s+([a-zA-Z0-9\-_@/]+)",
            # "Replace X with Y"
            r"(?i)replace\s+([a-zA-Z0-9\-_@/]+)\s+with\s+([a-zA-Z0-9\-_@/]+)",
            # "Prefer Y over X"
            r"(?i)prefer\s+([a-zA-Z0-9\-_@/]+)\s+over\s+([a-zA-Z0-9\-_@/]+)",
        ]

        # Boundary/architecture patterns
        self.boundary_patterns = [
            # "X should not access Y"
            r"(?i)([a-zA-Z0-9\-_]+)\s+should\s+not\s+(?:access|call|use)\s+([a-zA-Z0-9\-_]+)",
            # "No direct access from X to Y"
            r"(?i)no\s+direct\s+access\s+from\s+([a-zA-Z0-9\-_]+)\s+to\s+([a-zA-Z0-9\-_]+)",
            # "X must go through Y"
            r"(?i)([a-zA-Z0-9\-_]+)\s+must\s+go\s+through\s+([a-zA-Z0-9\-_]+)",
        ]

        # Common library name mappings for normalization
        self.library_mappings = {
            "react-query": "@tanstack/react-query",
            "react query": "@tanstack/react-query",
            "tanstack query": "@tanstack/react-query",
            "axios": "axios",
            "fetch": "fetch",
            "lodash": "lodash",
            "moment": "moment",
            "momentjs": "moment",
            "moment.js": "moment",
            "date-fns": "date-fns",
            "dayjs": "dayjs",
            "jquery": "jquery",
            "underscore": "underscore",
        }

    def extract_from_content(self, content: str) -> PolicyModel:
        """Extract policy from ADR content using pattern matching."""
        imports = self._extract_import_policies(content)
        boundaries = self._extract_boundary_policies(content)
        python_policies = self._extract_python_policies(content)
        rationales = self._extract_rationales(content)

        return PolicyModel(
            imports=imports,
            boundaries=boundaries,
            python=python_policies,
            rationales=rationales,
        )

    def _extract_import_policies(self, content: str) -> ImportPolicy | None:
        """Extract import-related policies from content."""
        disallow = set()
        prefer = set()

        # Extract banned imports
        for pattern in self.import_ban_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                normalized = self._normalize_library_name(match)
                if normalized:
                    disallow.add(normalized)

        # Extract preferences
        for pattern in self.preference_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) == 2:  # (preferred, deprecated)
                    preferred, deprecated = match
                    preferred_norm = self._normalize_library_name(preferred)
                    deprecated_norm = self._normalize_library_name(deprecated)

                    if preferred_norm:
                        prefer.add(preferred_norm)
                    if deprecated_norm:
                        disallow.add(deprecated_norm)

        if disallow or prefer:
            return ImportPolicy(
                disallow=list(disallow) if disallow else None,
                prefer=list(prefer) if prefer else None,
            )

        return None

    def _extract_boundary_policies(self, content: str) -> BoundaryPolicy | None:
        """Extract architectural boundary policies from content."""
        rules = []

        for pattern in self.boundary_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) == 2:
                    source, target = match
                    # Create forbid rule
                    rule = BoundaryRule(forbid=f"{source} -> {target}")
                    rules.append(rule)

        if rules:
            return BoundaryPolicy(layers=None, rules=rules)

        return None

    def _extract_python_policies(self, content: str) -> PythonPolicy | None:
        """Extract Python-specific policies from content."""
        python_libs = {"requests", "urllib", "urllib2", "httplib", "http.client"}
        disallow = set()

        # Look for Python-specific import restrictions
        for pattern in self.import_ban_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match.lower() in python_libs:
                    disallow.add(match.lower())

        if disallow:
            return PythonPolicy(disallow_imports=list(disallow))

        return None

    def _extract_rationales(self, content: str) -> list[str] | None:
        """Extract rationales for the policies from content."""
        rationales = set()

        # Common rationale keywords
        rationale_patterns = [
            r"(?i)for\s+(performance|security|maintainability|consistency|bundle\s+size)",
            r"(?i)to\s+(?:improve|enhance|ensure)\s+(performance|security|maintainability|consistency)",
            r"(?i)(?:better|improved)\s+(performance|security|maintainability|developer\s+experience)",
        ]

        for pattern in rationale_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                rationale = match.replace("_", " ").title()
                rationales.add(rationale)

        return list(rationales) if rationales else None

    def _normalize_library_name(self, name: str) -> str | None:
        """Normalize library names using common mappings."""
        name_lower = name.lower().strip()
        return self.library_mappings.get(name_lower, name if len(name) > 1 else None)


class PolicyExtractor:
    """Main policy extraction engine with hybrid approach."""

    def __init__(self) -> None:
        self.pattern_extractor = PolicyPatternExtractor()

    def extract_policy(self, adr: ADR) -> PolicyModel:
        """Extract unified policy using hybrid approach.

        Priority:
        1. Structured policy from front-matter (preferred)
        2. Pattern extraction from content (backup)
        3. Merge both with structured taking priority
        """
        # Tier 1: Structured policy (highest priority)
        structured_policy = adr.front_matter.policy

        # Tier 2: Pattern extraction (backup)
        pattern_policy = self.pattern_extractor.extract_from_content(adr.content)

        # Merge policies with structured taking priority
        merged_policy = self._merge_policies(structured_policy, pattern_policy)

        return merged_policy

    def _merge_policies(
        self, structured: PolicyModel | None, pattern: PolicyModel | None
    ) -> PolicyModel:
        """Merge structured and pattern-extracted policies."""
        if structured and pattern:
            # Merge both, with structured taking priority
            return PolicyModel(
                imports=structured.imports or pattern.imports,
                boundaries=structured.boundaries or pattern.boundaries,
                python=structured.python or pattern.python,
                rationales=self._merge_lists(structured.rationales, pattern.rationales),
            )
        elif structured:
            return structured
        elif pattern:
            return pattern
        else:
            # Return empty policy - explicit None values for mypy
            return PolicyModel(
                imports=None,
                boundaries=None,
                python=None,
                rationales=None,
            )

    def _merge_lists(
        self, list1: list[str] | None, list2: list[str] | None
    ) -> list[str] | None:
        """Merge two lists, removing duplicates."""
        if list1 and list2:
            combined = set(list1) | set(list2)
            return list(combined)
        return list1 or list2

    def has_extractable_policy(self, adr: ADR) -> bool:
        """Check if ADR has any extractable policy information."""
        policy = self.extract_policy(adr)

        return (
            (policy.imports and bool(policy.imports.disallow or policy.imports.prefer))
            or (
                policy.boundaries
                and bool(policy.boundaries.layers or policy.boundaries.rules)
            )
            or (policy.python and bool(policy.python.disallow_imports))
            or bool(policy.rationales)
        )

    def validate_policy_completeness(self, adr: ADR) -> list[str]:
        """Validate that accepted ADRs have sufficient policy information."""
        from .model import ADRStatus

        errors = []

        if adr.front_matter.status == ADRStatus.ACCEPTED:
            if not self.has_extractable_policy(adr):
                errors.append(
                    f"ADR {adr.front_matter.id} is accepted but has no extractable policy. "
                    "Add structured policy in front-matter or include decision rationales in content."
                )

        return errors
