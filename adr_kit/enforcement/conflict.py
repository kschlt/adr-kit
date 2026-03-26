"""Conflict detection for the enforcement pipeline.

Two types of conflicts are detected:

1. Policy-contract conflicts: A new ADR policy contradicts the existing contract.
   Used by the Decision Plane (pre-approval validation) and reusable by any
   decision-plane workflow (e.g., pre-approval checks).

2. Fragment-config conflicts: A generated config fragment contradicts existing
   user configuration already on disk in the target file.
   Used by the enforcement pipeline before writing fragments.
"""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import toml

from ..contract.models import ConstraintsContract
from ..core.model import PolicyModel

if TYPE_CHECKING:
    from .adapters.base import ConfigFragment
    from .pipeline import EnforcementConflict


class ConflictDetector:
    """Detects conflicts in the enforcement pipeline.

    Instances are stateless; create one per pipeline run or reuse freely.
    """

    def detect_policy_conflicts(
        self,
        new_policy: PolicyModel,
        contract: ConstraintsContract,
    ) -> list["EnforcementConflict"]:
        """Detect contradictions between a new ADR policy and the existing contract.

        This is a Decision Plane utility: call it before approving an ADR to
        surface architectural contradictions between decisions. The detection
        logic is intentionally reusable outside the enforcement pipeline.

        Args:
            new_policy: The structured policy from the ADR being approved.
            contract: The current compiled ConstraintsContract.

        Returns:
            List of EnforcementConflict describing each detected contradiction.
            Empty list means no conflicts.
        """
        from .pipeline import EnforcementConflict

        raw = contract.has_conflicts_with_policy(new_policy, adr_id="incoming")
        conflicts: list[EnforcementConflict] = []

        for description in raw:
            source_adrs = self._extract_adr_ids(description)
            conflicts.append(
                EnforcementConflict(
                    adapter="policy_router",
                    description=description,
                    source_adrs=source_adrs,
                )
            )

        # Python import disallow vs existing import prefer
        if new_policy.python and new_policy.python.disallow_imports:
            if contract.constraints.imports and contract.constraints.imports.prefer:
                for item in new_policy.python.disallow_imports:
                    if item in contract.constraints.imports.prefer:
                        source = contract._find_provenance_for_rule(
                            f"imports.prefer.{item}"
                        )
                        conflicts.append(
                            EnforcementConflict(
                                adapter="policy_router",
                                description=(
                                    f"New policy wants to disallow python import '{item}' "
                                    f"but {source} prefers it"
                                ),
                                source_adrs=[source],
                            )
                        )

        return conflicts

    def detect_config_conflicts(
        self,
        fragments: list["ConfigFragment"],
        project_path: Path,
    ) -> list["EnforcementConflict"]:
        """Detect contradictions between adapter fragments and existing user config.

        For each fragment, inspects the target file on disk. If the file exists
        and contains settings that explicitly contradict what the fragment wants
        to enforce, a conflict is recorded.

        Fragments with detected conflicts must NOT be written to disk; the
        calling pipeline is responsible for routing them to EnforcementResult.conflicts
        and surfacing them to the agent for resolution.

        Args:
            fragments: In-memory fragments produced by adapters (not yet written).
            project_path: Absolute path to the project root.

        Returns:
            List of EnforcementConflict for fragments with contradictions.
            Empty list means all fragments are safe to apply.
        """
        from .pipeline import EnforcementConflict

        conflicts: list[EnforcementConflict] = []

        for fragment in fragments:
            target = project_path / fragment.target_file
            if not target.exists():
                continue  # Nothing on disk — no conflict possible

            existing_text = target.read_text(encoding="utf-8")

            if fragment.fragment_type == "json_file":
                conflicts.extend(self._check_json_conflict(fragment, existing_text))
            elif fragment.fragment_type in ("toml_file", "toml_section"):
                conflicts.extend(self._check_toml_conflict(fragment, existing_text))

        return conflicts

    # ------------------------------------------------------------------
    # JSON conflict check (ESLint-style)
    # ------------------------------------------------------------------

    def _check_json_conflict(
        self,
        fragment: "ConfigFragment",
        existing_text: str,
    ) -> list["EnforcementConflict"]:
        """ESLint: detect rules that the fragment enables but the user has disabled."""
        from .pipeline import EnforcementConflict

        try:
            existing = json.loads(existing_text)
            generated = json.loads(fragment.content)
        except (json.JSONDecodeError, ValueError):
            return []

        conflicts: list[EnforcementConflict] = []
        existing_rules: dict = existing.get("rules", {})
        generated_rules: dict = generated.get("rules", {})

        for rule_name, generated_level in generated_rules.items():
            existing_level = existing_rules.get(rule_name)
            if existing_level is None:
                continue  # Rule not present in user config — no conflict

            if self._rule_is_disabled(existing_level) and self._rule_is_enabled(
                generated_level
            ):
                conflicts.append(
                    EnforcementConflict(
                        adapter=fragment.adapter,
                        description=(
                            f"Fragment wants to enable ESLint rule '{rule_name}' "
                            f"in '{fragment.target_file}' but the existing config "
                            f"explicitly disables it. "
                            f"Resolve: remove the 'off' override or update the ADR policy."
                        ),
                        source_adrs=list(fragment.policy_keys),
                    )
                )

        return conflicts

    # ------------------------------------------------------------------
    # TOML conflict check (Ruff-style)
    # ------------------------------------------------------------------

    def _check_toml_conflict(
        self,
        fragment: "ConfigFragment",
        existing_text: str,
    ) -> list["EnforcementConflict"]:
        """Ruff: detect rules the fragment selects that the user has explicitly ignored."""
        from .pipeline import EnforcementConflict

        try:
            existing = toml.loads(existing_text)
            generated = toml.loads(fragment.content)
        except Exception:
            return []

        conflicts: list[EnforcementConflict] = []

        # Navigate ruff lint section (handles both [lint] and [tool.ruff.lint])
        existing_lint = self._get_ruff_lint(existing)
        generated_lint = self._get_ruff_lint(generated)

        existing_ignore: set[str] = set(existing_lint.get("ignore", []))
        generated_select: set[str] = set(generated_lint.get("select", []))

        for rule in generated_select & existing_ignore:
            conflicts.append(
                EnforcementConflict(
                    adapter=fragment.adapter,
                    description=(
                        f"Fragment wants to enforce Ruff rule '{rule}' "
                        f"in '{fragment.target_file}' but the existing config "
                        f"explicitly ignores it. "
                        f"Resolve: remove the rule from 'ignore' or update the ADR policy."
                    ),
                    source_adrs=list(fragment.policy_keys),
                )
            )

        return conflicts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_is_disabled(level: object) -> bool:
        return level in ("off", 0, "0")

    @staticmethod
    def _rule_is_enabled(level: object) -> bool:
        return level not in ("off", 0, "0")

    @staticmethod
    def _get_ruff_lint(config: dict[str, Any]) -> dict[str, Any]:
        """Extract the ruff lint section regardless of nesting depth."""
        # [lint] at top level (adr-generated format)
        if "lint" in config:
            lint: dict[str, Any] = config["lint"]
            return lint
        # [tool.ruff.lint]
        result: dict[str, Any] = config.get("tool", {}).get("ruff", {}).get("lint", {})
        return result

    @staticmethod
    def _extract_adr_ids(text: str) -> list[str]:
        """Extract ADR-NNNN identifiers from a conflict description string."""
        return sorted(set(re.findall(r"ADR-\d+", text)))
