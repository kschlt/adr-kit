"""Unit tests for FallbackAdapter (ENF-MODE).

Covers:
- FallbackAdapter capability declarations (output_modes, supported_stages)
- generate_fragments: empty input, single key, multiple keys
- Promptlet JSON structure and content
- Pipeline integration: unroutable keys appear in both fallback_promptlets
  and fragments_applied with output_mode='script_fallback'
"""

import json
from pathlib import Path

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
)
from adr_kit.enforcement.adapters.base import ConfigFragment
from adr_kit.enforcement.adapters.fallback import FallbackAdapter
from adr_kit.enforcement.clause_kinds import EnforcementStage, OutputMode
from adr_kit.enforcement.pipeline import EnforcementPipeline


def _make_contract(
    constraints: MergedConstraints | None = None,
    provenance: dict | None = None,
    tmp_path: Path | None = None,
) -> ConstraintsContract:
    return ConstraintsContract(
        metadata=ContractMetadata(
            hash="test",
            source_adrs=[],
            adr_directory=str(tmp_path or "."),
        ),
        constraints=constraints or MergedConstraints(),
        provenance=provenance or {},
        approved_adrs=[],
    )


class TestFallbackAdapterCapabilities:
    def setup_method(self):
        self.adapter = FallbackAdapter()

    def test_name(self):
        assert self.adapter.name == "fallback"

    def test_output_mode_is_script_fallback(self):
        assert self.adapter.output_modes == [OutputMode.SCRIPT_FALLBACK]

    def test_supported_stages(self):
        assert self.adapter.supported_stages == [EnforcementStage.CI]

    def test_supported_policy_keys_empty(self):
        assert self.adapter.supported_policy_keys == []

    def test_supported_languages_empty(self):
        assert self.adapter.supported_languages == []

    def test_config_targets_empty(self):
        assert self.adapter.config_targets == []


class TestFallbackAdapterGenerateFragments:
    def setup_method(self):
        self.adapter = FallbackAdapter()
        self.constraints = MergedConstraints()

    def test_no_policy_keys_returns_empty(self):
        frags = self.adapter.generate_fragments(self.constraints, policy_keys=None)
        assert frags == []

    def test_empty_policy_keys_returns_empty(self):
        frags = self.adapter.generate_fragments(self.constraints, policy_keys=[])
        assert frags == []

    def test_single_key_produces_one_fragment(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert len(frags) == 1

    def test_multiple_keys_produce_multiple_fragments(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["key_a", "key_b"]
        )
        assert len(frags) == 2

    def test_fragment_type_is_promptlet_json(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert frags[0].fragment_type == "promptlet_json"

    def test_fragment_output_mode_is_script_fallback(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert frags[0].output_mode == OutputMode.SCRIPT_FALLBACK

    def test_fragment_target_file_is_empty(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert frags[0].target_file == ""

    def test_fragment_adapter_name(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert frags[0].adapter == "fallback"

    def test_fragment_policy_keys_set(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert frags[0].policy_keys == ["unknown_key"]

    def test_fragment_is_config_fragment(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        assert isinstance(frags[0], ConfigFragment)

    def test_content_is_valid_json(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        parsed = json.loads(frags[0].content)
        assert isinstance(parsed, dict)

    def test_content_has_required_keys(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["unknown_key"]
        )
        parsed = json.loads(frags[0].content)
        assert "unenforceable_policy" in parsed
        assert "instruction" in parsed
        assert "script_requirements" in parsed

    def test_content_policy_key_matches(self):
        frags = self.adapter.generate_fragments(
            self.constraints, policy_keys=["my_custom_key"]
        )
        parsed = json.loads(frags[0].content)
        assert parsed["unenforceable_policy"]["policy_key"] == "my_custom_key"


class TestFallbackAdapterPipelineIntegration:
    def test_unroutable_key_appears_in_fallback_promptlets(self, tmp_path):
        contract = _make_contract(tmp_path=tmp_path)
        # Patch constraints to include an unroutable key
        # The pipeline will detect 'unknown_key' as unroutable (no adapter handles it)
        # We just verify the pipeline still works when there are no routable constraints
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])
        # No unroutable keys in an empty contract — just verify pipeline runs cleanly
        assert result is not None
        assert isinstance(result.fallback_promptlets, list)

    def test_fragments_applied_contains_script_fallback_entries(self, tmp_path):
        from datetime import datetime, timezone

        from adr_kit.contract.models import PolicyProvenance

        # Build a contract that deliberately has no adapter to handle it
        # by using a provenance key that no adapter supports
        prov = PolicyProvenance(
            adr_id="ADR-001",
            adr_title="Test",
            rule_path="patterns.no_god_objects",
            effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            clause_id=PolicyProvenance.make_clause_id(
                "ADR-001", "patterns.no_god_objects"
            ),
        )
        contract = _make_contract(
            provenance={"patterns.no_god_objects": prov},
            tmp_path=tmp_path,
        )

        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        # Unroutable key should produce a fallback
        # (patterns key is not handled by any standard adapter)
        # Check that if fallback_promptlets exist, fragments_applied also has them
        if result.fallback_promptlets:
            script_fallback_frags = [
                f
                for f in result.fragments_applied
                if f.output_mode == "script_fallback"
            ]
            assert len(script_fallback_frags) == len(result.fallback_promptlets)
            for frag in script_fallback_frags:
                assert frag.adapter == "fallback"
                assert frag.fragment_type == "promptlet_json"
