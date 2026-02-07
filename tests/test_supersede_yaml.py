"""Tests for YAML generation in supersede workflow (Issue #3 from feedback).

This test verifies that supersede generates valid YAML frontmatter,
especially with multiline text and special characters.
"""

from pathlib import Path

import pytest
import yaml

from adr_kit.core.parse import parse_adr_file
from adr_kit.workflows.creation import CreationInput, CreationWorkflow
from adr_kit.workflows.supersede import SupersedeInput, SupersedeWorkflow


def test_supersede_with_simple_reason(tmp_path):
    """Superseding with simple reason should generate valid YAML."""
    adr_dir = tmp_path / "docs" / "adr"

    # Create initial ADR
    creation = CreationWorkflow(adr_dir=adr_dir)
    original = CreationInput(
        title="Original Decision",
        context="Original context",
        decision="Use Technology A",
        consequences="Benefits of A",
    )
    result = creation.execute(input_data=original)
    assert result.success

    old_id = result.data["creation_result"].adr_id

    # Supersede with simple reason
    supersede = SupersedeWorkflow(adr_dir=adr_dir)
    supersede_input = SupersedeInput(
        old_adr_id=old_id,
        new_proposal=CreationInput(
            title="New Decision",
            context="New context",
            decision="Use Technology B",
            consequences="Benefits of B",
        ),
        supersede_reason="Technology A was deprecated",
    )

    result = supersede.execute(input_data=supersede_input)
    assert result.success

    # Parse old ADR and verify YAML is valid
    old_adr_files = list(adr_dir.glob(f"{old_id}-*.md"))
    assert len(old_adr_files) == 1

    old_adr = parse_adr_file(old_adr_files[0])
    assert old_adr.status == "superseded"
    assert old_adr.front_matter.superseded_by is not None


def test_supersede_with_multiline_reason(tmp_path):
    """Superseding with multiline reason should generate valid YAML."""
    adr_dir = tmp_path / "docs" / "adr"

    # Create initial ADR
    creation = CreationWorkflow(adr_dir=adr_dir)
    original = CreationInput(
        title="Original Decision",
        context="Original context",
        decision="Use Old Framework",
        consequences="Benefits",
    )
    result = creation.execute(input_data=original)
    assert result.success

    old_id = result.data["creation_result"].adr_id

    # Supersede with MULTILINE reason
    multiline_reason = """The old framework has several critical issues:
    1. Security vulnerabilities discovered
    2. Performance problems at scale
    3. No longer maintained by vendor

    After evaluation, we decided to migrate to new framework."""

    supersede = SupersedeWorkflow(adr_dir=adr_dir)
    supersede_input = SupersedeInput(
        old_adr_id=old_id,
        new_proposal=CreationInput(
            title="New Framework Decision",
            context="Need to replace old framework",
            decision="Migrate to new framework",
            consequences="Better security and performance",
        ),
        supersede_reason=multiline_reason,
    )

    result = supersede.execute(input_data=supersede_input)
    assert result.success, f"Supersede failed: {result.errors}"

    # Parse old ADR - this will fail if YAML is malformed
    old_adr_files = list(adr_dir.glob(f"{old_id}-*.md"))
    assert len(old_adr_files) == 1

    with open(old_adr_files[0]) as f:
        content = f.read()

    # Extract YAML frontmatter
    yaml_match = content.split("---\n", 2)
    assert len(yaml_match) >= 2, "No YAML frontmatter found"

    yaml_content = yaml_match[1]

    # Parse YAML - this will raise exception if malformed
    try:
        parsed_yaml = yaml.safe_load(yaml_content)
        assert parsed_yaml is not None
        assert "supersede_reason" in parsed_yaml
        assert "superseded_by" in parsed_yaml
    except yaml.YAMLError as e:
        pytest.fail(f"YAML parsing failed: {e}\n\nYAML content:\n{yaml_content}")


