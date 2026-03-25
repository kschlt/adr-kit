"""Unit tests for the canonical enforcement pipeline (CPL task).

Covers:
- EnforcementResult model and idempotency hash
- ESLint/Ruff contract-driven adapter functions
- PolicyProvenance clause_id generation
- Topological sort in PolicyMerger
"""

import hashlib
from datetime import date, datetime, timezone

import pytest

from adr_kit.contract.models import MergedConstraints, PolicyProvenance
from adr_kit.enforcement.pipeline import (
    AppliedFragment,
    EnforcementConflict,
    EnforcementResult,
    ProvenanceEntry,
    SkippedAdapter,
)

# ---------------------------------------------------------------------------
# PolicyProvenance clause_id tests
# ---------------------------------------------------------------------------


class TestClauseIdGeneration:
    def test_clause_id_is_12_chars(self):
        cid = PolicyProvenance.make_clause_id("ADR-0001", "imports.disallow.axios")
        assert len(cid) == 12

    def test_clause_id_is_stable(self):
        """Same inputs always produce the same clause_id."""
        cid1 = PolicyProvenance.make_clause_id("ADR-0001", "imports.disallow.axios")
        cid2 = PolicyProvenance.make_clause_id("ADR-0001", "imports.disallow.axios")
        assert cid1 == cid2

    def test_clause_id_differs_by_adr(self):
        cid1 = PolicyProvenance.make_clause_id("ADR-0001", "imports.disallow.axios")
        cid2 = PolicyProvenance.make_clause_id("ADR-0002", "imports.disallow.axios")
        assert cid1 != cid2

    def test_clause_id_differs_by_rule_path(self):
        cid1 = PolicyProvenance.make_clause_id("ADR-0001", "imports.disallow.axios")
        cid2 = PolicyProvenance.make_clause_id("ADR-0001", "imports.disallow.moment")
        assert cid1 != cid2

    def test_provenance_has_clause_id_via_merger(self):
        """Merger populates clause_id on every provenance entry."""
        from adr_kit.contract.merger import PolicyMerger
        from adr_kit.core.model import (
            ADR,
            ADRFrontMatter,
            ADRStatus,
            ImportPolicy,
            PolicyModel,
        )

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use React Query",
            status=ADRStatus.ACCEPTED,
            date=date(2024, 1, 1),
            deciders=["team"],
            tags=["frontend"],
            policy=PolicyModel(
                imports=ImportPolicy(disallow=["axios"], prefer=["react-query"])
            ),
        )
        adr = ADR(front_matter=front_matter, content="## Decision\nUse it.")

        merger = PolicyMerger()
        result = merger.merge_policies([adr])

        for prov in result.provenance.values():
            assert len(prov.clause_id) == 12
            assert prov.clause_id != ""


