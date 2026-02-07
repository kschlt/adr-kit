"""Tests for safe ADR deletion workflow with immutability protection."""

import json
from pathlib import Path
from datetime import date as Date
import pytest

from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus
from adr_kit.workflows.deletion import DeletionInput, DeletionWorkflow
from adr_kit.workflows.base import WorkflowStatus


@pytest.fixture
def temp_adr_dir(tmp_path):
    """Create a temporary ADR directory for testing."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    return adr_dir


@pytest.fixture
def create_test_adr():
    """Factory fixture to create test ADRs."""

    def _create_adr(
        adr_dir: Path, adr_id: str, status: ADRStatus, title: str = "Test ADR"
    ) -> Path:
        """Create a test ADR file.

        Args:
            adr_dir: Directory to create ADR in
            adr_id: ADR ID (e.g., "ADR-0001")
            status: ADR status
            title: ADR title

        Returns:
            Path to created ADR file
        """
        front_matter = ADRFrontMatter(
            id=adr_id,
            title=title,
            status=status,
            date=Date(2025, 1, 1),
            deciders=["Test Developer"],
            tags=["test"],
        )

        adr = ADR(
            front_matter=front_matter,
            content=f"## Context\n\nTest ADR for {adr_id}\n\n## Decision\n\nTest decision\n\n## Consequences\n\nTest consequences",
        )

        # Write to file
        file_path = adr_dir / f"{adr_id}-{title.lower().replace(' ', '-')}.md"
        with open(file_path, "w") as f:
            f.write(adr.to_markdown())

        return file_path

    return _create_adr


def test_delete_proposed_adr_success(temp_adr_dir, create_test_adr):
    """Test successful deletion of a proposed ADR."""
    # Create a proposed ADR
    adr_id = "ADR-0001"
    create_test_adr(temp_adr_dir, adr_id, ADRStatus.PROPOSED)

    # Create workflow and execute deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion succeeded
    assert result.success is True
    assert result.status == WorkflowStatus.SUCCESS
    assert adr_id in result.message
    assert result.data["adr_id"] == adr_id
    assert result.data["was_forced"] is False

    # Verify file was deleted
    assert not any(temp_adr_dir.glob(f"{adr_id}-*.md"))


def test_delete_rejected_adr_success(temp_adr_dir, create_test_adr):
    """Test successful deletion of a rejected ADR."""
    # Create a rejected ADR
    adr_id = "ADR-0002"
    create_test_adr(temp_adr_dir, adr_id, ADRStatus.REJECTED)

    # Create workflow and execute deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion succeeded
    assert result.success is True
    assert result.status == WorkflowStatus.SUCCESS
    assert result.data["adr_id"] == adr_id

    # Verify file was deleted
    assert not any(temp_adr_dir.glob(f"{adr_id}-*.md"))


def test_delete_accepted_adr_blocked(temp_adr_dir, create_test_adr):
    """Test that deletion of accepted ADR is blocked."""
    # Create an accepted ADR
    adr_id = "ADR-0003"
    create_test_adr(temp_adr_dir, adr_id, ADRStatus.ACCEPTED)

    # Create workflow and attempt deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion was blocked
    assert result.success is False
    assert result.status == WorkflowStatus.VALIDATION_ERROR
    assert "immutability" in result.message.lower()
    assert result.data["deletion_allowed"] is False
    assert result.data["status"] == "accepted"

    # Verify file still exists
    assert any(temp_adr_dir.glob(f"{adr_id}-*.md"))


def test_delete_superseded_adr_blocked(temp_adr_dir, create_test_adr):
    """Test that deletion of superseded ADR is blocked."""
    # Create a superseded ADR
    adr_id = "ADR-0004"
    file_path = create_test_adr(temp_adr_dir, adr_id, ADRStatus.ACCEPTED)

    # Manually set to superseded with superseded_by field
    from adr_kit.core.parse import parse_adr_file

    adr = parse_adr_file(file_path)
    adr.front_matter.status = ADRStatus.SUPERSEDED
    adr.front_matter.superseded_by = ["ADR-0005"]

    with open(file_path, "w") as f:
        f.write(adr.to_markdown())

    # Create workflow and attempt deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion was blocked
    assert result.success is False
    assert result.status == WorkflowStatus.VALIDATION_ERROR
    assert result.data["deletion_allowed"] is False
    assert result.data["status"] == "superseded"

    # Verify file still exists
    assert any(temp_adr_dir.glob(f"{adr_id}-*.md"))


def test_delete_deprecated_adr_blocked(temp_adr_dir, create_test_adr):
    """Test that deletion of deprecated ADR is blocked."""
    # Create a deprecated ADR
    adr_id = "ADR-0005"
    file_path = create_test_adr(temp_adr_dir, adr_id, ADRStatus.ACCEPTED)

    # Manually set to deprecated
    from adr_kit.core.parse import parse_adr_file

    adr = parse_adr_file(file_path)
    adr.front_matter.status = ADRStatus.DEPRECATED

    with open(file_path, "w") as f:
        f.write(adr.to_markdown())

    # Create workflow and attempt deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion was blocked
    assert result.success is False
    assert result.status == WorkflowStatus.VALIDATION_ERROR
    assert result.data["deletion_allowed"] is False
    assert result.data["status"] == "deprecated"

    # Verify file still exists
    assert any(temp_adr_dir.glob(f"{adr_id}-*.md"))


def test_delete_with_force_flag_success(temp_adr_dir, create_test_adr):
    """Test that force flag allows deletion of accepted ADR."""
    # Create an accepted ADR
    adr_id = "ADR-0006"
    create_test_adr(temp_adr_dir, adr_id, ADRStatus.ACCEPTED)

    # Create workflow and execute forced deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(
        adr_id=adr_id, force=True, reason="Testing force deletion"
    )
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion succeeded
    assert result.success is True
    assert result.status == WorkflowStatus.SUCCESS
    assert result.data["adr_id"] == adr_id
    assert result.data["was_forced"] is True

    # Verify file was deleted
    assert not any(temp_adr_dir.glob(f"{adr_id}-*.md"))


def test_delete_nonexistent_adr_fails(temp_adr_dir):
    """Test that deleting non-existent ADR fails."""
    # Attempt to delete non-existent ADR
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id="ADR-9999", force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion failed
    assert result.success is False
    assert result.status == WorkflowStatus.FAILED
    assert "not found" in result.message.lower()


def test_delete_with_supersede_relationships_warning(temp_adr_dir, create_test_adr):
    """Test that deletion warns about broken supersede relationships."""
    # Create ADRs with supersede relationships
    adr_id_old = "ADR-0007"
    adr_id_new = "ADR-0008"

    # Create old ADR (superseded)
    file_path_old = create_test_adr(temp_adr_dir, adr_id_old, ADRStatus.ACCEPTED)
    from adr_kit.core.parse import parse_adr_file

    adr_old = parse_adr_file(file_path_old)
    adr_old.front_matter.status = ADRStatus.SUPERSEDED
    adr_old.front_matter.superseded_by = [adr_id_new]
    with open(file_path_old, "w") as f:
        f.write(adr_old.to_markdown())

    # Create new ADR (supersedes old)
    file_path_new = create_test_adr(temp_adr_dir, adr_id_new, ADRStatus.PROPOSED)
    adr_new = parse_adr_file(file_path_new)
    adr_new.front_matter.supersedes = [adr_id_old]
    with open(file_path_new, "w") as f:
        f.write(adr_new.to_markdown())

    # Delete the new ADR (proposed, so allowed)
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id_new, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion succeeded with warnings
    assert result.success is True
    assert result.data["warnings"]  # Should have warnings about relationships
    assert any(
        adr_id_old in warning for warning in result.data["warnings"]
    )  # Should mention old ADR


def test_delete_regenerates_index(temp_adr_dir, create_test_adr):
    """Test that deletion regenerates the ADR index."""
    # Create multiple ADRs
    create_test_adr(temp_adr_dir, "ADR-0009", ADRStatus.PROPOSED)
    create_test_adr(temp_adr_dir, "ADR-0010", ADRStatus.PROPOSED)

    # Create initial index
    from adr_kit.index.json_index import generate_adr_index

    index_path = temp_adr_dir / "adr-index.json"
    generate_adr_index(temp_adr_dir, index_path, validate=False)

    # Verify index has both ADRs
    with open(index_path) as f:
        index_data = json.load(f)
    assert index_data["metadata"]["total_adrs"] == 2

    # Delete one ADR
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id="ADR-0009", force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion succeeded
    assert result.success is True

    # Verify index was regenerated with only one ADR
    with open(index_path) as f:
        index_data = json.load(f)
    assert index_data["metadata"]["total_adrs"] == 1


def test_delete_guidance_messages(temp_adr_dir, create_test_adr):
    """Test that proper guidance messages are returned when deletion is blocked."""
    # Create an accepted ADR
    adr_id = "ADR-0011"
    create_test_adr(temp_adr_dir, adr_id, ADRStatus.ACCEPTED)

    # Attempt deletion
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion blocked with helpful guidance
    assert result.success is False
    assert result.guidance  # Should have guidance
    assert "supersede" in result.guidance.lower() or "deprecate" in result.guidance.lower()
    assert result.next_steps  # Should have next steps
    assert any("supersede" in step.lower() for step in result.next_steps)


def test_delete_immutability_lock_removed(temp_adr_dir, create_test_adr):
    """Test that immutability lock is removed when deleting a locked ADR."""
    from adr_kit.core.immutability import ImmutabilityManager

    # Create a proposed ADR and lock it
    adr_id = "ADR-0012"
    file_path = create_test_adr(temp_adr_dir, adr_id, ADRStatus.PROPOSED)

    # Create immutability lock
    from adr_kit.core.parse import parse_adr_file

    adr = parse_adr_file(file_path)
    immutability_mgr = ImmutabilityManager(temp_adr_dir.parent.parent)
    immutability_mgr.approve_adr(adr, make_readonly=False)

    # Verify lock exists
    assert immutability_mgr.is_adr_locked(adr_id)

    # Delete the ADR
    workflow = DeletionWorkflow(adr_dir=temp_adr_dir, project_root=temp_adr_dir.parent.parent)
    deletion_input = DeletionInput(adr_id=adr_id, force=False)
    result = workflow.execute(input_data=deletion_input)

    # Assert deletion succeeded
    assert result.success is True

    # Verify lock was removed
    assert not immutability_mgr.is_adr_locked(adr_id)
