"""Unit and integration tests for the ADP task: New Config Adapters.

Covers:
- MypyAdapter capability declarations and fragment generation
- TsconfigAdapter capability declarations and fragment generation
- ImportLinterAdapter capability declarations and fragment generation
- INI conflict detection
- Pipeline integration: config_enforcement → mypy/tsconfig config written
- Pipeline integration: architecture boundaries → import-linter config written
- Router routing for new adapters (stack + policy key matching)
"""

import configparser
import json
from pathlib import Path

import pytest

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
)
from adr_kit.core.model import (
    ArchitecturePolicy,
    ConfigEnforcementPolicy,
    ImportPolicy,
    LayerBoundaryRule,
    PythonConfig,
    TypeScriptConfig,
)
from adr_kit.enforcement.adapters.base import BaseAdapter, ConfigFragment
from adr_kit.enforcement.adapters.eslint import ESLintAdapter
from adr_kit.enforcement.adapters.import_linter import (
    ImportLinterAdapter,
    generate_import_linter_config_from_contract,
)
from adr_kit.enforcement.adapters.mypy import (
    MypyAdapter,
    generate_mypy_config_from_contract,
)
from adr_kit.enforcement.adapters.ruff import RuffAdapter
from adr_kit.enforcement.adapters.tsconfig import (
    TsconfigAdapter,
    generate_tsconfig_from_contract,
)
from adr_kit.enforcement.clause_kinds import ClauseKind
from adr_kit.enforcement.router import PolicyRouter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract(
    *,
    mypy: dict | None = None,
    tsconfig: dict | None = None,
    layer_boundaries: list[LayerBoundaryRule] | None = None,
    disallow_imports: list[str] | None = None,
    tmp_path: Path | None = None,
) -> ConstraintsContract:
    config_enforcement = None
    if mypy or tsconfig:
        config_enforcement = ConfigEnforcementPolicy(
            python=PythonConfig(mypy=mypy) if mypy else None,
            typescript=TypeScriptConfig(tsconfig=tsconfig) if tsconfig else None,
        )

    architecture = None
    if layer_boundaries:
        architecture = ArchitecturePolicy(layer_boundaries=layer_boundaries)

    imports = None
    if disallow_imports:
        imports = ImportPolicy(disallow=disallow_imports)

    constraints = MergedConstraints(
        imports=imports,
        config_enforcement=config_enforcement,
        architecture=architecture,
    )
    metadata = ContractMetadata(
        hash="test",
        source_adrs=[],
        adr_directory=str(tmp_path or "."),
    )
    return ConstraintsContract(
        metadata=metadata,
        constraints=constraints,
        provenance={},
        approved_adrs=[],
    )


# ---------------------------------------------------------------------------
# MypyAdapter capability declarations
# ---------------------------------------------------------------------------


class TestMypyAdapterCapabilities:
    def setup_method(self):
        self.adapter = MypyAdapter()

    def test_is_base_adapter(self):
        assert isinstance(self.adapter, BaseAdapter)

    def test_name(self):
        assert self.adapter.name == "mypy"

    def test_supported_policy_keys(self):
        assert "config_enforcement" in self.adapter.supported_policy_keys

    def test_supported_languages(self):
        assert "python" in self.adapter.supported_languages

    def test_config_targets(self):
        assert ".mypy-adr.ini" in self.adapter.config_targets

    def test_output_modes(self):
        assert "native_config" in self.adapter.output_modes

    def test_supported_stages(self):
        assert len(self.adapter.supported_stages) > 0