# ---------------------------------------------------------------------------
# Topological sort tests
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def _make_adr(self, id_: str, date_: date, supersedes: list[str] | None = None):
        from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus

        return ADR(
            front_matter=ADRFrontMatter(
                id=id_,
                title=f"ADR {id_}",
                status=ADRStatus.ACCEPTED,
                date=date_,
                deciders=["team"],
                supersedes=supersedes,
            ),
            content="",
        )

    def test_no_supersession_falls_back_to_date_sort(self):
        from adr_kit.contract.merger import PolicyMerger

        merger = PolicyMerger()
        adrs = [
            self._make_adr("ADR-0003", date(2024, 3, 1)),
            self._make_adr("ADR-0001", date(2024, 1, 1)),
            self._make_adr("ADR-0002", date(2024, 2, 1)),
        ]
        sorted_adrs = merger._topological_sort(adrs)
        ids = [a.front_matter.id for a in sorted_adrs]
        assert ids == ["ADR-0001", "ADR-0002", "ADR-0003"]

    def test_linear_supersession_chain(self):
        """ADR-002 supersedes ADR-001 → ADR-001 must come first."""
        from adr_kit.contract.merger import PolicyMerger

        merger = PolicyMerger()
        adrs = [
            self._make_adr("ADR-0002", date(2024, 2, 1), supersedes=["ADR-0001"]),
            self._make_adr("ADR-0001", date(2024, 1, 1)),
        ]
        sorted_adrs = merger._topological_sort(adrs)
        ids = [a.front_matter.id for a in sorted_adrs]
        assert ids.index("ADR-0001") < ids.index("ADR-0002")

    def test_diamond_supersession(self):
        """ADR-003 supersedes both ADR-001 and ADR-002 — both must come before ADR-003."""
        from adr_kit.contract.merger import PolicyMerger

        merger = PolicyMerger()
        adrs = [
            self._make_adr(
                "ADR-0003", date(2024, 3, 1), supersedes=["ADR-0001", "ADR-0002"]
            ),  # noqa
            self._make_adr("ADR-0001", date(2024, 1, 1)),
            self._make_adr("ADR-0002", date(2024, 2, 1)),
        ]
        sorted_adrs = merger._topological_sort(adrs)
        ids = [a.front_matter.id for a in sorted_adrs]
        assert ids.index("ADR-0001") < ids.index("ADR-0003")
        assert ids.index("ADR-0002") < ids.index("ADR-0003")

    def test_supersession_not_in_list_is_ignored(self):
        """supersedes references to ADRs not in the input list are safely ignored."""
        from adr_kit.contract.merger import PolicyMerger

        merger = PolicyMerger()
        adrs = [
            self._make_adr("ADR-0002", date(2024, 2, 1), supersedes=["ADR-9999"]),
            self._make_adr("ADR-0001", date(2024, 1, 1)),
        ]
        sorted_adrs = merger._topological_sort(adrs)
        assert len(sorted_adrs) == 2

    def test_empty_list(self):
        from adr_kit.contract.merger import PolicyMerger

        merger = PolicyMerger()
        assert merger._topological_sort([]) == []


# ---------------------------------------------------------------------------
# EnforcementResult model tests
# ---------------------------------------------------------------------------


class TestEnforcementResult:
    def test_empty_result_has_empty_hash(self):
        result = EnforcementResult()
        assert result.idempotency_hash == ""

    def test_compute_hash_populates_field(self):
        result = EnforcementResult()
        h = result.compute_idempotency_hash()
        assert len(h) == 64  # SHA-256 hex
        assert result.idempotency_hash == h

    def test_same_result_same_hash(self):
        """Identical outputs always produce identical hash."""
        r1 = EnforcementResult(
            fragments_applied=[
                AppliedFragment(
                    adapter="eslint",
                    target_file="/project/.eslintrc.adrs.json",
                    policy_keys=["imports.disallow.axios"],
                    fragment_type="json_file",
                )
            ],
            files_touched=["/project/.eslintrc.adrs.json"],
        )
        r2 = EnforcementResult(
            fragments_applied=[
                AppliedFragment(
                    adapter="eslint",
                    target_file="/project/.eslintrc.adrs.json",
                    policy_keys=["imports.disallow.axios"],
                    fragment_type="json_file",
                )
            ],
            files_touched=["/project/.eslintrc.adrs.json"],
        )
        h1 = r1.compute_idempotency_hash()
        h2 = r2.compute_idempotency_hash()
        assert h1 == h2

    def test_different_fragments_different_hash(self):
        r1 = EnforcementResult(
            fragments_applied=[
                AppliedFragment(
                    adapter="eslint",
                    target_file="/project/.eslintrc.adrs.json",
                    policy_keys=["imports.disallow.axios"],
                    fragment_type="json_file",
                )
            ]
        )
        r2 = EnforcementResult(
            fragments_applied=[
                AppliedFragment(
                    adapter="ruff",
                    target_file="/project/.ruff-adr.toml",
                    policy_keys=["python.disallow_imports.requests"],
                    fragment_type="toml_file",
                )
            ]
        )
        assert r1.compute_idempotency_hash() != r2.compute_idempotency_hash()

    def test_skipped_adapters_included_in_hash(self):
        r1 = EnforcementResult(
            skipped_adapters=[SkippedAdapter(adapter="ruff", reason="no python policy")]
        )
        r2 = EnforcementResult(
            skipped_adapters=[
                SkippedAdapter(adapter="eslint", reason="no imports policy")
            ]
        )
        assert r1.compute_idempotency_hash() != r2.compute_idempotency_hash()


