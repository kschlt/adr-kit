"""Unit tests for relations surfacing in PlanningWorkflow."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from adr_kit.contract.models import ConstraintsContract, ContractRelations
from adr_kit.workflows.planning import PlanningWorkflow


def _make_contract_with_relations(relations: ContractRelations) -> ConstraintsContract:
    """Build a minimal ConstraintsContract with pre-populated relations."""
    contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
    contract.relations = relations
    return contract


class TestGetAdrRelations:
    def _workflow(self) -> PlanningWorkflow:
        return PlanningWorkflow(adr_dir=Path("/tmp/adrs"))

    def test_populated_relations_for_known_adr(self) -> None:
        rel = ContractRelations(
            depends_on={"ADR-0002": ["ADR-0001"]},
            required_by={"ADR-0001": ["ADR-0002"]},
            related_to={"ADR-0002": ["ADR-0003"]},
            related_from={"ADR-0003": ["ADR-0002"]},
            supersedes={"ADR-0002": ["ADR-0001"]},
            superseded_by={"ADR-0001": ["ADR-0002"]},
        )
        contract = _make_contract_with_relations(rel)
        wf = self._workflow()

        result = wf._get_adr_relations("ADR-0002", contract)

        assert result["depends_on"] == ["ADR-0001"]
        assert result["required_by"] == []
        assert result["related_to"] == ["ADR-0003"]
        assert result["related_from"] == []
        assert result["supersedes"] == ["ADR-0001"]
        assert result["superseded_by"] == []

    def test_all_lists_empty_for_unknown_adr(self) -> None:
        contract = _make_contract_with_relations(ContractRelations())
        wf = self._workflow()

        result = wf._get_adr_relations("ADR-9999", contract)

        assert result["depends_on"] == []
        assert result["required_by"] == []
        assert result["related_to"] == []
        assert result["related_from"] == []
        assert result["supersedes"] == []
        assert result["superseded_by"] == []

    def test_returns_dict_with_expected_keys(self) -> None:
        contract = _make_contract_with_relations(ContractRelations())
        wf = self._workflow()
        result = wf._get_adr_relations("ADR-0001", contract)
        assert set(result.keys()) == {
            "depends_on",
            "required_by",
            "related_to",
            "related_from",
            "supersedes",
            "superseded_by",
        }


class TestPlanningWorkflowRelations:
    def test_contract_relations_in_result_data(self) -> None:
        """After execute(), result.data must contain 'contract_relations'."""
        wf = PlanningWorkflow(adr_dir=Path("/tmp/adrs"))

        rel = ContractRelations(depends_on={"ADR-0002": ["ADR-0001"]})
        contract = _make_contract_with_relations(rel)

        with patch.object(wf, "_load_constraints_contract", return_value=contract):
            from adr_kit.workflows.planning import PlanningInput

            result = wf.execute(
                input_data=PlanningInput(task_description="implement a feature")
            )

        assert result.success
        assert "contract_relations" in result.data
        assert isinstance(result.data["contract_relations"], ContractRelations)

    def test_relevant_adrs_have_relations_key(self) -> None:
        """Each ADR dict in relevant_adrs must include a 'relations' key."""
        from datetime import date

        from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus

        fm = ADRFrontMatter(
            id="ADR-0001",
            title="Use Python",
            status=ADRStatus.ACCEPTED,
            date=date(2024, 1, 1),
        )
        adr = ADR(front_matter=fm, content="## Decision\nUse Python.")

        contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        contract.approved_adrs = [adr]

        wf = PlanningWorkflow(adr_dir=Path("/tmp/adrs"))

        with patch.object(wf, "_load_constraints_contract", return_value=contract):
            from adr_kit.workflows.planning import PlanningInput

            result = wf.execute(
                input_data=PlanningInput(
                    task_description="python implementation feature"
                )
            )

        assert result.success
        relevant = result.data["architectural_context"].relevant_adrs
        for adr_info in relevant:
            assert "relations" in adr_info
            assert isinstance(adr_info["relations"], dict)
