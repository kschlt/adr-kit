"""Fallback adapter for unroutable policy keys.

FallbackAdapter handles policy keys that no other adapter can enforce by
emitting script-authoring promptlets as ConfigFragment objects. This makes
the fallback path a first-class output mode (SCRIPT_FALLBACK) rather than
a special side path in the pipeline.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ...contract.models import MergedConstraints
from ..clause_kinds import EnforcementStage, OutputMode
from .base import BaseAdapter, ConfigFragment

if TYPE_CHECKING:
    from ...contract.models import ConstraintsContract


class FallbackAdapter(BaseAdapter):
    """Handles unroutable policy keys by emitting script-authoring promptlets.

    One ConfigFragment is produced per unroutable policy key. The fragment's
    content is a JSON promptlet that instructs the calling agent to write a
    validation script. The fragment is never written to disk (target_file="").

    output_modes = [OutputMode.SCRIPT_FALLBACK]
    """

    @property
    def name(self) -> str:
        return "fallback"

    @property
    def supported_policy_keys(self) -> list[str]:
        # Not used for normal routing — pipeline calls this adapter directly.
        return []

    @property
    def supported_languages(self) -> list[str]:
        # Not language-filtered.
        return []

    @property
    def config_targets(self) -> list[str]:
        # No files written to disk.
        return []

    @property
    def output_modes(self) -> list[OutputMode]:
        return [OutputMode.SCRIPT_FALLBACK]

    @property
    def supported_stages(self) -> list[EnforcementStage]:
        return [EnforcementStage.CI]

    def generate_fragments(
        self,
        constraints: MergedConstraints,
        *,
        policy_keys: list[str] | None = None,
        contract: ConstraintsContract | None = None,
    ) -> list[ConfigFragment]:
        """Generate one promptlet fragment per unroutable policy key.

        Args:
            constraints: Merged policy constraints (required by BaseAdapter interface).
            policy_keys: Unroutable policy keys to generate promptlets for.
                If None or empty, returns an empty list.
            contract: Full contract used to collect provenance and constraint values.

        Returns:
            One ConfigFragment per key, with fragment_type='promptlet_json'
            and output_mode=OutputMode.SCRIPT_FALLBACK. target_file is empty
            — these fragments are never written to disk.
        """
        if not policy_keys:
            return []

        fragments = []
        for key in policy_keys:
            content = self._build_promptlet(key, constraints, contract)
            fragments.append(
                ConfigFragment(
                    adapter=self.name,
                    target_file="",
                    content=content,
                    fragment_type="promptlet_json",
                    policy_keys=[key],
                    output_mode=OutputMode.SCRIPT_FALLBACK,
                )
            )
        return fragments

    def _build_promptlet(
        self,
        policy_key: str,
        constraints: MergedConstraints,
        contract: ConstraintsContract | None,
    ) -> str:
        """Build a JSON promptlet for one unroutable policy key."""
        constraint_value: Any = None
        source_adrs: list[str] = []

        if contract is not None:
            constraints_dump = contract.constraints.model_dump(exclude_none=True)
            constraint_value = constraints_dump.get(policy_key)
            source_adrs = sorted(
                {
                    prov.adr_id
                    for rule_path, prov in contract.provenance.items()
                    if rule_path == policy_key or rule_path.startswith(policy_key + ".")
                }
            )

        promptlet = {
            "unenforceable_policy": {
                "policy_key": policy_key,
                "constraint": constraint_value,
                "source_adrs": source_adrs,
            },
            "instruction": (
                f"No enforcement adapter exists for policy key '{policy_key}'. "
                "Create a validation script that checks for this policy constraint."
            ),
            "script_requirements": {
                "input": "list of file paths to check",
                "output": "EnforcementReport JSON (schema: {passed, violations: [{file, message, severity}]})",
                "integration": (
                    "Place in scripts/adr-validations/ — "
                    "the enforcement pipeline picks up all scripts in that directory"
                ),
            },
            "example_script_structure": (
                "#!/usr/bin/env python3\n"
                "import sys, json\n"
                "violations = []\n"
                "for path in sys.argv[1:]:\n"
                "    # ... check constraint ...\n"
                "    pass\n"
                'print(json.dumps({"passed": not violations, "violations": violations}))'
            ),
        }

        return json.dumps(promptlet, indent=2, default=str)
