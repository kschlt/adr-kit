"""ESLint configuration generation from ADRs.

Design decisions:
- Parse ADRs to extract library/framework decisions
- Generate ESLint rules to ban disallowed imports
- Support common patterns like "Use React Query instead of X"
- Generate rules for deprecated patterns based on superseded ADRs
"""

import json
import re
from pathlib import Path
from typing import Any, TypedDict

from ..core.model import ADR, ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from ..core.policy_extractor import PolicyExtractor


class ADRMetadata(TypedDict):
    """Type definition for ADR metadata in ESLint config."""

    id: str
    title: str
    file_path: str | None


class ESLintADRMetadata(TypedDict):
    """Type definition for __adr_metadata section."""

    generated_by: str
    source_adrs: list[ADRMetadata]
    generation_timestamp: str | None
    preferred_libraries: dict[str, str] | None


class ESLintConfig(TypedDict):
    """Type definition for complete ESLint configuration."""

    rules: dict[str, Any]
    settings: dict[str, Any]
    env: dict[str, Any]
    extends: list[str]
    __adr_metadata: ESLintADRMetadata


class StructuredESLintGenerator:
    """Generate ESLint configuration from structured ADR policies."""

    def __init__(self) -> None:
        self.policy_extractor = PolicyExtractor()

    def generate_eslint_config(self, adr_dir: str = "docs/adr") -> ESLintConfig:
        """Generate complete ESLint configuration from all accepted ADRs.

        Args:
            adr_dir: Directory containing ADR files

        Returns:
            ESLint configuration dictionary
        """
        config: ESLintConfig = {
            "rules": {},
            "settings": {},
            "env": {},
            "extends": [],
            "__adr_metadata": {
                "generated_by": "ADR Kit",
                "source_adrs": [],
                "generation_timestamp": None,
                "preferred_libraries": None,
            },
        }

        # Find all ADR files
        adr_files = find_adr_files(adr_dir)
        accepted_adrs = []

        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.status == ADRStatus.ACCEPTED:
                    accepted_adrs.append(adr)
            except ParseError:
                continue

        # Extract policies and generate rules
        banned_imports = []
        preferred_mappings = {}

        for adr in accepted_adrs:
            policy = self.policy_extractor.extract_policy(adr)
            config["__adr_metadata"]["source_adrs"].append(
                {
                    "id": adr.front_matter.id,
                    "title": adr.front_matter.title,
                    "file_path": str(adr.file_path) if adr.file_path else None,
                }
            )

            # Process import policies
            if policy.imports:
                if policy.imports.disallow:
                    for lib in policy.imports.disallow:
                        banned_imports.append(
                            {
                                "name": lib,
                                "message": f"Use alternative instead of {lib} (per {adr.front_matter.id}: {adr.front_matter.title})",
                                "adr_id": adr.front_matter.id,
                            }
                        )

                if policy.imports.prefer:
                    for lib in policy.imports.prefer:
                        preferred_mappings[lib] = adr.front_matter.id

        # Generate no-restricted-imports rule
        if banned_imports:
            config["rules"]["no-restricted-imports"] = [
                "error",
                {"paths": banned_imports},
            ]

        # Generate additional rules based on preferences
        if preferred_mappings:
            config["__adr_metadata"]["preferred_libraries"] = preferred_mappings

        # Add timestamp
        from datetime import datetime

        config["__adr_metadata"]["generation_timestamp"] = datetime.now().isoformat()

        return config


