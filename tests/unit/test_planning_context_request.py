"""Unit tests for the extended PlanningContextRequest model (SCN backward compat)."""

import json

from adr_kit.context.models import (
    ChangeMode,
    ContextScenario,
    DetailLevel,
    ScopeHint,
    TargetRef,
)
from adr_kit.mcp.models import PlanningContextRequest


class TestPlanningContextRequestBackwardCompat:
    def test_legacy_call_succeeds(self):
        req = PlanningContextRequest(
            task_description="Implement user authentication", adr_dir="docs/adr"
        )
        assert req.task_description == "Implement user authentication"
        assert req.adr_dir == "docs/adr"

    def test_legacy_call_infers_strategic_planning(self):
        req = PlanningContextRequest(task_description="x")
        assert req.scenario == ContextScenario.STRATEGIC_PLANNING

    def test_legacy_context_type_preserved(self):
        req = PlanningContextRequest(
            task_description="refactor auth", context_type="refactoring"
        )
        assert req.context_type == "refactoring"

    def test_legacy_domain_hints_preserved(self):
        req = PlanningContextRequest(
            task_description="x", domain_hints=["backend", "security"]
        )
        assert req.domain_hints == ["backend", "security"]

    def test_legacy_priority_level_preserved(self):
        req = PlanningContextRequest(task_description="x", priority_level="high")
        assert req.priority_level == "high"

    def test_legacy_defaults(self):
        req = PlanningContextRequest(task_description="x")
        assert req.context_type == "implementation"
        assert req.domain_hints == []
        assert req.priority_level == "normal"
        assert req.adr_dir == "docs/adr"


class TestPlanningContextRequestNewFields:
    def test_new_scenario_field_accepted(self):
        req = PlanningContextRequest(
            task_description="evaluate replacing auth library",
            scenario=ContextScenario.SUPERSESSION_IMPACT,
        )
        assert req.scenario == ContextScenario.SUPERSESSION_IMPACT

    def test_change_mode_accepted(self):
        req = PlanningContextRequest(
            task_description="x",
            scenario=ContextScenario.FOCUSED_IMPLEMENTATION,
            change_mode=ChangeMode.MODIFYING,
        )
        assert req.change_mode == ChangeMode.MODIFYING

    def test_detail_level_accepted(self):
        req = PlanningContextRequest(
            task_description="x", detail_level=DetailLevel.DETAILED
        )
        assert req.detail_level == DetailLevel.DETAILED

    def test_scope_hint_accepted(self):
        req = PlanningContextRequest(
            task_description="x",
            scope=ScopeHint(hint_type="file_path", value="src/auth/"),
        )
        assert req.scope is not None
        assert req.scope.value == "src/auth/"

    def test_target_ref_accepted(self):
        req = PlanningContextRequest(
            task_description="x",
            target=TargetRef(ref_type="adr_id", ref_id="ADR-003"),
        )
        assert req.target is not None
        assert req.target.ref_id == "ADR-003"

    def test_new_field_defaults(self):
        req = PlanningContextRequest(task_description="x")
        assert req.change_mode is None
        assert req.detail_level == DetailLevel.STANDARD
        assert req.scope is None
        assert req.target is None


class TestPlanningContextRequestSerialisation:
    def test_model_dump_includes_all_fields(self):
        req = PlanningContextRequest(task_description="x")
        d = req.model_dump()
        legacy_fields = {
            "task_description",
            "context_type",
            "domain_hints",
            "priority_level",
            "adr_dir",
        }
        new_fields = {"scenario", "change_mode", "detail_level", "scope", "target"}
        assert legacy_fields.issubset(d.keys())
        assert new_fields.issubset(d.keys())

    def test_model_dump_is_json_serialisable(self):
        req = PlanningContextRequest(
            task_description="plan auth refactor",
            scenario=ContextScenario.PRE_DECISION,
            change_mode=ChangeMode.REPLACING,
            scope=ScopeHint(hint_type="domain", value="auth"),
        )
        # Should not raise
        json.dumps(req.model_dump())

    def test_scenario_serialised_as_string(self):
        req = PlanningContextRequest(
            task_description="x", scenario=ContextScenario.FOCUSED_IMPLEMENTATION
        )
        d = req.model_dump()
        assert isinstance(d["scenario"], str)
        assert d["scenario"] == "focused_implementation"
