"""Unit tests for ConstraintsContractBuilder — relation reference validation."""

from datetime import date
from pathlib import Path

import pytest

from adr_kit.contract.builder import ConstraintsContractBuilder
from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus


def _make_adr(
    adr_id: str,
    depends_on: list[str] | None = None,
    related_to: list[str] | None = None,
    status: ADRStatus = ADRStatus.ACCEPTED,
) -> ADR:
    fm = ADRFrontMatter(
        id=adr_id,
        title=f"ADR {adr_id}",
        status=status,
        date=date(2024, 1, 1),
        depends_on=depends_on,
        related_to=related_to,
    )
    return ADR(front_matter=fm, content="## Decision\nContent.")


class TestRelationReferenceValidation:
    @pytest.fixture()
    def builder(self, tmp_path: Path) -> ConstraintsContractBuilder:
        return ConstraintsContractBuilder(adr_dir=tmp_path)

    def test_no_warnings_when_refs_resolve(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [
            _make_adr("ADR-0001"),
            _make_adr("ADR-0002", depends_on=["ADR-0001"]),
        ]
        all_ids = {a.front_matter.id for a in adrs}
        warnings = builder._validate_relation_references(adrs, all_ids)
        assert warnings == []

    def test_warning_for_unknown_depends_on(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001", depends_on=["ADR-9999"])]
        all_ids = {"ADR-0001"}
        warnings = builder._validate_relation_references(adrs, all_ids)
        assert len(warnings) == 1
        assert "ADR-9999" in warnings[0]
        assert "depends_on" in warnings[0]
        assert "ADR-0001" in warnings[0]

    def test_warning_for_unknown_related_to(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001", related_to=["ADR-9999"])]
        all_ids = {"ADR-0001"}
        warnings = builder._validate_relation_references(adrs, all_ids)
        assert len(warnings) == 1
        assert "ADR-9999" in warnings[0]
        assert "related_to" in warnings[0]

    def test_none_fields_produce_no_warnings(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001")]
        all_ids = {"ADR-0001"}
        warnings = builder._validate_relation_references(adrs, all_ids)
        assert warnings == []

    def test_multiple_unknown_refs_each_warn(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001", depends_on=["ADR-8888", "ADR-9999"])]
        all_ids = {"ADR-0001"}
        warnings = builder._validate_relation_references(adrs, all_ids)
        assert len(warnings) == 2

    def test_proposed_adr_ref_resolves_via_all_ids(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        """depends_on referencing a proposed (not accepted) ADR should not warn."""
        proposed = _make_adr("ADR-0001", status=ADRStatus.PROPOSED)
        accepted = _make_adr("ADR-0002", depends_on=["ADR-0001"])
        # all_ids includes all parsed ADRs, not just accepted ones
        all_ids = {"ADR-0001", "ADR-0002"}
        warnings = builder._validate_relation_references([accepted], all_ids)
        assert warnings == []
