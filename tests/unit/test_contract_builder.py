"""Unit tests for ConstraintsContractBuilder — relation reference validation and computation."""

from datetime import date
from pathlib import Path

import pytest

from adr_kit.contract.builder import ConstraintsContractBuilder
from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus


def _make_adr(
    adr_id: str,
    depends_on: list[str] | None = None,
    related_to: list[str] | None = None,
    supersedes: list[str] | None = None,
    status: ADRStatus = ADRStatus.ACCEPTED,
) -> ADR:
    fm = ADRFrontMatter(
        id=adr_id,
        title=f"ADR {adr_id}",
        status=status,
        date=date(2024, 1, 1),
        depends_on=depends_on,
        related_to=related_to,
        supersedes=supersedes,
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


class TestComputeRelations:
    @pytest.fixture()
    def builder(self, tmp_path: Path) -> ConstraintsContractBuilder:
        return ConstraintsContractBuilder(adr_dir=tmp_path)

    def test_empty_corpus_returns_empty_relations(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        rel = builder._compute_relations([], {})
        assert rel.depends_on == {}
        assert rel.required_by == {}
        assert rel.related_to == {}
        assert rel.related_from == {}
        assert rel.supersedes == {}
        assert rel.superseded_by == {}
        assert rel.supersession_chains == []
        assert rel.clause_to_adr == {}
        assert rel.adr_to_clauses == {}

    def test_depends_on_forward_index(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001"), _make_adr("ADR-0002", depends_on=["ADR-0001"])]
        rel = builder._compute_relations(adrs, {})
        assert rel.depends_on == {"ADR-0002": ["ADR-0001"]}

    def test_required_by_reverse_index(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001"), _make_adr("ADR-0002", depends_on=["ADR-0001"])]
        rel = builder._compute_relations(adrs, {})
        assert rel.required_by == {"ADR-0001": ["ADR-0002"]}

    def test_related_to_forward_and_reverse(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001"), _make_adr("ADR-0002", related_to=["ADR-0001"])]
        rel = builder._compute_relations(adrs, {})
        assert rel.related_to == {"ADR-0002": ["ADR-0001"]}
        assert rel.related_from == {"ADR-0001": ["ADR-0002"]}

    def test_supersedes_forward_and_reverse(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [_make_adr("ADR-0001"), _make_adr("ADR-0002", supersedes=["ADR-0001"])]
        rel = builder._compute_relations(adrs, {})
        assert rel.supersedes == {"ADR-0002": ["ADR-0001"]}
        assert rel.superseded_by == {"ADR-0001": ["ADR-0002"]}

    def test_supersession_chain_three_links(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        """ADR-0003 supersedes ADR-0002 supersedes ADR-0001 → chain [0001, 0002, 0003]."""
        adrs = [
            _make_adr("ADR-0001"),
            _make_adr("ADR-0002", supersedes=["ADR-0001"]),
            _make_adr("ADR-0003", supersedes=["ADR-0002"]),
        ]
        rel = builder._compute_relations(adrs, {})
        assert rel.supersession_chains == [["ADR-0001", "ADR-0002", "ADR-0003"]]

    def test_unresolved_depends_on_silently_dropped(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        """Reference to a non-existent ADR ID must not appear in the index."""
        adrs = [_make_adr("ADR-0001", depends_on=["ADR-9999"])]
        rel = builder._compute_relations(adrs, {})
        assert rel.depends_on == {}
        assert rel.required_by == {}

    def test_circular_depends_on_does_not_raise(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        adrs = [
            _make_adr("ADR-0001", depends_on=["ADR-0002"]),
            _make_adr("ADR-0002", depends_on=["ADR-0001"]),
        ]
        rel = builder._compute_relations(adrs, {})
        # Both edges recorded as-is
        assert "ADR-0001" in rel.depends_on
        assert "ADR-0002" in rel.depends_on

    def test_circular_supersession_chain_terminates(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        """Circular supersedes must not cause infinite loop in chain builder."""
        adrs = [
            _make_adr("ADR-0001", supersedes=["ADR-0002"]),
            _make_adr("ADR-0002", supersedes=["ADR-0001"]),
        ]
        # Should complete without error; chain will be a truncated fragment
        rel = builder._compute_relations(adrs, {})
        # No assertion on chain content — just verify no infinite loop

    def test_no_duplicate_reverse_entries(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        """If both sides declare the relationship, reverse entry must not duplicate."""
        adrs = [
            _make_adr("ADR-0001", related_to=["ADR-0002"]),
            _make_adr("ADR-0002", related_to=["ADR-0001"]),
        ]
        rel = builder._compute_relations(adrs, {})
        # Each related_from entry should list the other only once
        assert rel.related_from.get("ADR-0001", []).count("ADR-0002") == 1
        assert rel.related_from.get("ADR-0002", []).count("ADR-0001") == 1

    def test_clause_lookup_tables_built_from_provenance(
        self, builder: ConstraintsContractBuilder
    ) -> None:
        from datetime import datetime, timezone

        from adr_kit.contract.models import PolicyProvenance

        prov = {
            "imports.disallow.axios": PolicyProvenance(
                adr_id="ADR-0001",
                adr_title="No Axios",
                rule_path="imports.disallow.axios",
                effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                clause_id="abc123def456",
            )
        }
        rel = builder._compute_relations([], prov)
        assert rel.clause_to_adr == {"abc123def456": "ADR-0001"}
        assert rel.adr_to_clauses == {"ADR-0001": ["abc123def456"]}
