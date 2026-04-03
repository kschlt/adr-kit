"""Import-linter adapter for enforcement pipeline.

Generates import-linter configuration from contract architecture constraints.
Reads from constraints.architecture.layer_boundaries and writes a standalone
.importlinter-adr INI file for architectural boundary enforcement.
"""

import configparser
from io import StringIO

from ...contract.models import MergedConstraints
from ...core.model import LayerBoundaryRule
from ..clause_kinds import ClauseKind, EnforcementStage, OutputMode
from .base import BaseAdapter, ConfigFragment


def _parse_boundary_rule(rule_str: str) -> tuple[str, str] | None:
    """Parse a boundary rule string like 'ui -> database' into (source, forbidden).

    Returns:
        Tuple of (source_module, forbidden_module) or None if unparseable.
    """
    parts = rule_str.split("->")
    if len(parts) != 2:
        return None
    source = parts[0].strip()
    forbidden = parts[1].strip()
    if not source or not forbidden:
        return None
    return (source, forbidden)


def generate_import_linter_config_from_contract(
    constraints: MergedConstraints,
) -> str:
    """Generate import-linter INI configuration from compiled MergedConstraints.

    Args:
        constraints: MergedConstraints from the ConstraintsContract.

    Returns:
        INI string with import-linter configuration, or empty string if no boundaries.
    """
    boundaries: list[LayerBoundaryRule] = []

    if constraints.architecture and constraints.architecture.layer_boundaries:
        boundaries = constraints.architecture.layer_boundaries

    if not boundaries:
        return ""

    config = configparser.ConfigParser()

    config["importlinter"] = {
        "root_packages": "src",
        "include_external_packages": "False",
    }

    for i, boundary in enumerate(boundaries):
        parsed = _parse_boundary_rule(boundary.rule)
        if not parsed:
            continue

        source, forbidden = parsed
        contract_name = f"importlinter:contract:{i + 1}"

        description = boundary.message or f"{source} must not import from {forbidden}"

        config[contract_name] = {
            "name": description,
            "type": "forbidden",
            "source_modules": source,
            "forbidden_modules": forbidden,
        }

    # If no valid contracts were generated, return empty
    sections = [s for s in config.sections() if s.startswith("importlinter:contract:")]
    if not sections:
        return ""

    output = StringIO()
    config.write(output)

    header = (
        "# ADR Kit Generated Import-Linter Configuration\n" "# Do not edit manually\n\n"
    )
    return header + output.getvalue()


class ImportLinterAdapter(BaseAdapter):
    """Enforcement adapter that generates import-linter config from architecture constraints."""

    @property
    def name(self) -> str:
        return "import_linter"

    @property
    def supported_policy_keys(self) -> list[str]:
        return ["architecture"]

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    @property
    def config_targets(self) -> list[str]:
        return [".importlinter-adr"]

    @property
    def supported_clause_kinds(self) -> list[str]:
        return [ClauseKind.LAYER_BOUNDARY]

    @property
    def output_modes(self) -> list[OutputMode]:
        return [OutputMode.NATIVE_RULES]

    @property
    def supported_stages(self) -> list[EnforcementStage]:
        return [EnforcementStage.COMMIT, EnforcementStage.CI]

    def generate_fragments(
        self, constraints: MergedConstraints
    ) -> list[ConfigFragment]:
        """Generate import-linter config fragment from merged constraints."""
        content = generate_import_linter_config_from_contract(constraints)

        if not content:
            return []

        policy_keys: list[str] = []
        if constraints.architecture and constraints.architecture.layer_boundaries:
            policy_keys.extend(
                [
                    f"architecture.layer_boundaries.{b.rule}"
                    for b in constraints.architecture.layer_boundaries
                ]
            )

        return [
            ConfigFragment(
                adapter=self.name,
                target_file=".importlinter-adr",
                content=content,
                fragment_type="ini_file",
                policy_keys=policy_keys,
            )
        ]
