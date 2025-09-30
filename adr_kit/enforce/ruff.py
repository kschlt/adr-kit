"""Ruff and import-linter configuration generation from ADRs.

Design decisions:
- Generate Ruff rules for Python code quality based on ADR decisions
- Create import-linter rules to enforce architectural boundaries
- Support common Python library migration patterns
- Generate rules for deprecated packages based on superseded ADRs
"""

import configparser
import re
from io import StringIO
from pathlib import Path
from typing import Any

import toml

from ..core.model import ADR, ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file


class PythonRuleExtractor:
    """Extract Python linting rules from ADR content."""

    def __init__(self) -> None:
        # Common patterns for Python library decisions
        self.python_ban_patterns = [
            r"(?i)(?:don't\s+use|avoid|ban|deprecated?)\s+([a-zA-Z0-9\-_]+)",
            r"(?i)use\s+([a-zA-Z0-9\-_]+)\s+instead\s+of\s+([a-zA-Z0-9\-_]+)",
            r"(?i)replace\s+([a-zA-Z0-9\-_]+)\s+with\s+([a-zA-Z0-9\-_]+)",
            r"(?i)no\s+longer\s+use\s+([a-zA-Z0-9\-_]+)",
        ]

        # Python library mappings
        self.python_libraries = {
            "requests": "requests",
            "urllib": "urllib",
            "httpx": "httpx",
            "aiohttp": "aiohttp",
            "flask": "flask",
            "django": "django",
            "fastapi": "fastapi",
            "sqlalchemy": "sqlalchemy",
            "peewee": "peewee",
            "pydantic": "pydantic",
            "marshmallow": "marshmallow",
            "pandas": "pandas",
            "numpy": "numpy",
            "pytest": "pytest",
            "unittest": "unittest",
            "click": "click",
            "argparse": "argparse",
            "typer": "typer",
        }

    def extract_from_adr(self, adr: Any) -> dict[str, Any]:
        """Extract Python rules from a single ADR."""
        rules: dict[str, Any] = {
            "banned_imports": [],
            "preferred_imports": {},
            "architectural_rules": [],
            "ruff_rules": {},
        }

        # Only extract from accepted ADRs
        if adr.front_matter.status != ADRStatus.ACCEPTED:
            return rules

        content = f"{adr.front_matter.title} {adr.content}".lower()
        tags = adr.front_matter.tags or []

        # Extract banned Python imports
        for pattern in self.python_ban_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:
                        preferred, banned = match
                        banned_lib = self._normalize_python_library(banned.strip())
                        preferred_lib = self._normalize_python_library(
                            preferred.strip()
                        )

                        if banned_lib:
                            rules["banned_imports"].append(banned_lib)
                            if preferred_lib:
                                rules["preferred_imports"][banned_lib] = preferred_lib
                else:
                    banned_lib = self._normalize_python_library(match.strip())
                    if banned_lib:
                        rules["banned_imports"].append(banned_lib)

        # Extract architectural rules
        if "architecture" in tags or "layering" in tags:
            rules["architectural_rules"].extend(
                self._extract_architectural_rules(content, adr)
            )

        # Extract code quality rules
        if "code-quality" in tags or "standards" in tags:
            rules["ruff_rules"].update(self._extract_ruff_rules(content))

        return rules

    def _normalize_python_library(self, name: str) -> str | None:
        """Normalize Python library name."""
        name = name.lower().strip()

        if name in self.python_libraries:
            return self.python_libraries[name]

        # Skip common words
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

        # Basic validation for Python module names
        if re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", name):
            return name

        return None

    def _extract_architectural_rules(
        self, content: str, adr: ADR
    ) -> list[dict[str, Any]]:
        """Extract architectural/layering rules."""
        rules = []

        # Look for layer separation rules
        if "layer" in content or "boundary" in content:
            # Example: "Domain layer should not depend on infrastructure"
            domain_infra_pattern = r"domain.*should not.*depend.*infrastructure"
            if re.search(domain_infra_pattern, content, re.IGNORECASE):
                rules.append(
                    {
                        "name": f"domain-infra-separation-{adr.front_matter.id.lower()}",
                        "source_modules": ["domain", "core"],
                        "forbidden_modules": ["infrastructure", "adapters"],
                        "description": "Domain layer should not depend on infrastructure",
                    }
                )

        # Look for service separation rules
        if "service" in content and ("separate" in content or "isolated" in content):
            # This would need more sophisticated parsing to extract specific services
            pass

        return rules

    def _extract_ruff_rules(self, content: str) -> dict[str, str]:
        """Extract Ruff-specific rules."""
        rules = {}

        # Type checking rules
        if "type" in content and ("enforce" in content or "strict" in content):
            rules.update(
                {
                    "ANN": "error",  # flake8-annotations
                    "UP": "error",  # pyupgrade
                }
            )

        # Code complexity rules
        if "complexity" in content or "cyclomatic" in content:
            rules["C901"] = "error"  # mccabe complexity

        # Security rules
        if "security" in content:
            rules["S"] = "error"  # flake8-bandit

        # Performance rules
        if "performance" in content:
            rules["PERF"] = "error"  # perflint

        return rules