class ESLintRuleExtractor:
    """Extract ESLint rules from ADR content (legacy pattern-based approach)."""

    def __init__(self) -> None:
        # Common patterns for identifying banned imports/libraries
        self.ban_patterns = [
            # "Don't use X", "Avoid X", "Ban X"
            r"(?i)(?:don't\s+use|avoid|ban|deprecated?)\s+([a-zA-Z0-9\-_@/]+)",
            # "Use Y instead of X"
            r"(?i)use\s+([a-zA-Z0-9\-_@/]+)\s+instead\s+of\s+([a-zA-Z0-9\-_@/]+)",
            # "Replace X with Y"
            r"(?i)replace\s+([a-zA-Z0-9\-_@/]+)\s+with\s+([a-zA-Z0-9\-_@/]+)",
            # "No longer use X"
            r"(?i)no\s+longer\s+use\s+([a-zA-Z0-9\-_@/]+)",
        ]

        # Common library name mappings
        self.library_mappings = {
            "react-query": "@tanstack/react-query",
            "react query": "@tanstack/react-query",
            "axios": "axios",
            "fetch": "fetch",
            "lodash": "lodash",
            "moment": "moment",
            "date-fns": "date-fns",
            "dayjs": "dayjs",
            "jquery": "jquery",
            "underscore": "underscore",
        }

    def extract_from_adr(self, adr: ADR) -> dict[str, Any]:
        """Extract ESLint rules from a single ADR.

        Args:
            adr: The ADR object to extract rules from

        Returns:
            Dictionary with extracted rule information
        """
        banned_imports: list[str] = []
        preferred_imports: dict[str, str] = {}
        custom_rules: list[dict[str, Any]] = []

        rules: dict[str, Any] = {
            "banned_imports": banned_imports,
            "preferred_imports": preferred_imports,
            "custom_rules": custom_rules,
        }

        # Only extract rules from accepted ADRs
        if adr.front_matter.status != ADRStatus.ACCEPTED:
            return rules

        content = f"{adr.front_matter.title} {adr.content}".lower()

        # Extract banned imports using patterns
        for pattern in self.ban_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    # Pattern with replacement (e.g., "use Y instead of X")
                    if len(match) == 2:
                        preferred, banned = match
                        banned_lib = self._normalize_library_name(banned.strip())
                        preferred_lib = self._normalize_library_name(preferred.strip())

                        if banned_lib:
                            rules["banned_imports"].append(banned_lib)
                            if preferred_lib:
                                rules["preferred_imports"][banned_lib] = preferred_lib
                else:
                    # Simple ban pattern
                    banned_lib = self._normalize_library_name(match.strip())
                    if banned_lib:
                        rules["banned_imports"].append(banned_lib)

        # Check for frontend-specific rules
        if "frontend" in (adr.front_matter.tags or []):
            rules.update(self._extract_frontend_rules(content))

        # Check for backend-specific rules
        if any(
            tag in (adr.front_matter.tags or []) for tag in ["backend", "api", "server"]
        ):
            rules.update(self._extract_backend_rules(content))

        return rules

    def _normalize_library_name(self, name: str) -> str | None:
        """Normalize library name to common import format."""
        name = name.lower().strip()

        # Check direct mappings
        if name in self.library_mappings:
            return self.library_mappings[name]

        # Skip common words that aren't libraries
        skip_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        if name in skip_words or len(name) < 2:
            return None

        # Basic validation - should look like a library name
        if re.match(r"^[a-zA-Z0-9\-_@/]+$", name):
            return name

        return None

    def _extract_frontend_rules(self, content: str) -> dict[str, Any]:
        """Extract frontend-specific ESLint rules."""
        rules: dict[str, list[dict[str, str]]] = {"custom_rules": []}

        # React-specific patterns
        if "react" in content:
            if "hooks" in content and ("don't" in content or "avoid" in content):
                rules["custom_rules"].append(
                    {"rule": "react-hooks/rules-of-hooks", "severity": "error"}
                )

        return rules

    def _extract_backend_rules(self, content: str) -> dict[str, Any]:
        """Extract backend-specific ESLint rules."""
        rules: dict[str, list[dict[str, str]]] = {"custom_rules": []}

        # Node.js specific patterns
        if "node" in content or "nodejs" in content:
            if "synchronous" in content and ("don't" in content or "avoid" in content):
                rules["custom_rules"].append({"rule": "no-sync", "severity": "error"})

        return rules


def generate_eslint_config(adr_directory: Path | str = "docs/adr") -> str:
    """Generate ESLint configuration from ADRs using hybrid approach.

    Uses structured policies first, falls back to pattern matching.

    Args:
        adr_directory: Directory containing ADR files

    Returns:
        JSON string with ESLint configuration
    """
    # Use structured policy generator (primary)
    structured_generator = StructuredESLintGenerator()
    config = structured_generator.generate_eslint_config(str(adr_directory))

    # Enhance with pattern-based extraction (backup for legacy ADRs)
    extractor = ESLintRuleExtractor()

    # Enhance with legacy pattern-based extraction for ADRs without structured policies
    additional_banned = set()
    adr_files = find_adr_files(adr_directory)

    for file_path in adr_files:
        try:
            adr = parse_adr_file(file_path, strict=False)
            if not adr or adr.front_matter.status != ADRStatus.ACCEPTED:
                continue

            # Skip if already has structured policy
            if adr.front_matter.policy and adr.front_matter.policy.imports:
                continue

            # Use pattern extraction for legacy ADRs
            rules = extractor.extract_from_adr(adr)
            additional_banned.update(rules["banned_imports"])

        except ParseError:
            continue

    # Merge additional pattern-based rules into structured config
    if additional_banned and "no-restricted-imports" in config["rules"]:
        existing_paths = config["rules"]["no-restricted-imports"][1]["paths"]
        existing_names = {item["name"] for item in existing_paths}

        for lib in additional_banned:
            if lib not in existing_names:
                existing_paths.append(
                    {
                        "name": lib,
                        "message": f"Import of '{lib}' is not allowed (extracted from ADR content)",
                    }
                )
    elif additional_banned:
        # No structured rules, use pattern-based only
        banned_patterns = []
        for lib in additional_banned:
            banned_patterns.append(
                {
                    "name": lib,
                    "message": f"Import of '{lib}' is not allowed according to ADR decisions",
                }
            )
        config["rules"]["no-restricted-imports"] = ["error", {"paths": banned_patterns}]

    # Return the enhanced configuration as JSON
    return json.dumps(config, indent=2)


def generate_eslint_overrides(
    adr_directory: Path | str = "docs/adr",
) -> dict[str, Any]:
    """Generate ESLint override configuration for specific file patterns.

    Args:
        adr_directory: Directory containing ADR files

    Returns:
        Dictionary with override configuration
    """
    # This could be extended to create file-pattern-specific rules
    # based on ADR tags or content analysis

    overrides = []

    # Example: Stricter rules for production files
    overrides.append(
        {
            "files": ["src/components/**/*.tsx", "src/pages/**/*.tsx"],
            "rules": {"no-console": "error", "no-debugger": "error"},
        }
    )

    # Example: Relaxed rules for test files
    overrides.append(
        {
            "files": ["**/*.test.{js,ts,jsx,tsx}", "**/*.spec.{js,ts,jsx,tsx}"],
            "rules": {"no-console": "warn"},
        }
    )

    return {"overrides": overrides}
