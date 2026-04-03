"""Unit tests for enforcement.clause_kinds module and ProvenanceEntry enrichment."""

from datetime import datetime, timezone

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
    PolicyProvenance,
)
from adr_kit.core.model import ImportPolicy
from adr_kit.enforcement.adapters.base import BaseAdapter, ConfigFragment
from adr_kit.enforcement.clause_kinds import (
    ClauseKind,
    EnforcementStage,
    OutputMode,
    classify_policy_rule,
)
from adr_kit.enforcement.pipeline import EnforcementPipeline
from adr_kit.enforcement.router import PolicyRouter


class TestOutputModeEnum:
    def test_all_five_members_exist(self):
        modes = {m.value for m in OutputMode}
        assert modes == {
            "native_config",
            "native_rules",
            "generated_checker",
            "policy_file",
            "script_fallback",
        }

    def test_output_mode_is_string(self):
        for mode in OutputMode:
            assert isinstance(mode, str), f"{mode} should be a str subclass"

    def test_round_trip(self):
        assert OutputMode("native_config") is OutputMode.NATIVE_CONFIG
        assert OutputMode("script_fallback") is OutputMode.SCRIPT_FALLBACK

    def test_string_equality(self):
        assert OutputMode.NATIVE_CONFIG == "native_config"
        assert OutputMode.SCRIPT_FALLBACK == "script_fallback"
        assert OutputMode.NATIVE_RULES == "native_rules"


class TestEnforcementStageEnum:
    def test_all_three_members_exist(self):
        stages = {s.value for s in EnforcementStage}
        assert stages == {"commit", "push", "ci"}

    def test_enforcement_stage_is_string(self):
        for stage in EnforcementStage:
            assert isinstance(stage, str), f"{stage} should be a str subclass"

    def test_round_trip(self):
        assert EnforcementStage("commit") is EnforcementStage.COMMIT
        assert EnforcementStage("ci") is EnforcementStage.CI

    def test_string_equality(self):
        assert EnforcementStage.COMMIT == "commit"
        assert EnforcementStage.CI == "ci"
        assert EnforcementStage.PUSH == "push"


class TestClauseKindEnum:
    def test_all_nine_members_exist(self):
        kinds = {k.value for k in ClauseKind}
        assert kinds == {
            "forbidden_import",
            "allowed_import_surface",
            "public_api_only",
            "layer_boundary",
            "forbidden_pattern",
            "required_structure",
            "config_invariant",
            "workflow_policy",
            "iac_policy",
        }

    def test_clause_kind_is_string(self):
        for kind in ClauseKind:
            assert isinstance(kind, str), f"{kind} should be a str subclass"

    def test_clause_kind_value_equals_name_lower(self):
        assert ClauseKind.FORBIDDEN_IMPORT == "forbidden_import"
        assert ClauseKind.ALLOWED_IMPORT_SURFACE == "allowed_import_surface"
        assert ClauseKind.CONFIG_INVARIANT == "config_invariant"


class TestClassifyPolicyRule:
    def test_imports_disallow_maps_to_forbidden_import(self):
        assert (
            classify_policy_rule("imports.disallow.axios")
            == ClauseKind.FORBIDDEN_IMPORT
        )
        assert (
            classify_policy_rule("imports.disallow.flask")
            == ClauseKind.FORBIDDEN_IMPORT
        )

    def test_imports_prefer_maps_to_allowed_import_surface(self):
        assert (
            classify_policy_rule("imports.prefer.fastapi")
            == ClauseKind.ALLOWED_IMPORT_SURFACE
        )

    def test_architecture_layer_boundaries_maps_to_layer_boundary(self):
        assert (
            classify_policy_rule("architecture.layer_boundaries.0")
            == ClauseKind.LAYER_BOUNDARY
        )
        assert (
            classify_policy_rule("architecture.layer_boundaries.frontend->database")
            == ClauseKind.LAYER_BOUNDARY
        )

    def test_architecture_required_structure_maps_to_required_structure(self):
        assert (
            classify_policy_rule("architecture.required_structure.0")
            == ClauseKind.REQUIRED_STRUCTURE
        )

    def test_patterns_maps_to_forbidden_pattern(self):
        assert (
            classify_policy_rule("patterns.no_god_objects")
            == ClauseKind.FORBIDDEN_PATTERN
        )
        assert (
            classify_policy_rule("patterns.no_raw_db") == ClauseKind.FORBIDDEN_PATTERN
        )

    def test_config_enforcement_maps_to_config_invariant(self):
        assert (
            classify_policy_rule("config_enforcement.python.mypy.strict")
            == ClauseKind.CONFIG_INVARIANT
        )
        assert (
            classify_policy_rule("config_enforcement.typescript.tsconfig.strict")
            == ClauseKind.CONFIG_INVARIANT
        )

    def test_python_disallow_imports_maps_to_forbidden_import(self):
        assert (
            classify_policy_rule("python.disallow_imports.requests")
            == ClauseKind.FORBIDDEN_IMPORT
        )

    def test_unknown_prefix_returns_none(self):
        assert classify_policy_rule("unknown.key") is None
        assert classify_policy_rule("imports") is None
        assert classify_policy_rule("") is None
        assert classify_policy_rule("workflow.deploy") is None

    def test_top_level_key_without_suffix_returns_none(self):
        # Top-level keys like "imports" (no dot) are unclassifiable
        assert classify_policy_rule("imports") is None
        assert classify_policy_rule("config_enforcement") is None