# ---------------------------------------------------------------------------
# ESLint contract-driven adapter
# ---------------------------------------------------------------------------


class TestESLintContractAdapter:
    def _make_constraints(self, disallow=None, prefer=None):
        from adr_kit.core.model import ImportPolicy

        return MergedConstraints(imports=ImportPolicy(disallow=disallow, prefer=prefer))

    def test_generates_no_restricted_imports_rule(self):
        from adr_kit.enforcement.adapters.eslint import (
            generate_eslint_config_from_contract,
        )

        constraints = self._make_constraints(disallow=["axios", "moment"])
        config = generate_eslint_config_from_contract(constraints)

        assert "no-restricted-imports" in config["rules"]
        paths = config["rules"]["no-restricted-imports"][1]["paths"]
        names = {p["name"] for p in paths}
        assert "axios" in names
        assert "moment" in names

    def test_prefer_goes_to_metadata(self):
        from adr_kit.enforcement.adapters.eslint import (
            generate_eslint_config_from_contract,
        )

        constraints = self._make_constraints(prefer=["react-query"])
        config = generate_eslint_config_from_contract(constraints)

        assert config["__adr_metadata"]["preferred_libraries"] is not None
        assert "react-query" in config["__adr_metadata"]["preferred_libraries"]

    def test_empty_constraints_produces_no_rules(self):
        from adr_kit.enforcement.adapters.eslint import (
            generate_eslint_config_from_contract,
        )

        constraints = MergedConstraints()
        config = generate_eslint_config_from_contract(constraints)

        assert "no-restricted-imports" not in config["rules"]

    def test_has_metadata_timestamp(self):
        from adr_kit.enforcement.adapters.eslint import (
            generate_eslint_config_from_contract,
        )

        constraints = self._make_constraints(disallow=["axios"])
        config = generate_eslint_config_from_contract(constraints)

        assert config["__adr_metadata"]["generation_timestamp"] is not None


# ---------------------------------------------------------------------------
# Ruff contract-driven adapter
# ---------------------------------------------------------------------------


class TestRuffContractAdapter:
    def test_python_disallow_goes_to_banned_from(self):
        import toml

        from adr_kit.core.model import PythonPolicy
        from adr_kit.enforcement.adapters.ruff import generate_ruff_config_from_contract

        constraints = MergedConstraints(
            python=PythonPolicy(disallow_imports=["requests", "httpx"])
        )
        toml_str = generate_ruff_config_from_contract(constraints)
        config = toml.loads(toml_str)

        banned = config["tool"]["ruff"]["lint"]["flake8-import-conventions"][
            "banned-from"
        ]
        assert "requests" in banned
        assert "httpx" in banned

    def test_imports_disallow_also_goes_to_banned_from(self):
        import toml

        from adr_kit.core.model import ImportPolicy
        from adr_kit.enforcement.adapters.ruff import generate_ruff_config_from_contract

        constraints = MergedConstraints(imports=ImportPolicy(disallow=["moment"]))
        toml_str = generate_ruff_config_from_contract(constraints)
        config = toml.loads(toml_str)

        banned = config["tool"]["ruff"]["lint"]["flake8-import-conventions"][
            "banned-from"
        ]
        assert "moment" in banned

    def test_empty_constraints_no_lint_section(self):
        import toml

        from adr_kit.enforcement.adapters.ruff import generate_ruff_config_from_contract

        constraints = MergedConstraints()
        toml_str = generate_ruff_config_from_contract(constraints)
        config = toml.loads(toml_str)

        ruff_cfg = config["tool"]["ruff"]
        assert "lint" not in ruff_cfg


