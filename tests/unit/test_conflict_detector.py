"""Unit tests for ConflictDetector (CFD task).

Covers:
- detect_policy_conflicts: new policy vs existing contract
- detect_config_conflicts: JSON (ESLint) and TOML (Ruff) fragment vs existing file
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
    PolicyProvenance,
)
from adr_kit.core.model import ImportPolicy, PolicyModel, PythonPolicy
from adr_kit.enforcement.adapters.base import ConfigFragment
from adr_kit.enforcement.conflict import ConflictDetector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract(
    imports_disallow: list[str] | None = None,
    imports_prefer: list[str] | None = None,
    provenance: dict | None = None,
) -> ConstraintsContract:
    constraints = MergedConstraints(
        imports=(
            ImportPolicy(disallow=imports_disallow, prefer=imports_prefer)
            if (imports_disallow or imports_prefer)
            else None
        ),
    )
    metadata = ContractMetadata(
        hash="abc",
        source_adrs=["ADR-0001"],
        adr_directory="/fake/adr",
    )
    prov = provenance or {}
    return ConstraintsContract(
        metadata=metadata,
        constraints=constraints,
        provenance=prov,
        approved_adrs=[],
    )


def _make_eslint_fragment(
    rules: dict,
    policy_keys: list[str] | None = None,
) -> ConfigFragment:
    content = json.dumps({"rules": rules})
    return ConfigFragment(
        adapter="eslint",
        target_file=".eslintrc.adrs.json",
        content=content,
        fragment_type="json_file",
        policy_keys=policy_keys or ["imports.disallow.axios"],
    )


RUFF_TOML_TEMPLATE = """\
[lint]
select = {select}
ignore = []
"""


def _make_ruff_fragment(
    select: list[str],
    policy_keys: list[str] | None = None,
) -> ConfigFragment:
    select_str = json.dumps(select)
    content = f"[lint]\nselect = {select_str}\n"
    return ConfigFragment(
        adapter="ruff",
        target_file=".ruff-adr.toml",
        content=content,
        fragment_type="toml_file",
        policy_keys=policy_keys or ["python.disallow_imports.requests"],
    )


# ---------------------------------------------------------------------------
# detect_policy_conflicts
# ---------------------------------------------------------------------------


class TestDetectPolicyConflicts:
    def test_no_conflict_when_contract_empty(self):
        detector = ConflictDetector()
        contract = _make_contract()
        policy = PolicyModel(imports=ImportPolicy(disallow=["flask"]))
        result = detector.detect_policy_conflicts(policy, contract)
        assert result == []

    def test_disallow_vs_prefer_conflict(self):
        """New policy disallows 'flask' but existing contract prefers it."""
        contract = _make_contract(imports_prefer=["flask"])
        detector = ConflictDetector()
        policy = PolicyModel(imports=ImportPolicy(disallow=["flask"]))
        result = detector.detect_policy_conflicts(policy, contract)
        assert len(result) == 1
        assert "flask" in result[0].description

    def test_prefer_vs_disallow_conflict(self):
        """New policy prefers 'flask' but existing contract disallows it."""
        contract = _make_contract(imports_disallow=["flask"])
        detector = ConflictDetector()
        policy = PolicyModel(imports=ImportPolicy(prefer=["flask"]))
        result = detector.detect_policy_conflicts(policy, contract)
        assert len(result) == 1
        assert "flask" in result[0].description

    def test_no_conflict_different_packages(self):
        contract = _make_contract(imports_prefer=["fastapi"])
        detector = ConflictDetector()
        policy = PolicyModel(imports=ImportPolicy(disallow=["flask"]))
        result = detector.detect_policy_conflicts(policy, contract)
        assert result == []

    def test_conflict_adapter_field_is_policy_router(self):
        contract = _make_contract(imports_prefer=["flask"])
        detector = ConflictDetector()
        policy = PolicyModel(imports=ImportPolicy(disallow=["flask"]))
        result = detector.detect_policy_conflicts(policy, contract)
        assert result[0].adapter == "policy_router"

    def test_python_disallow_vs_imports_prefer_conflict(self):
        """New python.disallow_imports vs existing imports.prefer."""
        contract = _make_contract(imports_prefer=["requests"])
        detector = ConflictDetector()
        policy = PolicyModel(python=PythonPolicy(disallow_imports=["requests"]))
        result = detector.detect_policy_conflicts(policy, contract)
        assert len(result) == 1
        assert "requests" in result[0].description

    def test_no_conflict_with_no_policy(self):
        contract = _make_contract(imports_disallow=["flask"])
        detector = ConflictDetector()
        policy = PolicyModel()
        result = detector.detect_policy_conflicts(policy, contract)
        assert result == []


# ---------------------------------------------------------------------------
# detect_config_conflicts — JSON / ESLint
# ---------------------------------------------------------------------------


class TestDetectConfigConflictsJson:
    def test_no_conflict_when_target_absent(self, tmp_path: Path):
        detector = ConflictDetector()
        fragment = _make_eslint_fragment({"no-restricted-imports": "error"})
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []

    def test_no_conflict_when_rule_not_in_existing(self, tmp_path: Path):
        existing = {"rules": {"no-console": "off"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing))
        fragment = _make_eslint_fragment({"no-restricted-imports": "error"})
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []

    def test_conflict_when_existing_disables_rule(self, tmp_path: Path):
        """Existing config has 'no-restricted-imports: off' → conflict."""
        existing = {"rules": {"no-restricted-imports": "off"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing))
        fragment = _make_eslint_fragment({"no-restricted-imports": "error"})
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert len(result) == 1
        assert "no-restricted-imports" in result[0].description
        assert result[0].adapter == "eslint"

    def test_conflict_with_numeric_zero(self, tmp_path: Path):
        """ESLint uses 0 for 'off'."""
        existing = {"rules": {"no-restricted-imports": 0}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing))
        fragment = _make_eslint_fragment({"no-restricted-imports": "error"})
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert len(result) == 1

    def test_no_conflict_when_both_enabled(self, tmp_path: Path):
        """Both existing and fragment enable the same rule — no conflict."""
        existing = {"rules": {"no-restricted-imports": "error"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing))
        fragment = _make_eslint_fragment({"no-restricted-imports": "error"})
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []

    def test_conflict_includes_policy_keys_as_source_adrs(self, tmp_path: Path):
        existing = {"rules": {"no-restricted-imports": "off"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing))
        fragment = _make_eslint_fragment(
            {"no-restricted-imports": "error"},
            policy_keys=["imports.disallow.axios"],
        )
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert "imports.disallow.axios" in result[0].source_adrs

    def test_invalid_json_in_existing_ignored(self, tmp_path: Path):
        (tmp_path / ".eslintrc.adrs.json").write_text("not valid json {{")
        fragment = _make_eslint_fragment({"no-restricted-imports": "error"})
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# detect_config_conflicts — TOML / Ruff
# ---------------------------------------------------------------------------


class TestDetectConfigConflictsToml:
    def test_no_conflict_when_target_absent(self, tmp_path: Path):
        detector = ConflictDetector()
        fragment = _make_ruff_fragment(["I001"])
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []

    def test_no_conflict_when_ignored_set_empty(self, tmp_path: Path):
        existing = "[lint]\nignore = []\n"
        (tmp_path / ".ruff-adr.toml").write_text(existing)
        fragment = _make_ruff_fragment(["I001"])
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []

    def test_conflict_when_rule_in_ignore(self, tmp_path: Path):
        """Existing config ignores I001 but fragment selects it."""
        existing = '[lint]\nignore = ["I001"]\n'
        (tmp_path / ".ruff-adr.toml").write_text(existing)
        fragment = _make_ruff_fragment(["I001"])
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert len(result) == 1
        assert "I001" in result[0].description
        assert result[0].adapter == "ruff"

    def test_no_conflict_different_rules(self, tmp_path: Path):
        existing = '[lint]\nignore = ["E501"]\n'
        (tmp_path / ".ruff-adr.toml").write_text(existing)
        fragment = _make_ruff_fragment(["I001"])
        detector = ConflictDetector()
        result = detector.detect_config_conflicts([fragment], tmp_path)
        assert result == []

    def test_multiple_fragments_multiple_conflicts(self, tmp_path: Path):
        """Two fragments with conflicts — both detected."""
        eslint_existing = {"rules": {"no-restricted-imports": "off"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(eslint_existing))
        ruff_existing = '[lint]\nignore = ["I001"]\n'
        (tmp_path / ".ruff-adr.toml").write_text(ruff_existing)

        fragments = [
            _make_eslint_fragment({"no-restricted-imports": "error"}),
            _make_ruff_fragment(["I001"]),
        ]
        detector = ConflictDetector()
        result = detector.detect_config_conflicts(fragments, tmp_path)
        assert len(result) == 2
        adapters = {c.adapter for c in result}
        assert adapters == {"eslint", "ruff"}