def test_supersede_with_quotes_in_reason(tmp_path):
    """Superseding with quotes in reason should escape properly."""
    adr_dir = tmp_path / "docs" / "adr"

    # Create initial ADR
    creation = CreationWorkflow(adr_dir=adr_dir)
    original = CreationInput(
        title="Original Decision",
        context="Original context",
        decision="Use Library X",
        consequences="Benefits",
    )
    result = creation.execute(input_data=original)
    assert result.success

    old_id = result.data["creation_result"].adr_id

    # Supersede with quotes in reason
    reason_with_quotes = 'The vendor said "Library X is deprecated" so we switched'

    supersede = SupersedeWorkflow(adr_dir=adr_dir)
    supersede_input = SupersedeInput(
        old_adr_id=old_id,
        new_proposal=CreationInput(
            title="New Library Decision",
            context="Library X deprecated",
            decision="Use Library Y",
            consequences="Better support",
        ),
        supersede_reason=reason_with_quotes,
    )

    result = supersede.execute(input_data=supersede_input)
    assert result.success

    # Parse old ADR
    old_adr_files = list(adr_dir.glob(f"{old_id}-*.md"))
    assert len(old_adr_files) == 1

    with open(old_adr_files[0]) as f:
        content = f.read()

    yaml_match = content.split("---\n", 2)
    yaml_content = yaml_match[1]

    try:
        parsed_yaml = yaml.safe_load(yaml_content)
        assert "supersede_reason" in parsed_yaml
        # Verify quotes are preserved in the content
        assert "deprecated" in parsed_yaml["supersede_reason"]
    except yaml.YAMLError as e:
        pytest.fail(f"YAML parsing failed with quotes: {e}\n\nYAML:\n{yaml_content}")


def test_supersede_with_special_characters_in_reason(tmp_path):
    """Superseding with special YAML characters should not break parsing."""
    adr_dir = tmp_path / "docs" / "adr"

    # Create initial ADR
    creation = CreationWorkflow(adr_dir=adr_dir)
    original = CreationInput(
        title="Original Decision",
        context="Original context",
        decision="Use Config A",
        consequences="Benefits",
    )
    result = creation.execute(input_data=original)
    assert result.success

    old_id = result.data["creation_result"].adr_id

    # Supersede with YAML special characters: colons, braces, brackets
    reason_with_special_chars = "Replaced because: {performance: low, cost: high}"

    supersede = SupersedeWorkflow(adr_dir=adr_dir)
    supersede_input = SupersedeInput(
        old_adr_id=old_id,
        new_proposal=CreationInput(
            title="New Config Decision",
            context="Config A has issues",
            decision="Use Config B",
            consequences="Better performance",
        ),
        supersede_reason=reason_with_special_chars,
    )

    result = supersede.execute(input_data=supersede_input)
    assert result.success

    # Parse old ADR
    old_adr_files = list(adr_dir.glob(f"{old_id}-*.md"))
    assert len(old_adr_files) == 1

    with open(old_adr_files[0]) as f:
        content = f.read()

    yaml_match = content.split("---\n", 2)
    yaml_content = yaml_match[1]

    try:
        parsed_yaml = yaml.safe_load(yaml_content)
        assert "supersede_reason" in parsed_yaml
    except yaml.YAMLError as e:
        pytest.fail(
            f"YAML parsing failed with special chars: {e}\n\nYAML:\n{yaml_content}"
        )


def test_all_superseded_fields_are_valid_yaml(tmp_path):
    """All fields added during supersession should be valid YAML."""
    adr_dir = tmp_path / "docs" / "adr"

    # Create initial ADR
    creation = CreationWorkflow(adr_dir=adr_dir)
    original = CreationInput(
        title="Original Decision",
        context="Original context",
        decision="Use Service A",
        consequences="Benefits",
    )
    result = creation.execute(input_data=original)
    assert result.success

    old_id = result.data["creation_result"].adr_id

    # Supersede
    supersede = SupersedeWorkflow(adr_dir=adr_dir)
    supersede_input = SupersedeInput(
        old_adr_id=old_id,
        new_proposal=CreationInput(
            title="New Service Decision",
            context="Service A needs replacement",
            decision="Use Service B",
            consequences="Better scalability",
        ),
        supersede_reason="Migrating to cloud-native architecture",
    )

    result = supersede.execute(input_data=supersede_input)
    assert result.success

    # Parse old ADR
    old_adr_files = list(adr_dir.glob(f"{old_id}-*.md"))
    old_adr = parse_adr_file(old_adr_files[0])

    # Verify all supersede-related fields are present
    assert old_adr.status == "superseded"
    assert old_adr.front_matter.superseded_by is not None
    assert len(old_adr.front_matter.superseded_by) > 0

    # Verify YAML is valid by reading raw file
    with open(old_adr_files[0]) as f:
        content = f.read()

    yaml_match = content.split("---\n", 2)
    yaml_content = yaml_match[1]

    parsed = yaml.safe_load(yaml_content)
    assert "status" in parsed
    assert "superseded_by" in parsed
    assert "supersede_date" in parsed
    assert "supersede_reason" in parsed

    assert parsed["status"] == "superseded"
