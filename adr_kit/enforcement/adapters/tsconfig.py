"""TypeScript tsconfig adapter for enforcement pipeline.

Generates tsconfig configuration from contract config_enforcement constraints.
Reads from constraints.config_enforcement.typescript.tsconfig and writes a
standalone tsconfig.adr.json file that can be extended via tsconfig's "extends".
"""

import json
from typing import Any

from ...contract.models import MergedConstraints
from .base import BaseAdapter, ConfigFragment


def generate_tsconfig_from_contract(constraints: MergedConstraints) -> str:
    """Generate tsconfig JSON from compiled MergedConstraints.

    Args:
        constraints: MergedConstraints from the ConstraintsContract.

    Returns:
        JSON string with tsconfig configuration, or empty string if no config.
    """
    tsconfig_settings: dict[str, Any] = {}

    if (
        constraints.config_enforcement
        and constraints.config_enforcement.typescript
        and constraints.config_enforcement.typescript.tsconfig
    ):
        tsconfig_settings = constraints.config_enforcement.typescript.tsconfig

    if not tsconfig_settings:
        return ""

    config = {
        "$schema": "https://json.schemastore.org/tsconfig",
        "compilerOptions": tsconfig_settings,
        "__adr_metadata": {
            "generated_by": "ADR Kit",
            "description": "ADR-enforced TypeScript compiler options. Extend this in your tsconfig.json.",
        },
    }

    return json.dumps(config, indent=2)


class TsconfigAdapter(BaseAdapter):
    """Enforcement adapter that generates tsconfig from contract constraints."""

    @property
    def name(self) -> str:
        return "tsconfig"

    @property
    def supported_policy_keys(self) -> list[str]:
        return ["config_enforcement"]

    @property
    def supported_languages(self) -> list[str]:
        return ["typescript"]

    @property
    def config_targets(self) -> list[str]:
        return ["tsconfig.adr.json"]

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
        """Generate tsconfig fragment from merged constraints."""
        content = generate_tsconfig_from_contract(constraints)

        if not content:
            return []

        policy_keys: list[str] = []
        if (
            constraints.config_enforcement
            and constraints.config_enforcement.typescript
            and constraints.config_enforcement.typescript.tsconfig
        ):
            policy_keys.extend(
                [
                    f"config_enforcement.typescript.tsconfig.{k}"
                    for k in sorted(
                        constraints.config_enforcement.typescript.tsconfig.keys()
                    )
                ]
            )

        return [
            ConfigFragment(
                adapter=self.name,
                target_file="tsconfig.adr.json",
                content=content,
                fragment_type="json_file",
                policy_keys=policy_keys,
            )
        ]
