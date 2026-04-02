"""Mypy configuration adapter for enforcement pipeline.

Generates mypy configuration from contract config_enforcement constraints.
Reads from constraints.config_enforcement.python.mypy and writes a standalone
.mypy-adr.ini file that can be referenced via mypy's --config-file flag.
"""

import configparser
from io import StringIO
from typing import Any

from ...contract.models import MergedConstraints
from .base import BaseAdapter, ConfigFragment


def generate_mypy_config_from_contract(constraints: MergedConstraints) -> str:
    """Generate mypy INI configuration from compiled MergedConstraints.

    Args:
        constraints: MergedConstraints from the ConstraintsContract.

    Returns:
        INI string with mypy configuration.
    """
    mypy_settings: dict[str, Any] = {}

    if (
        constraints.config_enforcement
        and constraints.config_enforcement.python
        and constraints.config_enforcement.python.mypy
    ):
        mypy_settings = constraints.config_enforcement.python.mypy

    if not mypy_settings:
        return ""

    config = configparser.ConfigParser()
    config["mypy"] = {}

    for key, value in sorted(mypy_settings.items()):
        if isinstance(value, bool):
            config["mypy"][key] = str(value)
        else:
            config["mypy"][key] = str(value)

    output = StringIO()
    config.write(output)

    header = "# ADR Kit Generated Mypy Configuration\n# Do not edit manually\n\n"
    return header + output.getvalue()


class MypyAdapter(BaseAdapter):
    """Enforcement adapter that generates mypy configuration from contract constraints."""

    @property
    def name(self) -> str:
        return "mypy"

    @property
    def supported_policy_keys(self) -> list[str]:
        return ["config_enforcement"]

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    @property
    def config_targets(self) -> list[str]:
        return [".mypy-adr.ini"]

    @property
    def supported_clause_kinds(self) -> list[str]:
        return ["config_enforcement"]

    @property
    def output_modes(self) -> list[str]:
        return ["native_config"]

    @property
    def supported_stages(self) -> list[str]:
        return ["commit", "ci"]

    def generate_fragments(
        self, constraints: MergedConstraints
    ) -> list[ConfigFragment]:
        """Generate mypy config fragment from merged constraints."""
        content = generate_mypy_config_from_contract(constraints)

        if not content:
            return []

        policy_keys: list[str] = []
        if (
            constraints.config_enforcement
            and constraints.config_enforcement.python
            and constraints.config_enforcement.python.mypy
        ):
            policy_keys.extend(
                [
                    f"config_enforcement.python.mypy.{k}"
                    for k in sorted(constraints.config_enforcement.python.mypy.keys())
                ]
            )

        return [
            ConfigFragment(
                adapter=self.name,
                target_file=".mypy-adr.ini",
                content=content,
                fragment_type="ini_file",
                policy_keys=policy_keys,
            )
        ]