def _make_provenance(rule_path: str, adr_id: str = "ADR-001") -> PolicyProvenance:
    return PolicyProvenance(
        adr_id=adr_id,
        adr_title="Test ADR",
        rule_path=rule_path,
        effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        clause_id=PolicyProvenance.make_clause_id(adr_id, rule_path),
    )


def _make_contract(provenance: dict[str, PolicyProvenance]) -> ConstraintsContract:
    return ConstraintsContract(
        metadata=ContractMetadata(hash="abc123", source_adrs=[], adr_directory="."),
        constraints=MergedConstraints(),
        provenance=provenance,
    )


class TestProvenanceEntryClauseKind:
    def setup_method(self, tmp_path_factory):
        from pathlib import Path

        self.pipeline = EnforcementPipeline(
            adr_dir=Path("/tmp"), project_path=Path("/tmp")
        )

    def _build_index(self, provenance: dict[str, PolicyProvenance]) -> dict:
        contract = _make_contract(provenance)
        return self.pipeline._build_provenance_index(contract)

    def test_known_rule_path_populates_clause_kind(self):
        idx = self._build_index(
            {"imports.disallow.axios": _make_provenance("imports.disallow.axios")}
        )
        entry = idx["imports.disallow.axios"]
        assert entry.clause_kind == "forbidden_import"

    def test_layer_boundary_rule_path_populates_clause_kind(self):
        idx = self._build_index(
            {
                "architecture.layer_boundaries.0": _make_provenance(
                    "architecture.layer_boundaries.0"
                )
            }
        )
        entry = idx["architecture.layer_boundaries.0"]
        assert entry.clause_kind == "layer_boundary"

    def test_config_enforcement_rule_path_populates_clause_kind(self):
        idx = self._build_index(
            {
                "config_enforcement.python.mypy.strict": _make_provenance(
                    "config_enforcement.python.mypy.strict"
                )
            }
        )
        entry = idx["config_enforcement.python.mypy.strict"]
        assert entry.clause_kind == "config_invariant"

    def test_unknown_rule_path_leaves_clause_kind_none(self):
        idx = self._build_index({"unknown.rule": _make_provenance("unknown.rule")})
        entry = idx["unknown.rule"]
        assert entry.clause_kind is None

    def test_existing_fields_unchanged(self):
        rule_path = "imports.disallow.flask"
        prov = _make_provenance(rule_path)
        idx = self._build_index({rule_path: prov})
        entry = idx[rule_path]
        assert entry.rule == rule_path
        assert entry.source_adr_id == "ADR-001"
        assert entry.clause_id == prov.clause_id
        assert entry.artifact_refs == []


# ---------------------------------------------------------------------------
# Router clause-kind filtering tests
# ---------------------------------------------------------------------------


class _ForbiddenOnlyAdapter(BaseAdapter):
    """Test adapter that declares only forbidden_import clause kind."""

    @property
    def name(self) -> str:
        return "forbidden_only"

    @property
    def supported_policy_keys(self) -> list[str]:
        return ["imports"]

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    @property
    def config_targets(self) -> list[str]:
        return []

    @property
    def supported_clause_kinds(self) -> list[str]:
        return [ClauseKind.FORBIDDEN_IMPORT]

    def generate_fragments(self, constraints):
        return []


class _NoClauseKindAdapter(BaseAdapter):
    """Test adapter with empty supported_clause_kinds (backward-compatible)."""

    @property
    def name(self) -> str:
        return "no_clause_kind"

    @property
    def supported_policy_keys(self) -> list[str]:
        return ["imports"]

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    @property
    def config_targets(self) -> list[str]:
        return []

    def generate_fragments(self, constraints):
        return []


def _make_contract_with_prov(
    provenance: dict[str, PolicyProvenance],
) -> ConstraintsContract:
    return ConstraintsContract(
        metadata=ContractMetadata(hash="abc123", source_adrs=[], adr_directory="."),
        constraints=MergedConstraints(
            imports=ImportPolicy(disallow=["axios"], prefer=["fastapi"])
        ),
        provenance=provenance,
    )


class TestRouterClauseKindFiltering:
    def _make_prov(self, rule_path: str) -> PolicyProvenance:
        return PolicyProvenance(
            adr_id="ADR-001",
            adr_title="Test",
            rule_path=rule_path,
            effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            clause_id=PolicyProvenance.make_clause_id("ADR-001", rule_path),
        )

    def test_forbidden_only_adapter_receives_disallow_keys(self):
        prov = {
            "imports.disallow.axios": self._make_prov("imports.disallow.axios"),
            "imports.prefer.fastapi": self._make_prov("imports.prefer.fastapi"),
        }
        contract = _make_contract_with_prov(prov)
        router = PolicyRouter([_ForbiddenOnlyAdapter()])
        decisions, _ = router.route(contract, ["python"])

        assert len(decisions) == 1
        keys = decisions[0].policy_keys
        assert "imports.disallow.axios" in keys
        assert "imports.prefer.fastapi" not in keys

    def test_adapter_with_empty_clause_kinds_receives_all_keys(self):
        prov = {
            "imports.disallow.axios": self._make_prov("imports.disallow.axios"),
            "imports.prefer.fastapi": self._make_prov("imports.prefer.fastapi"),
        }
        contract = _make_contract_with_prov(prov)
        router = PolicyRouter([_NoClauseKindAdapter()])
        decisions, _ = router.route(contract, ["python"])

        assert len(decisions) == 1
        keys = decisions[0].policy_keys
        assert "imports.disallow.axios" in keys
        assert "imports.prefer.fastapi" in keys
