"""Tests for schema file loading and packaging.

This test ensures that the JSON schema is properly bundled with the package
and can be loaded after installation (fixes Issue #1 from feedback).
"""

from pathlib import Path

import pytest

from adr_kit.core.validate import ADRValidator


def test_schema_loads_successfully():
    """Schema should load without errors using default path."""
    validator = ADRValidator()

    assert validator.schema is not None
    assert isinstance(validator.schema, dict)
    assert validator.schema_path.exists()


def test_schema_path_is_inside_package():
    """Schema path should be inside the adr_kit package, not at project root.

    This ensures the schema is bundled with the package and will be
    included in distribution packages (wheels, sdist).
    """
    validator = ADRValidator()
    schema_path = validator.schema_path

    # Schema should be in adr_kit/schemas/
    assert "adr_kit" in str(schema_path)
    assert "schemas" in str(schema_path)
    assert schema_path.name == "adr.schema.json"

    # Should NOT be at project root (old location)
    assert not str(schema_path).endswith("adr-kit/schemas/adr.schema.json")


def test_schema_contains_required_fields():
    """Schema should define required ADR fields."""
    validator = ADRValidator()
    schema = validator.schema

    assert "$schema" in schema
    assert "type" in schema
    assert schema["type"] == "object"

    # Required fields for an ADR
    required = schema.get("required", [])
    assert "id" in required
    assert "title" in required
    assert "status" in required
    assert "date" in required


def test_schema_has_policy_structure():
    """Schema should define policy structure for enforcement."""
    validator = ADRValidator()
    schema = validator.schema

    properties = schema.get("properties", {})
    assert "policy" in properties

    policy_schema = properties["policy"]
    policy_props = policy_schema.get("properties", {})

    # Should have enforcement-related fields
    assert "imports" in policy_props
    assert "boundaries" in policy_props
    assert "python" in policy_props
    assert "rationales" in policy_props


def test_custom_schema_path_still_works():
    """Should still accept custom schema path for testing/flexibility."""
    validator = ADRValidator()
    default_schema_path = validator.schema_path

    # Should be able to create validator with explicit path
    custom_validator = ADRValidator(schema_path=default_schema_path)
    assert custom_validator.schema_path == default_schema_path
    assert custom_validator.schema is not None


def test_schema_file_not_found_raises_clear_error():
    """Should raise clear error if schema file missing."""
    nonexistent_path = Path("/tmp/nonexistent/schema.json")

    with pytest.raises(ValueError, match="Schema file not found"):
        ADRValidator(schema_path=nonexistent_path)


def test_schema_is_valid_json_schema_draft_2020_12():
    """Schema should use JSON Schema Draft 2020-12."""
    validator = ADRValidator()
    schema = validator.schema

    assert "$schema" in schema
    assert "2020-12" in schema["$schema"]