class TestMypyAdapterFragments:
    def setup_method(self):
        self.adapter = MypyAdapter()

    def test_generates_ini_fragment(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                python=PythonConfig(
                    mypy={"strict": True, "disallow_untyped_defs": True}
                )
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        frag = fragments[0]
        assert isinstance(frag, ConfigFragment)
        assert frag.adapter == "mypy"
        assert frag.fragment_type == "ini_file"
        assert frag.target_file == ".mypy-adr.ini"

    def test_fragment_contains_settings(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                python=PythonConfig(mypy={"strict": True})
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert "strict" in fragments[0].content
        assert "True" in fragments[0].content

    def test_fragment_includes_policy_keys(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                python=PythonConfig(
                    mypy={"strict": True, "disallow_untyped_defs": True}
                )
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        keys = fragments[0].policy_keys
        assert "config_enforcement.python.mypy.strict" in keys
        assert "config_enforcement.python.mypy.disallow_untyped_defs" in keys

    def test_empty_constraints_returns_no_fragments(self):
        constraints = MergedConstraints()
        fragments = self.adapter.generate_fragments(constraints)
        assert fragments == []

    def test_empty_mypy_dict_returns_no_fragments(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(python=PythonConfig(mypy={}))
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert fragments == []


class TestMypyConfigGeneration:
    def test_generates_valid_ini(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                python=PythonConfig(
                    mypy={"strict": True, "disallow_untyped_defs": True}
                )
            )
        )
        ini_str = generate_mypy_config_from_contract(constraints)
        config = configparser.ConfigParser()
        config.read_string(ini_str)
        assert config.has_section("mypy")
        assert config.get("mypy", "strict") == "True"
        assert config.get("mypy", "disallow_untyped_defs") == "True"

    def test_empty_constraints_returns_empty_string(self):
        constraints = MergedConstraints()
        assert generate_mypy_config_from_contract(constraints) == ""

    def test_has_header_comment(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                python=PythonConfig(mypy={"strict": True})
            )
        )
        ini_str = generate_mypy_config_from_contract(constraints)
        assert "ADR Kit" in ini_str
        assert "Do not edit manually" in ini_str


# ---------------------------------------------------------------------------
# TsconfigAdapter capability declarations
# ---------------------------------------------------------------------------


class TestTsconfigAdapterCapabilities:
    def setup_method(self):
        self.adapter = TsconfigAdapter()

    def test_is_base_adapter(self):
        assert isinstance(self.adapter, BaseAdapter)

    def test_name(self):
        assert self.adapter.name == "tsconfig"

    def test_supported_policy_keys(self):
        assert "config_enforcement" in self.adapter.supported_policy_keys

    def test_supported_languages(self):
        assert "typescript" in self.adapter.supported_languages

    def test_config_targets(self):
        assert "tsconfig.adr.json" in self.adapter.config_targets


class TestTsconfigAdapterFragments:
    def setup_method(self):
        self.adapter = TsconfigAdapter()

    def test_generates_json_fragment(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(
                    tsconfig={"strict": True, "noImplicitAny": True}
                )
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        frag = fragments[0]
        assert frag.adapter == "tsconfig"
        assert frag.fragment_type == "json_file"
        assert frag.target_file == "tsconfig.adr.json"

    def test_fragment_contains_compiler_options(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(tsconfig={"strict": True})
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        config = json.loads(fragments[0].content)
        assert config["compilerOptions"]["strict"] is True

    def test_fragment_includes_policy_keys(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(
                    tsconfig={"strict": True, "noImplicitAny": True}
                )
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        keys = fragments[0].policy_keys
        assert "config_enforcement.typescript.tsconfig.strict" in keys
        assert "config_enforcement.typescript.tsconfig.noImplicitAny" in keys

    def test_empty_constraints_returns_no_fragments(self):
        constraints = MergedConstraints()
        fragments = self.adapter.generate_fragments(constraints)
        assert fragments == []

    def test_empty_tsconfig_dict_returns_no_fragments(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(tsconfig={})
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert fragments == []


class TestTsconfigGeneration:
    def test_generates_valid_json(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(
                    tsconfig={"strict": True, "noImplicitAny": True}
                )
            )
        )
        json_str = generate_tsconfig_from_contract(constraints)
        config = json.loads(json_str)
        assert "compilerOptions" in config
        assert config["compilerOptions"]["strict"] is True
        assert config["compilerOptions"]["noImplicitAny"] is True

    def test_has_schema_reference(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(tsconfig={"strict": True})
            )
        )
        json_str = generate_tsconfig_from_contract(constraints)
        config = json.loads(json_str)
        assert "$schema" in config

    def test_has_metadata(self):
        constraints = MergedConstraints(
            config_enforcement=ConfigEnforcementPolicy(
                typescript=TypeScriptConfig(tsconfig={"strict": True})
            )
        )
        json_str = generate_tsconfig_from_contract(constraints)
        config = json.loads(json_str)
        assert config["__adr_metadata"]["generated_by"] == "ADR Kit"

    def test_empty_constraints_returns_empty_string(self):
        constraints = MergedConstraints()
        assert generate_tsconfig_from_contract(constraints) == ""


# ---------------------------------------------------------------------------
# ImportLinterAdapter capability declarations
# ---------------------------------------------------------------------------


class TestImportLinterAdapterCapabilities:
    def setup_method(self):
        self.adapter = ImportLinterAdapter()

    def test_is_base_adapter(self):
        assert isinstance(self.adapter, BaseAdapter)

    def test_name(self):
        assert self.adapter.name == "import_linter"

    def test_supported_policy_keys(self):
        assert "architecture" in self.adapter.supported_policy_keys

    def test_supported_languages(self):
        assert "python" in self.adapter.supported_languages

    def test_config_targets(self):
        assert ".importlinter-adr" in self.adapter.config_targets


class TestImportLinterAdapterFragments:
    def setup_method(self):
        self.adapter = ImportLinterAdapter()

    def test_generates_ini_fragment(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(rule="ui -> database", action="block")
                ]
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        frag = fragments[0]
        assert frag.adapter == "import_linter"
        assert frag.fragment_type == "ini_file"
        assert frag.target_file == ".importlinter-adr"

    def test_fragment_contains_boundary_rule(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(rule="ui -> database", action="block")
                ]
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        content = fragments[0].content
        assert "ui" in content
        assert "database" in content
        assert "forbidden" in content

    def test_fragment_includes_policy_keys(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(rule="ui -> database", action="block")
                ]
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        keys = fragments[0].policy_keys
        assert "architecture.layer_boundaries.ui -> database" in keys

    def test_multiple_boundaries(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(rule="ui -> database", action="block"),
                    LayerBoundaryRule(
                        rule="domain -> infrastructure",
                        action="block",
                        message="Domain must not depend on infrastructure",
                    ),
                ]
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        content = fragments[0].content
        config = configparser.ConfigParser()
        config.read_string(content)
        # Should have importlinter section + 2 contract sections
        contract_sections = [
            s for s in config.sections() if s.startswith("importlinter:contract:")
        ]
        assert len(contract_sections) == 2

    def test_custom_message_used_as_description(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(
                        rule="ui -> database",
                        action="block",
                        message="Keep UI decoupled from DB",
                    )
                ]
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert "Keep UI decoupled from DB" in fragments[0].content

    def test_empty_constraints_returns_no_fragments(self):
        constraints = MergedConstraints()
        fragments = self.adapter.generate_fragments(constraints)
        assert fragments == []

    def test_invalid_rule_format_skipped(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(rule="invalid rule format", action="block")
                ]
            )
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert fragments == []


class TestImportLinterConfigGeneration:
    def test_generates_valid_ini(self):
        constraints = MergedConstraints(
            architecture=ArchitecturePolicy(
                layer_boundaries=[
                    LayerBoundaryRule(rule="ui -> database", action="block")
                ]
            )
        )
        ini_str = generate_import_linter_config_from_contract(constraints)
        config = configparser.ConfigParser()
        config.read_string(ini_str)
        assert config.has_section("importlinter")
        assert config.get("importlinter", "root_packages") == "src"

    def test_empty_constraints_returns_empty_string(self):
        constraints = MergedConstraints()
        assert generate_import_linter_config_from_contract(constraints) == ""


# ---------------------------------------------------------------------------
# INI conflict detection
# ---------------------------------------------------------------------------


class TestINIConflictDetection:
    def test_no_conflict_when_no_existing_file(self, tmp_path):
        from adr_kit.enforcement.conflict import ConflictDetector

        fragment = ConfigFragment(
            adapter="mypy",
            target_file=".mypy-adr.ini",
            content="[mypy]\nstrict = True\n",
            fragment_type="ini_file",
        )
        detector = ConflictDetector()
        conflicts = detector.detect_config_conflicts([fragment], tmp_path)
        assert conflicts == []

    def test_no_conflict_when_values_match(self, tmp_path):
        from adr_kit.enforcement.conflict import ConflictDetector

        existing = tmp_path / ".mypy-adr.ini"
        existing.write_text("[mypy]\nstrict = True\n")

        fragment = ConfigFragment(
            adapter="mypy",
            target_file=".mypy-adr.ini",
            content="[mypy]\nstrict = True\n",
            fragment_type="ini_file",
        )
        detector = ConflictDetector()
        conflicts = detector.detect_config_conflicts([fragment], tmp_path)
        assert conflicts == []

    def test_conflict_when_values_differ(self, tmp_path):
        from adr_kit.enforcement.conflict import ConflictDetector

        existing = tmp_path / ".mypy-adr.ini"
        existing.write_text("[mypy]\nstrict = False\n")

        fragment = ConfigFragment(
            adapter="mypy",
            target_file=".mypy-adr.ini",
            content="[mypy]\nstrict = True\n",
            fragment_type="ini_file",
        )
        detector = ConflictDetector()
        conflicts = detector.detect_config_conflicts([fragment], tmp_path)
        assert len(conflicts) == 1
        assert "strict" in conflicts[0].description

    def test_no_conflict_for_new_keys(self, tmp_path):
        from adr_kit.enforcement.conflict import ConflictDetector

        existing = tmp_path / ".mypy-adr.ini"
        existing.write_text("[mypy]\nstrict = True\n")

        fragment = ConfigFragment(
            adapter="mypy",
            target_file=".mypy-adr.ini",
            content="[mypy]\nstrict = True\ndisallow_untyped_defs = True\n",
            fragment_type="ini_file",
        )
        detector = ConflictDetector()
        conflicts = detector.detect_config_conflicts([fragment], tmp_path)
        assert conflicts == []


# ---------------------------------------------------------------------------
# Router integration: new adapters selected by policy key + stack
# ---------------------------------------------------------------------------


class TestRouterWithNewAdapters:
    def setup_method(self):
        from adr_kit.enforcement.adapters.eslint import ESLintAdapter
        from adr_kit.enforcement.adapters.ruff import RuffAdapter

        self.router = PolicyRouter(
            [
                ESLintAdapter(),
                RuffAdapter(),
                MypyAdapter(),
                TsconfigAdapter(),
                ImportLinterAdapter(),
            ]
        )

    def test_python_config_enforcement_routes_mypy(self, tmp_path):
        contract = _make_contract(mypy={"strict": True}, tmp_path=tmp_path)
        decisions, _ = self.router.route(contract, ["python"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "mypy" in adapter_names

    def test_typescript_config_enforcement_routes_tsconfig(self, tmp_path):
        contract = _make_contract(tsconfig={"strict": True}, tmp_path=tmp_path)
        decisions, _ = self.router.route(contract, ["typescript"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "tsconfig" in adapter_names

    def test_architecture_boundaries_routes_import_linter(self, tmp_path):
        contract = _make_contract(
            layer_boundaries=[LayerBoundaryRule(rule="ui -> database", action="block")],
            tmp_path=tmp_path,
        )
        decisions, _ = self.router.route(contract, ["python"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "import_linter" in adapter_names

    def test_mypy_not_routed_for_js_stack(self, tmp_path):
        contract = _make_contract(mypy={"strict": True}, tmp_path=tmp_path)
        decisions, _ = self.router.route(contract, ["javascript"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "mypy" not in adapter_names

    def test_tsconfig_not_routed_for_python_stack(self, tmp_path):
        contract = _make_contract(tsconfig={"strict": True}, tmp_path=tmp_path)
        decisions, _ = self.router.route(contract, ["python"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "tsconfig" not in adapter_names

    def test_import_linter_not_routed_for_js_stack(self, tmp_path):
        contract = _make_contract(
            layer_boundaries=[LayerBoundaryRule(rule="ui -> database", action="block")],
            tmp_path=tmp_path,
        )
        decisions, _ = self.router.route(contract, ["javascript"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "import_linter" not in adapter_names


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestPipelineWithNewAdapters:
    def _make_pipeline(self, tmp_path):
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        return EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)

    def test_mypy_config_written_to_disk(self, tmp_path):
        contract = _make_contract(
            mypy={"strict": True, "disallow_untyped_defs": True},
            tmp_path=tmp_path,
        )
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        applied = {f.adapter for f in result.fragments_applied}
        assert "mypy" in applied
        assert (tmp_path / ".mypy-adr.ini").exists()

        # Verify content
        content = (tmp_path / ".mypy-adr.ini").read_text()
        assert "strict" in content

    def test_tsconfig_written_to_disk(self, tmp_path):
        contract = _make_contract(
            tsconfig={"strict": True, "noImplicitAny": True},
            tmp_path=tmp_path,
        )
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["typescript"])

        applied = {f.adapter for f in result.fragments_applied}
        assert "tsconfig" in applied
        assert (tmp_path / "tsconfig.adr.json").exists()

        # Verify content
        config = json.loads((tmp_path / "tsconfig.adr.json").read_text())
        assert config["compilerOptions"]["strict"] is True

    def test_import_linter_config_written_to_disk(self, tmp_path):
        contract = _make_contract(
            layer_boundaries=[LayerBoundaryRule(rule="ui -> database", action="block")],
            tmp_path=tmp_path,
        )
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        applied = {f.adapter for f in result.fragments_applied}
        assert "import_linter" in applied
        assert (tmp_path / ".importlinter-adr").exists()

    def test_mixed_stack_routes_correct_adapters(self, tmp_path):
        """Python + TypeScript stack with config_enforcement routes both mypy and tsconfig."""
        contract = _make_contract(
            mypy={"strict": True},
            tsconfig={"strict": True},
            tmp_path=tmp_path,
        )
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(
            contract=contract, detected_stack=["python", "typescript"]
        )

        applied = {f.adapter for f in result.fragments_applied}
        assert "mypy" in applied
        assert "tsconfig" in applied

    def test_pipeline_idempotent_with_new_adapters(self, tmp_path):
        contract = _make_contract(
            mypy={"strict": True},
            layer_boundaries=[LayerBoundaryRule(rule="ui -> database", action="block")],
            tmp_path=tmp_path,
        )
        pipeline = self._make_pipeline(tmp_path)
        r1 = pipeline.compile(contract=contract, detected_stack=["python"])
        r2 = pipeline.compile(contract=contract, detected_stack=["python"])
        assert r1.idempotency_hash == r2.idempotency_hash

    def test_no_config_enforcement_skips_new_adapters(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        applied = {f.adapter for f in result.fragments_applied}
        assert "mypy" not in applied
        assert "tsconfig" not in applied
        assert "import_linter" not in applied


# ---------------------------------------------------------------------------
# ENF-CLA: Adapter supported_clause_kinds canonical vocabulary tests
# ---------------------------------------------------------------------------


class TestMypyAdapterClauseKinds:
    def setup_method(self):
        self.adapter = MypyAdapter()

    def test_returns_config_invariant(self):
        assert ClauseKind.CONFIG_INVARIANT in self.adapter.supported_clause_kinds

    def test_all_values_are_clause_kind_instances(self):
        for v in self.adapter.supported_clause_kinds:
            assert isinstance(v, ClauseKind)

    def test_no_stale_config_enforcement_string(self):
        assert "config_enforcement" not in self.adapter.supported_clause_kinds


class TestTsconfigAdapterClauseKinds:
    def setup_method(self):
        self.adapter = TsconfigAdapter()

    def test_returns_config_invariant(self):
        assert ClauseKind.CONFIG_INVARIANT in self.adapter.supported_clause_kinds

    def test_all_values_are_clause_kind_instances(self):
        for v in self.adapter.supported_clause_kinds:
            assert isinstance(v, ClauseKind)

    def test_no_stale_config_enforcement_string(self):
        assert "config_enforcement" not in self.adapter.supported_clause_kinds


class TestImportLinterAdapterClauseKinds:
    def setup_method(self):
        self.adapter = ImportLinterAdapter()

    def test_returns_layer_boundary(self):
        assert ClauseKind.LAYER_BOUNDARY in self.adapter.supported_clause_kinds

    def test_all_values_are_clause_kind_instances(self):
        for v in self.adapter.supported_clause_kinds:
            assert isinstance(v, ClauseKind)


class TestESLintAdapterClauseKinds:
    def setup_method(self):
        self.adapter = ESLintAdapter()

    def test_returns_forbidden_import(self):
        assert ClauseKind.FORBIDDEN_IMPORT in self.adapter.supported_clause_kinds

    def test_returns_allowed_import_surface(self):
        assert ClauseKind.ALLOWED_IMPORT_SURFACE in self.adapter.supported_clause_kinds

    def test_no_stale_preferred_import_string(self):
        assert "preferred_import" not in self.adapter.supported_clause_kinds

    def test_all_values_are_clause_kind_instances(self):
        for v in self.adapter.supported_clause_kinds:
            assert isinstance(v, ClauseKind)


class TestRuffAdapterClauseKinds:
    def setup_method(self):
        self.adapter = RuffAdapter()

    def test_returns_forbidden_import(self):
        assert ClauseKind.FORBIDDEN_IMPORT in self.adapter.supported_clause_kinds

    def test_all_values_are_clause_kind_instances(self):
        for v in self.adapter.supported_clause_kinds:
            assert isinstance(v, ClauseKind)


# ---------------------------------------------------------------------------
# ENF-CLA: Creation workflow enforcement metadata tests
# ---------------------------------------------------------------------------


class TestEnforcementMetadataAllAdapters:
    """Verify _build_enforcement_metadata includes all 5 adapters with clause_kinds."""

    def setup_method(self):
        from pathlib import Path
        from unittest.mock import MagicMock

        # CreationWorkflow needs an adr_dir; use MagicMock to avoid filesystem setup
        from adr_kit.decision.workflows.creation import CreationWorkflow

        self.workflow = CreationWorkflow.__new__(CreationWorkflow)

    def _get_metadata(self):
        return self.workflow._build_enforcement_metadata()

    def test_all_five_adapters_present(self):
        meta = self._get_metadata()
        adapters = meta["adapters"]
        assert "eslint" in adapters
        assert "ruff" in adapters
        assert "mypy" in adapters
        assert "tsconfig" in adapters
        assert "import_linter" in adapters

    def test_each_adapter_has_supported_clause_kinds_key(self):
        meta = self._get_metadata()
        for name, details in meta["adapters"].items():
            assert (
                "supported_clause_kinds" in details
            ), f"{name} missing supported_clause_kinds"

    def test_mypy_adapter_reports_config_invariant(self):
        meta = self._get_metadata()
        assert "config_invariant" in meta["adapters"]["mypy"]["supported_clause_kinds"]

    def test_eslint_adapter_reports_forbidden_import(self):
        meta = self._get_metadata()
        assert (
            "forbidden_import" in meta["adapters"]["eslint"]["supported_clause_kinds"]
        )

    def test_policy_enforcement_paths_covers_all_known_keys(self):
        meta = self._get_metadata()
        paths = meta["policy_enforcement_paths"]
        for key in [
            "imports",
            "python",
            "patterns",
            "architecture",
            "config_enforcement",
        ]:
            assert key in paths
