"""Unit and integration tests for the RTR task: Router + Adapter Registry.

Covers:
- BaseAdapter contract (capability declarations)
- ESLintAdapter and RuffAdapter capability declarations
- ConfigFragment produced by each adapter
- PolicyRouter routing logic (policy-key and stack matching)
- Unroutable policy key reporting
- Integration: Python-only project → only Ruff selected
- Integration: JS/TS-only project → only ESLint selected
- Integration: mixed project → both selected
- EnforcementPipeline uses router (stack override via detected_stack parameter)
"""

from datetime import date
from pathlib import Path

import pytest

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
)
from adr_kit.core.model import ImportPolicy, PythonPolicy
from adr_kit.enforcement.adapters.base import BaseAdapter, ConfigFragment
from adr_kit.enforcement.adapters.eslint import ESLintAdapter
from adr_kit.enforcement.adapters.ruff import RuffAdapter
from adr_kit.enforcement.detection.stack import StackDetector
from adr_kit.enforcement.router import PolicyRouter, RoutingDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract(
    *,
    disallow_imports: list[str] | None = None,
    prefer_imports: list[str] | None = None,
    python_disallow: list[str] | None = None,
    tmp_path: Path | None = None,
) -> ConstraintsContract:
    constraints = MergedConstraints(
        imports=(
            ImportPolicy(
                disallow=disallow_imports or [],
                prefer=prefer_imports or [],
            )
            if (disallow_imports or prefer_imports)
            else None
        ),
        python=(
            PythonPolicy(disallow_imports=python_disallow) if python_disallow else None
        ),
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
# BaseAdapter contract tests
# ---------------------------------------------------------------------------


class TestBaseAdapterContract:
    """Verify the ABC prevents instantiation and subclasses must implement all abstract methods."""

    def test_cannot_instantiate_base_adapter(self):
        with pytest.raises(TypeError):
            BaseAdapter()  # type: ignore[abstract]

    def test_eslint_adapter_is_base_adapter(self):
        assert isinstance(ESLintAdapter(), BaseAdapter)

    def test_ruff_adapter_is_base_adapter(self):
        assert isinstance(RuffAdapter(), BaseAdapter)

    def test_default_supported_clause_kinds_is_list(self):
        """Adapters not overriding supported_clause_kinds get an empty list."""

        class MinimalAdapter(BaseAdapter):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def supported_policy_keys(self) -> list[str]:
                return ["imports"]

            @property
            def supported_languages(self) -> list[str]:
                return ["javascript"]

            @property
            def config_targets(self) -> list[str]:
                return [".minimal.json"]

            def generate_fragments(self, constraints):
                return []

        adapter = MinimalAdapter()
        assert adapter.supported_clause_kinds == []
        assert adapter.output_modes == ["native_config"]
        assert adapter.supported_stages == ["ci"]


# ---------------------------------------------------------------------------
# ESLintAdapter capability declarations
# ---------------------------------------------------------------------------


class TestESLintAdapterCapabilities:
    def setup_method(self):
        self.adapter = ESLintAdapter()

    def test_name(self):
        assert self.adapter.name == "eslint"

    def test_supported_policy_keys(self):
        assert "imports" in self.adapter.supported_policy_keys

    def test_supported_languages(self):
        assert "javascript" in self.adapter.supported_languages
        assert "typescript" in self.adapter.supported_languages

    def test_config_targets(self):
        assert any("eslintrc" in t for t in self.adapter.config_targets)

    def test_output_modes(self):
        assert "native_config" in self.adapter.output_modes

    def test_supported_stages(self):
        stages = self.adapter.supported_stages
        assert isinstance(stages, list)
        assert len(stages) > 0

    def test_generate_fragments_with_disallow_returns_json_fragment(self):
        constraints = MergedConstraints(imports=ImportPolicy(disallow=["axios"]))
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        frag = fragments[0]
        assert isinstance(frag, ConfigFragment)
        assert frag.adapter == "eslint"
        assert frag.fragment_type == "json_file"
        assert "axios" in frag.content

    def test_generate_fragments_includes_policy_keys(self):
        constraints = MergedConstraints(imports=ImportPolicy(disallow=["moment"]))
        fragments = self.adapter.generate_fragments(constraints)
        assert any("moment" in k for k in fragments[0].policy_keys)

    def test_generate_fragments_empty_constraints(self):
        constraints = MergedConstraints()
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        assert fragments[0].policy_keys == []


# ---------------------------------------------------------------------------
# RuffAdapter capability declarations
# ---------------------------------------------------------------------------


class TestRuffAdapterCapabilities:
    def setup_method(self):
        self.adapter = RuffAdapter()

    def test_name(self):
        assert self.adapter.name == "ruff"

    def test_supported_policy_keys(self):
        assert "python" in self.adapter.supported_policy_keys
        assert "imports" in self.adapter.supported_policy_keys

    def test_supported_languages(self):
        assert "python" in self.adapter.supported_languages

    def test_config_targets(self):
        assert any("ruff" in t for t in self.adapter.config_targets)

    def test_generate_fragments_with_python_disallow(self):
        constraints = MergedConstraints(
            python=PythonPolicy(disallow_imports=["requests"])
        )
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        frag = fragments[0]
        assert frag.adapter == "ruff"
        assert frag.fragment_type == "toml_file"
        assert "requests" in frag.content

    def test_generate_fragments_includes_policy_keys(self):
        constraints = MergedConstraints(python=PythonPolicy(disallow_imports=["httpx"]))
        fragments = self.adapter.generate_fragments(constraints)
        assert any("httpx" in k for k in fragments[0].policy_keys)

    def test_generate_fragments_empty_constraints(self):
        constraints = MergedConstraints()
        fragments = self.adapter.generate_fragments(constraints)
        assert len(fragments) == 1
        assert fragments[0].policy_keys == []


# ---------------------------------------------------------------------------
# StackDetector
# ---------------------------------------------------------------------------


class TestStackDetector:
    def test_detects_python(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        detector = StackDetector(tmp_path)
        assert "python" in detector.detect()

    def test_detects_javascript(self, tmp_path):
        (tmp_path / "index.js").write_text("console.log('hi')")
        detector = StackDetector(tmp_path)
        assert "javascript" in detector.detect()

    def test_detects_typescript(self, tmp_path):
        (tmp_path / "app.ts").write_text("const x: number = 1;")
        detector = StackDetector(tmp_path)
        assert "typescript" in detector.detect()

    def test_empty_dir_returns_empty_list(self, tmp_path):
        detector = StackDetector(tmp_path)
        assert detector.detect() == []

    def test_mixed_project_detects_multiple(self, tmp_path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "app.ts").write_text("")
        detector = StackDetector(tmp_path)
        result = detector.detect()
        assert "python" in result
        assert "typescript" in result

    def test_result_is_sorted(self, tmp_path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "app.ts").write_text("")
        detector = StackDetector(tmp_path)
        result = detector.detect()
        assert result == sorted(result)

    def test_skips_node_modules(self, tmp_path):
        node_mod = tmp_path / "node_modules"
        node_mod.mkdir()
        (node_mod / "lib.js").write_text("")
        detector = StackDetector(tmp_path)
        # Only js from node_modules — should be ignored
        assert "javascript" not in detector.detect()

    def test_skips_venv(self, tmp_path):
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "site.py").write_text("")
        detector = StackDetector(tmp_path)
        assert "python" not in detector.detect()


# ---------------------------------------------------------------------------
# PolicyRouter unit tests
# ---------------------------------------------------------------------------


class TestPolicyRouter:
    def setup_method(self):
        self.eslint = ESLintAdapter()
        self.ruff = RuffAdapter()
        self.router = PolicyRouter([self.eslint, self.ruff])

    def test_no_constraints_no_decisions(self, tmp_path):
        contract = _make_contract(tmp_path=tmp_path)
        decisions, unroutable = self.router.route(contract, ["python", "javascript"])
        assert decisions == []
        assert unroutable == []

    def test_js_stack_routes_eslint_for_imports(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        decisions, unroutable = self.router.route(contract, ["javascript"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "eslint" in adapter_names
        assert "ruff" not in adapter_names

    def test_python_stack_routes_ruff_for_imports(self, tmp_path):
        contract = _make_contract(disallow_imports=["requests"], tmp_path=tmp_path)
        decisions, unroutable = self.router.route(contract, ["python"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "ruff" in adapter_names
        assert "eslint" not in adapter_names

    def test_python_stack_routes_ruff_for_python_policy(self, tmp_path):
        contract = _make_contract(python_disallow=["httpx"], tmp_path=tmp_path)
        decisions, unroutable = self.router.route(contract, ["python"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "ruff" in adapter_names

    def test_mixed_stack_routes_both_for_imports(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        decisions, unroutable = self.router.route(contract, ["python", "javascript"])
        adapter_names = [d.adapter.name for d in decisions]
        assert "eslint" in adapter_names
        assert "ruff" in adapter_names

    def test_routing_decision_has_reflected_capabilities(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        decisions, _ = self.router.route(contract, ["javascript"])
        assert len(decisions) == 1
        decision = decisions[0]
        assert isinstance(decision, RoutingDecision)
        assert decision.output_modes == self.eslint.output_modes
        assert decision.supported_stages == self.eslint.supported_stages

    def test_unroutable_key_reported(self, tmp_path):
        """Policy keys with no matching adapter are returned as unroutable."""
        from adr_kit.core.model import PatternPolicy, PatternRule

        constraints = MergedConstraints(
            patterns=PatternPolicy(
                patterns={
                    "no-god-class": PatternRule(
                        description="No god class",
                        rule=r"class \w+",
                    )
                }
            )
        )
        metadata = ContractMetadata(
            hash="test", source_adrs=[], adr_directory=str(tmp_path)
        )
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=constraints,
            provenance={},
            approved_adrs=[],
        )
        decisions, unroutable = self.router.route(contract, ["python"])
        assert "patterns" in unroutable

    def test_no_stack_match_skips_adapter(self, tmp_path):
        """ESLint not selected when detected stack has no JS/TS."""
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        decisions, _ = self.router.route(contract, ["python"])  # Python-only
        adapter_names = [d.adapter.name for d in decisions]
        assert "eslint" not in adapter_names


# ---------------------------------------------------------------------------
# Integration: pipeline uses router (stack injected via detected_stack param)
# ---------------------------------------------------------------------------


class TestPipelineUsesRouter:
    def _make_pipeline(self, tmp_path):
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        return EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)

    def test_python_only_stack_runs_ruff_not_eslint(self, tmp_path):
        contract = _make_contract(disallow_imports=["requests"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        applied = {f.adapter for f in result.fragments_applied}
        skipped = {s.adapter for s in result.skipped_adapters}
        assert "ruff" in applied
        assert "eslint" not in applied
        assert "eslint" in skipped

    def test_js_only_stack_runs_eslint_not_ruff(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["javascript"])

        applied = {f.adapter for f in result.fragments_applied}
        skipped = {s.adapter for s in result.skipped_adapters}
        assert "eslint" in applied
        assert "ruff" not in applied
        assert "ruff" in skipped

    def test_mixed_stack_runs_both(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(
            contract=contract, detected_stack=["python", "javascript"]
        )

        applied = {f.adapter for f in result.fragments_applied}
        assert "eslint" in applied
        assert "ruff" in applied

    def test_no_constraints_skips_both_adapters(self, tmp_path):
        contract = _make_contract(tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(
            contract=contract, detected_stack=["python", "javascript"]
        )

        assert len(result.fragments_applied) == 0
        skipped = {s.adapter for s in result.skipped_adapters}
        assert "eslint" in skipped
        assert "ruff" in skipped

    def test_auto_stack_detection_used_when_no_override(self, tmp_path):
        """Pipeline auto-detects stack when detected_stack is not provided."""
        (tmp_path / "main.py").write_text("import requests")
        contract = _make_contract(python_disallow=["requests"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        result = pipeline.compile(contract=contract)  # no detected_stack override

        applied = {f.adapter for f in result.fragments_applied}
        assert "ruff" in applied

    def test_ruff_file_written_to_disk(self, tmp_path):
        contract = _make_contract(python_disallow=["httpx"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        pipeline.compile(contract=contract, detected_stack=["python"])

        assert (tmp_path / ".ruff-adr.toml").exists()

    def test_eslint_file_written_to_disk(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        pipeline.compile(contract=contract, detected_stack=["javascript"])

        assert (tmp_path / ".eslintrc.adrs.json").exists()

    def test_pipeline_still_idempotent_with_router(self, tmp_path):
        contract = _make_contract(disallow_imports=["axios"], tmp_path=tmp_path)
        pipeline = self._make_pipeline(tmp_path)
        r1 = pipeline.compile(contract=contract, detected_stack=["javascript"])
        r2 = pipeline.compile(contract=contract, detected_stack=["javascript"])
        assert r1.idempotency_hash == r2.idempotency_hash
