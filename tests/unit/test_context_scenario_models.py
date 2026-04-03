"""Unit tests for SCN scenario taxonomy models in adr_kit.context.models."""

import pytest

from adr_kit.context.models import (
    ChangeMode,
    ConstraintSummary,
    ContextRequest,
    ContextScenario,
    DetailLevel,
    InspectReference,
    PacketMetadata,
    ScenarioContextPacket,
    ScopeHint,
    TargetRef,
)


class TestContextScenario:
    def test_all_values_are_strings(self):
        for member in ContextScenario:
            assert isinstance(member.value, str)

    def test_round_trip_via_value(self):
        for member in ContextScenario:
            assert ContextScenario(member.value) is member

    def test_four_scenarios_defined(self):
        assert len(ContextScenario) == 4

    def test_expected_values(self):
        assert ContextScenario.STRATEGIC_PLANNING == "strategic_planning"
        assert ContextScenario.FOCUSED_IMPLEMENTATION == "focused_implementation"
        assert ContextScenario.PRE_DECISION == "pre_decision"
        assert ContextScenario.SUPERSESSION_IMPACT == "supersession_impact"


class TestChangeMode:
    def test_all_values_are_strings(self):
        for member in ChangeMode:
            assert isinstance(member.value, str)

    def test_expected_values(self):
        assert ChangeMode.NONE == "none"
        assert ChangeMode.ADDITIVE == "additive"
        assert ChangeMode.MODIFYING == "modifying"
        assert ChangeMode.REPLACING == "replacing"


class TestDetailLevel:
    def test_all_values_are_strings(self):
        for member in DetailLevel:
            assert isinstance(member.value, str)

    def test_expected_values(self):
        assert DetailLevel.MINIMAL == "minimal"
        assert DetailLevel.STANDARD == "standard"
        assert DetailLevel.DETAILED == "detailed"


class TestScopeHint:
    def test_constructs_with_required_fields(self):
        hint = ScopeHint(hint_type="file_path", value="src/auth/")
        assert hint.hint_type == "file_path"
        assert hint.value == "src/auth/"

    def test_serialises(self):
        hint = ScopeHint(hint_type="domain", value="authentication")
        d = hint.model_dump()
        assert d == {"hint_type": "domain", "value": "authentication"}


class TestTargetRef:
    def test_constructs_with_required_fields(self):
        ref = TargetRef(ref_type="adr_id", ref_id="ADR-003")
        assert ref.ref_type == "adr_id"
        assert ref.ref_id == "ADR-003"

    def test_serialises(self):
        ref = TargetRef(ref_type="clause_id", ref_id="a1b2c3d4")
        d = ref.model_dump()
        assert d == {"ref_type": "clause_id", "ref_id": "a1b2c3d4"}


