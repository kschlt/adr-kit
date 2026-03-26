"""Integration tests for CFD — Conflict Detection + Guided Fallback.

Covers:
- Conflicting fragment NOT silently applied — surfaces in EnforcementResult.conflicts
- Unroutable policies generate fallback promptlets (not silently dropped)
- Clean fragments still applied when only some adapters conflict
- Pipeline with mix of routable and unroutable policies
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractMetadata,
    MergedConstraints,
    PolicyProvenance,
)
from adr_kit.core.model import ImportPolicy, PatternPolicy, PythonPolicy
from adr_kit.enforcement.pipeline import EnforcementPipeline


def _make_contract(
    constraints: MergedConstraints,
    source_adrs: list[str] | None = None,
    provenance: dict | None = None,
    tmp_path: Path | None = None,
) -> ConstraintsContract:
    metadata = ContractMetadata(
        hash="test-hash",
        source_adrs=source_adrs or ["ADR-0001"],
        adr_directory=str(tmp_path or Path("/tmp")),
    )
    return ConstraintsContract(
        metadata=metadata,
        constraints=constraints,
        provenance=provenance or {},
        approved_adrs=[],
    )


# ---------------------------------------------------------------------------
# Fragment-config conflict detection in pipeline
# ---------------------------------------------------------------------------


class TestPipelineConflictDetection:
    def test_conflicting_eslint_fragment_not_applied(self, tmp_path: Path):
        """ESLint fragment conflicts with existing .eslintrc.adrs.json — not written."""
        # Pre-existing config that disables the rule the adapter wants to enable
        existing_eslint = {"rules": {"no-restricted-imports": "off"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing_eslint))

        contract = _make_contract(
            constraints=MergedConstraints(imports=ImportPolicy(disallow=["axios"])),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["javascript"])

        # Conflict must be recorded
        assert len(result.conflicts) >= 1
        conflict_descriptions = " ".join(c.description for c in result.conflicts)
        assert "no-restricted-imports" in conflict_descriptions

        # Fragment must NOT be applied (file content unchanged)
        on_disk = json.loads((tmp_path / ".eslintrc.adrs.json").read_text())
        assert on_disk["rules"]["no-restricted-imports"] == "off"

        # ESLint must appear in skipped_adapters (conflict reason)
        eslint_skipped = [s for s in result.skipped_adapters if s.adapter == "eslint"]
        assert eslint_skipped, "ESLint should be in skipped_adapters due to conflict"
        assert "conflict" in eslint_skipped[0].reason

    def test_no_conflict_when_existing_file_absent(self, tmp_path: Path):
        """No existing config → adapter runs normally, no conflicts."""
        contract = _make_contract(
            constraints=MergedConstraints(imports=ImportPolicy(disallow=["axios"])),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["javascript"])

        assert result.conflicts == []
        eslint_applied = [f for f in result.fragments_applied if f.adapter == "eslint"]
        assert len(eslint_applied) == 1
        assert (tmp_path / ".eslintrc.adrs.json").exists()

    def test_conflict_surfaces_source_adrs(self, tmp_path: Path):
        """Conflict records policy_keys of the conflicting fragment."""
        existing_eslint = {"rules": {"no-restricted-imports": "off"}}
        (tmp_path / ".eslintrc.adrs.json").write_text(json.dumps(existing_eslint))

        prov_key = "imports.disallow.axios"
        provenance = {
            prov_key: PolicyProvenance(
                adr_id="ADR-0001",
                adr_title="No Axios",
                rule_path=prov_key,
                effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                clause_id=PolicyProvenance.make_clause_id("ADR-0001", prov_key),
            )
        }
        contract = _make_contract(
            constraints=MergedConstraints(imports=ImportPolicy(disallow=["axios"])),
            provenance=provenance,
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["javascript"])

        assert len(result.conflicts) >= 1
        # source_adrs contains the policy key that caused the conflict
        all_source_adrs = [adr for c in result.conflicts for adr in c.source_adrs]
        assert any("imports" in s for s in all_source_adrs)


# ---------------------------------------------------------------------------
# Fallback promptlet generation for unroutable policies
# ---------------------------------------------------------------------------


class TestPipelineFallbackPromptlets:
    def test_unroutable_policy_generates_promptlet(self, tmp_path: Path):
        """'patterns' key has no adapter — must generate a fallback promptlet."""
        from adr_kit.core.model import PatternRule

        contract = _make_contract(
            constraints=MergedConstraints(
                patterns=PatternPolicy(
                    patterns={
                        "no_god_objects": PatternRule(
                            description="Classes must not exceed 500 lines",
                            language="python",
                            rule=r"^class\s+\w+",
                            severity="error",
                        )
                    }
                )
            ),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        # Use python stack so Ruff adapter is considered (but patterns not covered by Ruff)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        assert len(result.fallback_promptlets) >= 1
        promptlet = json.loads(result.fallback_promptlets[0])
        assert "unenforceable_policy" in promptlet
        assert promptlet["unenforceable_policy"]["policy_key"] == "patterns"
        assert "instruction" in promptlet
        assert "script_requirements" in promptlet
        assert "integration" in promptlet["script_requirements"]

    def test_routable_policy_no_promptlet(self, tmp_path: Path):
        """'imports' is routable via ESLint — no fallback promptlet generated."""
        contract = _make_contract(
            constraints=MergedConstraints(imports=ImportPolicy(disallow=["axios"])),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["javascript"])

        assert result.fallback_promptlets == []

    def test_unroutable_key_in_skipped_adapters(self, tmp_path: Path):
        """Unroutable policy key is also recorded in skipped_adapters with fallback reason."""
        from adr_kit.core.model import PatternRule

        contract = _make_contract(
            constraints=MergedConstraints(
                patterns=PatternPolicy(
                    patterns={
                        "check": PatternRule(
                            description="Check something",
                            language="python",
                            rule=r"\bfoo\b",
                            severity="warning",
                        )
                    }
                )
            ),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        fallback_skipped = [
            s
            for s in result.skipped_adapters
            if "unroutable" in s.reason or "fallback" in s.reason
        ]
        assert fallback_skipped, "Unroutable key should appear in skipped_adapters"

    def test_promptlet_includes_constraint_value(self, tmp_path: Path):
        """Fallback promptlet includes the actual constraint data."""
        from adr_kit.core.model import PatternRule

        contract = _make_contract(
            constraints=MergedConstraints(
                patterns=PatternPolicy(
                    patterns={
                        "no_print": PatternRule(
                            description="No print statements",
                            language="python",
                            rule=r"\bprint\s*\(",
                            severity="error",
                        )
                    }
                )
            ),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        assert result.fallback_promptlets
        promptlet = json.loads(result.fallback_promptlets[0])
        # Constraint value should be present (patterns dict is non-None)
        assert promptlet["unenforceable_policy"]["constraint"] is not None


# ---------------------------------------------------------------------------
# Mixed routable + unroutable policies
# ---------------------------------------------------------------------------


class TestPipelineMixedPolicies:
    def test_routable_applied_unroutable_prompts(self, tmp_path: Path):
        """Python import (Ruff) is routable; patterns is not. Both handled correctly."""
        from adr_kit.core.model import PatternRule

        contract = _make_contract(
            constraints=MergedConstraints(
                python=PythonPolicy(disallow_imports=["requests"]),
                patterns=PatternPolicy(
                    patterns={
                        "no_bare_except": PatternRule(
                            description="No bare except clauses",
                            language="python",
                            rule=r"except\s*:",
                            severity="error",
                        )
                    }
                ),
            ),
            tmp_path=tmp_path,
        )
        pipeline = EnforcementPipeline(adr_dir=tmp_path, project_path=tmp_path)
        result = pipeline.compile(contract=contract, detected_stack=["python"])

        # Ruff adapter should have applied (python disallow_imports)
        ruff_applied = [f for f in result.fragments_applied if f.adapter == "ruff"]
        assert len(ruff_applied) == 1
        assert (tmp_path / ".ruff-adr.toml").exists()

        # Fallback promptlet for patterns
        assert len(result.fallback_promptlets) >= 1
        promptlet = json.loads(result.fallback_promptlets[0])
        assert promptlet["unenforceable_policy"]["policy_key"] == "patterns"

        # No conflicts (no existing files to conflict with)
        assert result.conflicts == []
