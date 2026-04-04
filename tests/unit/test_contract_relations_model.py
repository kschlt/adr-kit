"""Unit tests for ContractRelations model and its integration into ConstraintsContract."""

from pathlib import Path

from adr_kit.contract.models import (
    ConstraintsContract,
    ContractRelations,
    MergedConstraints,
)


class TestContractRelationsDefaults:
    def test_all_fields_default_to_empty(self) -> None:
        rel = ContractRelations()
        assert rel.depends_on == {}
        assert rel.related_to == {}
        assert rel.supersedes == {}
        assert rel.required_by == {}
        assert rel.related_from == {}
        assert rel.superseded_by == {}
        assert rel.supersession_chains == []
        assert rel.clause_to_adr == {}
        assert rel.adr_to_clauses == {}

    def test_round_trip_serialization(self) -> None:
        rel = ContractRelations(
            depends_on={"ADR-0002": ["ADR-0001"]},
            required_by={"ADR-0001": ["ADR-0002"]},
            related_to={"ADR-0003": ["ADR-0004"]},
            related_from={"ADR-0004": ["ADR-0003"]},
            supersedes={"ADR-0005": ["ADR-0004"]},
            superseded_by={"ADR-0004": ["ADR-0005"]},
            supersession_chains=[["ADR-0004", "ADR-0005"]],
            clause_to_adr={"abc123def456": "ADR-0001"},
            adr_to_clauses={"ADR-0001": ["abc123def456"]},
        )
        dumped = rel.model_dump()
        restored = ContractRelations.model_validate(dumped)

        assert restored.depends_on == {"ADR-0002": ["ADR-0001"]}
        assert restored.required_by == {"ADR-0001": ["ADR-0002"]}
        assert restored.related_to == {"ADR-0003": ["ADR-0004"]}
        assert restored.related_from == {"ADR-0004": ["ADR-0003"]}
        assert restored.supersedes == {"ADR-0005": ["ADR-0004"]}
        assert restored.superseded_by == {"ADR-0004": ["ADR-0005"]}
        assert restored.supersession_chains == [["ADR-0004", "ADR-0005"]]
        assert restored.clause_to_adr == {"abc123def456": "ADR-0001"}
        assert restored.adr_to_clauses == {"ADR-0001": ["abc123def456"]}


class TestConstraintsContractRelationsField:
    def test_create_empty_has_relations_attribute(self) -> None:
        contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        assert hasattr(contract, "relations")
        assert isinstance(contract.relations, ContractRelations)

    def test_create_empty_relations_are_empty(self) -> None:
        contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        assert contract.relations.depends_on == {}
        assert contract.relations.supersession_chains == []

    def test_relations_excluded_from_content_hash(self) -> None:
        """Populating relations must not change the contract content hash."""
        contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        hash_without_relations = contract.calculate_content_hash()

        contract.relations = ContractRelations(
            depends_on={"ADR-0002": ["ADR-0001"]},
            required_by={"ADR-0001": ["ADR-0002"]},
        )
        hash_with_relations = contract.calculate_content_hash()

        assert hash_without_relations == hash_with_relations

    def test_relations_default_factory_per_instance(self) -> None:
        """Each ConstraintsContract instance must have its own ContractRelations."""
        a = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        b = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        a.relations.depends_on["ADR-0001"] = ["ADR-0002"]
        assert "ADR-0001" not in b.relations.depends_on

    def test_contract_with_populated_relations_round_trips(self) -> None:
        contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        contract.relations = ContractRelations(
            supersedes={"ADR-0002": ["ADR-0001"]},
            superseded_by={"ADR-0001": ["ADR-0002"]},
            supersession_chains=[["ADR-0001", "ADR-0002"]],
        )
        dumped = contract.model_dump()
        restored = ConstraintsContract.model_validate(dumped)
        assert restored.relations.supersedes == {"ADR-0002": ["ADR-0001"]}
        assert restored.relations.supersession_chains == [["ADR-0001", "ADR-0002"]]

    def test_empty_dicts_not_excluded_by_exclude_none(self) -> None:
        """Empty dicts are not None, so they appear in model_dump(exclude_none=True)."""
        rel = ContractRelations()
        dumped = rel.model_dump(exclude_none=True)
        # Empty dicts should still be present (they are not None)
        assert "depends_on" in dumped
        assert dumped["depends_on"] == {}

    def test_constraints_contract_has_relations_field_in_dump(self) -> None:
        contract = ConstraintsContract.create_empty(Path("/tmp/adrs"))
        dumped = contract.model_dump()
        assert "relations" in dumped
