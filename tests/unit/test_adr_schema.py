"""Unit tests for schemas/adr.schema.json — relation fields."""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "adr.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())


def _minimal_adr(**extra: object) -> dict:
    return {
        "id": "ADR-0001",
        "title": "Use FastAPI",
        "status": "accepted",
        "date": "2024-01-01",
        **extra,
    }


class TestRelationFieldsInSchema:
    def test_depends_on_valid(self) -> None:
        jsonschema.validate(_minimal_adr(depends_on=["ADR-0002"]), SCHEMA)

    def test_related_to_valid(self) -> None:
        jsonschema.validate(_minimal_adr(related_to=["ADR-0003"]), SCHEMA)

    def test_both_fields_valid(self) -> None:
        jsonschema.validate(
            _minimal_adr(depends_on=["ADR-0001"], related_to=["ADR-0002", "ADR-0003"]),
            SCHEMA,
        )

    def test_depends_on_wrong_type_fails(self) -> None:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_minimal_adr(depends_on="ADR-0002"), SCHEMA)

    def test_related_to_wrong_type_fails(self) -> None:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_minimal_adr(related_to="ADR-0003"), SCHEMA)

    def test_adr_without_relation_fields_valid(self) -> None:
        jsonschema.validate(_minimal_adr(), SCHEMA)