def generate_ruff_config(adr_directory: Path | str = "docs/adr") -> str:
    """Generate Ruff configuration from ADRs.

    Args:
        adr_directory: Directory containing ADR files

    Returns:
        TOML string with Ruff configuration
    """
    extractor = PythonRuleExtractor()

    # Find and parse all ADRs
    adr_files = find_adr_files(adr_directory)
    all_banned_imports = set()
    preferred_imports = {}
    all_ruff_rules = {}

    for file_path in adr_files:
        try:
            adr = parse_adr_file(file_path, strict=False)
            if not adr:
                continue

            rules = extractor.extract_from_adr(adr)

            all_banned_imports.update(rules["banned_imports"])
            preferred_imports.update(rules["preferred_imports"])
            all_ruff_rules.update(rules["ruff_rules"])

        except ParseError:
            continue

    # Build Ruff configuration
    ruff_config = {
        "# ADR Kit Generated Configuration": "Do not edit manually",
        "target-version": "py312",
        "line-length": 88,
        "select": list(all_ruff_rules.keys()) if all_ruff_rules else ["E", "W", "F"],
        "extend-ignore": [],
    }

    # Add banned imports if any
    if all_banned_imports:
        banned_list = list(all_banned_imports)
        ruff_config["flake8-import-conventions"] = {"banned-imports": banned_list}

        # Add custom error messages
        ruff_config["# Banned imports from ADRs"] = {
            lib: f"Import of '{lib}' is not allowed according to ADR decisions"
            for lib in banned_list
        }

    return toml.dumps(ruff_config)


def generate_import_linter_config(adr_directory: Path | str = "docs/adr") -> str:
    """Generate import-linter configuration from ADRs.

    Args:
        adr_directory: Directory containing ADR files

    Returns:
        INI string with import-linter configuration
    """
    extractor = PythonRuleExtractor()

    # Find and parse all ADRs
    adr_files = find_adr_files(adr_directory)
    all_architectural_rules = []

    for file_path in adr_files:
        try:
            adr = parse_adr_file(file_path, strict=False)
            if not adr:
                continue

            rules = extractor.extract_from_adr(adr)
            all_architectural_rules.extend(rules["architectural_rules"])

        except ParseError:
            continue

    # Build import-linter configuration
    config = configparser.ConfigParser()

    # Main configuration
    config["importlinter"] = {
        "root_package": "src",
        "include_external_packages": "False",
    }

    # Add architectural rules as contracts
    for _i, rule in enumerate(all_architectural_rules):
        contract_name = f"contract:{rule['name']}"
        config[contract_name] = {
            "name": rule["description"],
            "type": "forbidden",
            "source_modules": "\n    ".join(rule["source_modules"]),
            "forbidden_modules": "\n    ".join(rule["forbidden_modules"]),
        }

    # Add general layer separation if no specific rules found
    if not all_architectural_rules:
        config["contract:domain-infrastructure"] = {
            "name": "Domain layer should not depend on infrastructure",
            "type": "forbidden",
            "source_modules": "\n    domain\n    core",
            "forbidden_modules": "\n    infrastructure\n    adapters",
        }

    # Convert to string
    output = StringIO()
    config.write(output)
    content = output.getvalue()

    # Add header comment
    header = """# Import Linter Configuration Generated from ADRs
# Do not edit manually - regenerate using: adr-kit export-lint import-linter

"""

    return header + content


def generate_pyproject_ruff_section(
    adr_directory: Path | str = "docs/adr",
) -> dict[str, Any]:
    """Generate Ruff section for pyproject.toml from ADRs.

    Args:
        adr_directory: Directory containing ADR files

    Returns:
        Dictionary with Ruff configuration for pyproject.toml
    """
    extractor = PythonRuleExtractor()

    # Find and parse all ADRs
    adr_files = find_adr_files(adr_directory)
    all_ruff_rules = {}

    for file_path in adr_files:
        try:
            adr = parse_adr_file(file_path, strict=False)
            if not adr:
                continue

            rules = extractor.extract_from_adr(adr)
            all_ruff_rules.update(rules["ruff_rules"])

        except ParseError:
            continue

    # Return pyproject.toml compatible structure
    return {
        "tool": {
            "ruff": {
                "target-version": "py312",
                "line-length": 88,
                "select": (
                    list(all_ruff_rules.keys()) if all_ruff_rules else ["E", "W", "F"]
                ),
                "extend-ignore": [],
            }
        }
    }