# ---------------------------------------------------------------------------
# EnforcementPipeline integration (no real files needed)
# ---------------------------------------------------------------------------


class TestEnforcementPipeline:
    def test_pipeline_skips_adapters_when_no_constraints(self, tmp_path):
        """When the contract has no constraints, both adapters are skipped."""
        from adr_kit.contract.models import (
            ConstraintsContract,
            ContractMetadata,
        )
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        metadata = ContractMetadata(
            hash="abc123",
            source_adrs=[],
            adr_directory=str(tmp_path),
        )
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=MergedConstraints(),
            provenance={},
            approved_adrs=[],
        )

        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract)

        skipped_names = {s.adapter for s in result.skipped_adapters}
        assert "eslint" in skipped_names
        assert "ruff" in skipped_names
        assert len(result.fragments_applied) == 0

    def test_pipeline_applies_eslint_when_imports_present(self, tmp_path):
        """ESLint adapter runs and writes file when import constraints exist."""
        from adr_kit.contract.models import (
            ConstraintsContract,
            ContractMetadata,
        )
        from adr_kit.core.model import ImportPolicy
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        metadata = ContractMetadata(
            hash="abc123",
            source_adrs=["ADR-0001"],
            adr_directory=str(tmp_path),
        )
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=MergedConstraints(imports=ImportPolicy(disallow=["axios"])),
            provenance={},
            approved_adrs=[],
        )

        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract)

        eslint_fragments = [
            f for f in result.fragments_applied if f.adapter == "eslint"
        ]
        assert len(eslint_fragments) == 1
        assert (tmp_path / ".eslintrc.adrs.json").exists()

    def test_pipeline_produces_idempotency_hash(self, tmp_path):
        """Pipeline always produces a non-empty idempotency hash."""
        from adr_kit.contract.models import (
            ConstraintsContract,
            ContractMetadata,
        )
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        metadata = ContractMetadata(
            hash="abc123",
            source_adrs=[],
            adr_directory=str(tmp_path),
        )
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=MergedConstraints(),
            provenance={},
            approved_adrs=[],
        )

        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract)

        assert len(result.idempotency_hash) == 64

    def test_pipeline_idempotent_on_same_contract(self, tmp_path):
        """Same contract compiled twice → identical idempotency hash."""
        from adr_kit.contract.models import (
            ConstraintsContract,
            ContractMetadata,
        )
        from adr_kit.core.model import ImportPolicy
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        metadata = ContractMetadata(
            hash="abc123",
            source_adrs=["ADR-0001"],
            adr_directory=str(tmp_path),
        )
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=MergedConstraints(imports=ImportPolicy(disallow=["axios"])),
            provenance={},
            approved_adrs=[],
        )

        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        r1 = pipeline.compile(contract=contract)
        r2 = pipeline.compile(contract=contract)

        assert r1.idempotency_hash == r2.idempotency_hash

    def test_pipeline_provenance_from_contract(self, tmp_path):
        """Pipeline exposes contract provenance in result."""
        from adr_kit.contract.models import (
            ConstraintsContract,
            ContractMetadata,
            PolicyProvenance,
        )
        from adr_kit.enforcement.pipeline import EnforcementPipeline

        rule_path = "imports.disallow.axios"
        prov = PolicyProvenance(
            adr_id="ADR-0001",
            adr_title="Use React Query",
            rule_path=rule_path,
            effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            clause_id=PolicyProvenance.make_clause_id("ADR-0001", rule_path),
        )
        metadata = ContractMetadata(
            hash="abc123",
            source_adrs=["ADR-0001"],
            adr_directory=str(tmp_path),
        )
        contract = ConstraintsContract(
            metadata=metadata,
            constraints=MergedConstraints(),
            provenance={rule_path: prov},
            approved_adrs=[],
        )

        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract)

        assert len(result.provenance) == 1
        entry = result.provenance[0]
        assert entry.rule == rule_path
        assert entry.source_adr_id == "ADR-0001"
        assert len(entry.clause_id) == 12