class TestContextRequest:
    def test_minimal_construction(self):
        req = ContextRequest(task_summary="implement auth module")
        assert req.task_summary == "implement auth module"
        assert req.scenario == ContextScenario.STRATEGIC_PLANNING
        assert req.change_mode == ChangeMode.NONE
        assert req.detail_level == DetailLevel.STANDARD
        assert req.scope_hints == []
        assert req.known_targets == []
        assert req.focus == ""

    def test_full_construction(self):
        req = ContextRequest(
            scenario=ContextScenario.SUPERSESSION_IMPACT,
            task_summary="replace logging library",
            scope_hints=[ScopeHint(hint_type="tag", value="logging")],
            change_mode=ChangeMode.REPLACING,
            focus="structured logging",
            known_targets=[TargetRef(ref_type="adr_id", ref_id="ADR-005")],
            detail_level=DetailLevel.DETAILED,
        )
        assert req.scenario == ContextScenario.SUPERSESSION_IMPACT
        assert req.change_mode == ChangeMode.REPLACING
        assert req.detail_level == DetailLevel.DETAILED
        assert len(req.scope_hints) == 1
        assert len(req.known_targets) == 1

    def test_round_trip_serialisation(self):
        req = ContextRequest(
            scenario=ContextScenario.FOCUSED_IMPLEMENTATION,
            task_summary="add rate limiting",
            change_mode=ChangeMode.ADDITIVE,
        )
        dumped = req.model_dump()
        restored = ContextRequest.model_validate(dumped)
        assert restored.scenario == req.scenario
        assert restored.task_summary == req.task_summary
        assert restored.change_mode == req.change_mode

    def test_scenario_serialised_as_string(self):
        req = ContextRequest(task_summary="x")
        d = req.model_dump()
        assert isinstance(d["scenario"], str)
        assert d["scenario"] == "strategic_planning"

    def test_task_summary_is_required(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ContextRequest()  # type: ignore[call-arg]


class TestConstraintSummary:
    def test_minimal_construction(self):
        cs = ConstraintSummary(
            source_adr="ADR-001", summary="no raw SQL", relevance_score=0.9
        )
        assert cs.source_adr == "ADR-001"
        assert cs.summary == "no raw SQL"
        assert cs.relevance_score == 0.9
        assert cs.clause_id is None
        assert cs.domain is None

    def test_full_construction(self):
        cs = ConstraintSummary(
            clause_id="abc123",
            source_adr="ADR-002",
            summary="use ORM only",
            relevance_score=0.75,
            domain="persistence",
        )
        assert cs.clause_id == "abc123"
        assert cs.domain == "persistence"

    def test_serialises(self):
        cs = ConstraintSummary(
            source_adr="ADR-003", summary="rule", relevance_score=0.5
        )
        d = cs.model_dump()
        assert "source_adr" in d
        assert "relevance_score" in d


class TestInspectReference:
    def test_constructs_with_required_fields(self):
        ref = InspectReference(
            ref_type="adr", ref_id="ADR-003", label="Authentication Decision"
        )
        assert ref.ref_type == "adr"
        assert ref.ref_id == "ADR-003"
        assert ref.label == "Authentication Decision"

    def test_serialises(self):
        ref = InspectReference(ref_type="clause", ref_id="xyz", label="rate-limit rule")
        d = ref.model_dump()
        assert d == {"ref_type": "clause", "ref_id": "xyz", "label": "rate-limit rule"}


class TestScenarioContextPacket:
    def test_minimal_construction(self):
        pkt = ScenarioContextPacket(
            scenario=ContextScenario.STRATEGIC_PLANNING,
            overview="System uses layered architecture.",
        )
        assert pkt.scenario == ContextScenario.STRATEGIC_PLANNING
        assert pkt.overview == "System uses layered architecture."
        assert pkt.constraints == []
        assert pkt.warnings == []
        assert pkt.inspect_deeper == []
        assert pkt.metadata is None

    def test_full_construction(self):
        pkt = ScenarioContextPacket(
            scenario=ContextScenario.SUPERSESSION_IMPACT,
            overview="This change affects auth.",
            constraints=[
                ConstraintSummary(
                    source_adr="ADR-001", summary="rule", relevance_score=0.8
                )
            ],
            warnings=["Breaking change to session tokens"],
            inspect_deeper=[
                InspectReference(
                    ref_type="adr", ref_id="ADR-001", label="Auth Decision"
                )
            ],
            metadata=PacketMetadata(
                token_estimate=500, candidate_count=12, ranking_strategy="semantic"
            ),
        )
        assert len(pkt.constraints) == 1
        assert len(pkt.warnings) == 1
        assert len(pkt.inspect_deeper) == 1
        assert pkt.metadata is not None
        assert pkt.metadata.token_estimate == 500

    def test_scenario_serialised_as_string(self):
        pkt = ScenarioContextPacket(
            scenario=ContextScenario.PRE_DECISION,
            overview="Before committing.",
        )
        d = pkt.model_dump()
        assert isinstance(d["scenario"], str)
        assert d["scenario"] == "pre_decision"

    def test_scenario_required(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScenarioContextPacket(overview="x")  # type: ignore[call-arg]
