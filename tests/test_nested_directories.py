"""Tests for nested directory creation (Issue #4 from feedback).

This test verifies that ADR creation works with deeply nested directory paths
like 'docs/architecture/decisions/adr'.
"""

from pathlib import Path

import pytest

from adr_kit.workflows.creation import CreationInput, CreationWorkflow


def test_create_adr_in_nested_directory(tmp_path):
    """ADRs should be creatable in nested directories (3+ levels deep)."""
    # Create a 3-level nested directory path
    nested_adr_dir = tmp_path / "docs" / "architecture" / "decisions"

    # Directory should NOT exist yet
    assert not nested_adr_dir.exists()

    # Create workflow with nested path
    workflow = CreationWorkflow(adr_dir=nested_adr_dir)

    # Create test ADR
    input_data = CreationInput(
        title="Test Nested Directory ADR",
        context="Testing creation in nested directories",
        decision="Use nested directory structure for ADRs",
        consequences="Better organization of architectural decisions",
        deciders=["test-user"],
        tags=["testing", "nested"],
    )

    # Execute creation workflow
    result = workflow.execute(input_data=input_data)

    # Workflow should succeed
    assert result.success, f"Workflow failed: {result.errors}"
    assert nested_adr_dir.exists(), "Nested directory was not created"

    # ADR file should exist
    creation_result = result.data["creation_result"]
    file_path = Path(creation_result.file_path)
    assert file_path.exists(), f"ADR file not created at {file_path}"

    # File should be in correct directory
    assert file_path.parent == nested_adr_dir


def test_create_adr_with_very_deep_nesting(tmp_path):
    """Test with very deep nesting (5 levels)."""
    deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e"

    workflow = CreationWorkflow(adr_dir=deep_dir)

    input_data = CreationInput(
        title="Deep Nesting Test",
        context="Testing very deep directory structures",
        decision="Support arbitrary nesting depth",
        consequences="Maximum flexibility in directory organization",
    )

    result = workflow.execute(input_data=input_data)

    assert result.success
    assert deep_dir.exists()

    creation_result = result.data["creation_result"]
    file_path = Path(creation_result.file_path)
    assert file_path.exists()


def test_create_adr_with_relative_path(tmp_path):
    """Test creation with relative path containing '..'."""
    # Create base directory
    base_dir = tmp_path / "project"
    base_dir.mkdir()

    # Use relative path with parent directory reference
    rel_path = base_dir / ".." / "docs" / "adr"
    resolved_path = rel_path.resolve()

    workflow = CreationWorkflow(adr_dir=str(rel_path))  # Pass as string

    input_data = CreationInput(
        title="Relative Path Test",
        context="Testing relative paths with parent references",
        decision="Normalize paths before use",
        consequences="Consistent behavior across different path formats",
    )

    result = workflow.execute(input_data=input_data)

    assert result.success
    # Path should be resolved/normalized
    assert resolved_path.exists()


def test_create_adr_with_trailing_slash(tmp_path):
    """Test that trailing slashes are handled correctly."""
    adr_dir = tmp_path / "docs" / "adr"

    # Add trailing slash
    path_with_slash = str(adr_dir) + "/"

    workflow = CreationWorkflow(adr_dir=path_with_slash)

    input_data = CreationInput(
        title="Trailing Slash Test",
        context="Testing path normalization with trailing slashes",
        decision="Strip trailing slashes",
        consequences="Consistent path handling",
    )

    result = workflow.execute(input_data=input_data)

    assert result.success
    assert adr_dir.exists()


def test_create_multiple_adrs_in_same_nested_directory(tmp_path):
    """Multiple ADRs can be created in the same nested directory."""
    nested_dir = tmp_path / "docs" / "decisions" / "backend"

    workflow = CreationWorkflow(adr_dir=nested_dir)

    # Create first ADR
    input1 = CreationInput(
        title="First ADR",
        context="First decision",
        decision="Choose technology A",
        consequences="Benefits of A",
    )
    result1 = workflow.execute(input_data=input1)
    assert result1.success

    # Create second ADR (reuse workflow instance)
    input2 = CreationInput(
        title="Second ADR",
        context="Second decision",
        decision="Choose technology B",
        consequences="Benefits of B",
    )
    result2 = workflow.execute(input_data=input2)
    assert result2.success

    # Both files should exist
    creation1 = result1.data["creation_result"]
    creation2 = result2.data["creation_result"]

    assert Path(creation1.file_path).exists()
    assert Path(creation2.file_path).exists()

    # Both should be in same directory
    assert Path(creation1.file_path).parent == Path(creation2.file_path).parent


def test_nested_directory_with_spaces_in_path(tmp_path):
    """Test that paths with spaces are handled correctly."""
    # Create directory path with spaces
    spaced_dir = tmp_path / "Architectural Decisions" / "Backend Services"

    workflow = CreationWorkflow(adr_dir=spaced_dir)

    input_data = CreationInput(
        title="Spaces in Path Test",
        context="Testing paths with spaces",
        decision="Support spaces in directory names",
        consequences="User-friendly directory naming",
    )

    result = workflow.execute(input_data=input_data)

    assert result.success
    assert spaced_dir.exists()

    creation_result = result.data["creation_result"]
    file_path = Path(creation_result.file_path)
    assert file_path.exists()
