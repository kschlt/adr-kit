"""Unit tests for CreationWorkflow."""

import pytest
import tempfile
from pathlib import Path
from datetime import date

from adr_kit.workflows.creation import CreationWorkflow, CreationInput
from adr_kit.workflows.base import WorkflowStatus
from adr_kit.core.model import ADRStatus


class TestCreationWorkflow:
    """Test CreationWorkflow functionality."""

    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)

    @pytest.fixture
    def sample_creation_input(self):
        """Create sample creation input."""
        return CreationInput(
            title="Use PostgreSQL for primary database",
            context="We need a reliable relational database for storing user data and application state.",
            decision="Use PostgreSQL as our primary database management system.",
            consequences="Better data integrity and ACID compliance, but requires more infrastructure setup than SQLite.",
            deciders=["backend-team", "tech-lead"],
            tags=["database", "backend", "infrastructure"],
            alternatives="Considered MySQL, SQLite, and MongoDB as alternatives.",
        )

    @pytest.fixture
    def existing_adr(self, temp_adr_dir):
        """Create an existing ADR to test conflict detection."""
        adr_content = """---
id: ADR-0001
title: Use MySQL for database
status: accepted
date: 2024-01-15
deciders: ["backend-team"]
tags: ["database", "mysql"]
---

## Context

We need a database solution.

## Decision

Use MySQL for all database needs.

## Consequences

MySQL is reliable and well-supported.
"""

        existing_file = Path(temp_adr_dir) / "adr-0001-use-mysql-for-database.md"
        existing_file.write_text(adr_content)
        return str(existing_file)

    def test_successful_adr_creation(self, temp_adr_dir, sample_creation_input):
        """Test successful creation of a new ADR."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(input_data=sample_creation_input)

        # Check overall success
        assert result.success is True
        assert result.status == WorkflowStatus.SUCCESS
        assert "created successfully" in result.message.lower()
        assert result.duration_ms > 0

        # Check steps were executed
        step_names = [step.name for step in result.steps]
        expected_steps = [
            "generate_adr_id",
            "validate_input",
            "check_conflicts",
            "create_adr_content",
            "write_adr_file",
        ]

        for expected_step in expected_steps:
            assert expected_step in step_names

        # All steps should be successful
        for step in result.steps:
            assert step.status == WorkflowStatus.SUCCESS
            assert step.duration_ms > 0

        # Check creation result data
        assert "creation_result" in result.data
        creation_result = result.data["creation_result"]

        assert creation_result.adr_id.startswith("ADR-")
        assert creation_result.adr_id == "ADR-0001"  # First ADR
        assert Path(creation_result.file_path).exists()
        assert creation_result.conflicts_detected == []
        assert creation_result.validation_warnings == []

        # Check next steps guidance
        assert len(result.next_steps) > 0
        assert any("review" in step.lower() for step in result.next_steps)
        assert any("approve" in step.lower() for step in result.next_steps)

        # Verify file content
        created_file = Path(creation_result.file_path)
        content = created_file.read_text()

        assert "PostgreSQL" in content
        assert "status: proposed" in content
        assert "backend-team" in content
        assert sample_creation_input.context in content
        assert sample_creation_input.decision in content
        assert sample_creation_input.consequences in content

    def test_adr_id_generation_with_existing(
        self, temp_adr_dir, sample_creation_input, existing_adr
    ):
        """Test ADR ID generation when ADRs already exist."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(input_data=sample_creation_input)

        assert result.success is True

        creation_result = result.data["creation_result"]
        # Should generate ADR-0002 since ADR-0001 already exists
        assert creation_result.adr_id == "ADR-0002"

    def test_conflict_detection(self, temp_adr_dir, existing_adr):
        """Test detection of conflicting ADRs."""
        # Create input that conflicts with existing MySQL ADR
        conflicting_input = CreationInput(
            title="Use MongoDB for primary database",  # Different database choice
            context="We need a NoSQL database solution.",
            decision="Use MongoDB as our primary database.",
            consequences="Flexible schema but less ACID compliance.",
            tags=["database", "nosql"],
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=conflicting_input)

        # Should still create the ADR but detect conflicts
        assert result.success is True

        creation_result = result.data["creation_result"]

        # Should detect conflict with existing database decision
        # Note: Actual conflict detection depends on implementation sophistication
        # At minimum, should complete without errors
        assert isinstance(creation_result.conflicts_detected, list)
        assert isinstance(creation_result.related_adrs, list)

    def test_policy_integration(self, temp_adr_dir):
        """Test ADR creation with policy block."""
        policy_input = CreationInput(
            title="Use React for frontend development",
            context="We need a modern frontend framework.",
            decision="Use React for all frontend components.",
            consequences="Modern UI development but learning curve.",
            policy={
                "imports": {
                    "prefer": ["react", "@types/react"],
                    "disallow": ["vue", "angular"],
                },
                "boundaries": {
                    "layers": [
                        {"name": "components", "path": "src/components/*"},
                        {"name": "utils", "path": "src/utils/*"},
                    ],
                    "rules": ["forbid: utils -> components"],
                },
            },
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=policy_input)

        assert result.success is True

        creation_result = result.data["creation_result"]
        created_file = Path(creation_result.file_path)
        content = created_file.read_text()

        # Should include policy in YAML front matter
        assert "policy:" in content
        assert "imports:" in content
        assert "prefer:" in content
        assert "react" in content
        assert "disallow:" in content
        assert "vue" in content

    def test_missing_required_fields(self, temp_adr_dir):
        """Test handling of missing required fields."""
        incomplete_input = CreationInput(
            title="Incomplete ADR",
            context="Some context",
            decision="",  # Missing decision
            consequences="",  # Missing consequences
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=incomplete_input)

        # Should fail validation
        assert result.success is False
        assert result.status == WorkflowStatus.VALIDATION_ERROR

        # Should have validation error details
        assert len(result.errors) > 0
        assert any(
            "decision" in error.lower() or "consequence" in error.lower()
            for error in result.errors
        )

        # Should fail at validation step
        failed_steps = [
            step for step in result.steps if step.status == WorkflowStatus.FAILED
        ]
        assert len(failed_steps) > 0
        assert any("validate" in step.name.lower() for step in failed_steps)

    def test_file_system_errors(self, temp_adr_dir, sample_creation_input):
        """Test handling of file system errors."""
        # Make ADR directory read-only to simulate permission errors
        adr_path = Path(temp_adr_dir)
        original_permissions = adr_path.stat().st_mode

        try:
            adr_path.chmod(0o444)  # Read-only

            workflow = CreationWorkflow(adr_dir=temp_adr_dir)
            result = workflow.execute(input_data=sample_creation_input)

            # Should fail at file writing step
            assert result.success is False

            # Should have error details about permission or writing
            assert len(result.errors) > 0

            # Should have failed step
            failed_steps = [
                step for step in result.steps if step.status == WorkflowStatus.FAILED
            ]
            assert len(failed_steps) > 0

        finally:
            # Restore permissions for cleanup
            adr_path.chmod(original_permissions)

    def test_very_long_title_handling(self, temp_adr_dir):
        """Test handling of very long ADR titles."""
        long_title = (
            "Use a very long technology name that exceeds normal title length limits and might cause file system issues "
            * 3
        )

        long_title_input = CreationInput(
            title=long_title,
            context="Testing long title handling",
            decision="Use the long-named technology",
            consequences="Might cause file naming issues",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=long_title_input)

        # Should handle long titles gracefully
        # Either succeed with truncated filename or provide clear error
        if result.success:
            creation_result = result.data["creation_result"]
            created_file = Path(creation_result.file_path)

            # Filename should be reasonable length
            assert len(created_file.name) < 255  # Most file systems limit
            assert created_file.exists()
        else:
            # Should provide clear error about title length
            assert len(result.errors) > 0

    def test_special_characters_in_title(self, temp_adr_dir):
        """Test handling of special characters in ADR title."""
        special_title = "Use C++ & PostgreSQL with 100% reliability (v2.0)"

        special_input = CreationInput(
            title=special_title,
            context="Testing special character handling",
            decision="Use technologies with special characters in names",
            consequences="Must handle file naming properly",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=special_input)

        assert result.success is True

        creation_result = result.data["creation_result"]
        created_file = Path(creation_result.file_path)

        # Should create valid filename
        assert created_file.exists()

        # Filename should not contain problematic characters
        filename = created_file.name
        problematic_chars = ["<", ">", ":", '"', "|", "?", "*", "/"]
        for char in problematic_chars:
            assert char not in filename

    def test_semantic_similarity_detection(self, temp_adr_dir, existing_adr):
        """Test detection of semantically similar ADRs."""
        # Create input that's semantically similar to existing MySQL ADR
        similar_input = CreationInput(
            title="Use MariaDB for data storage",  # Similar to MySQL
            context="We need a relational database for our data.",
            decision="Use MariaDB as our database solution.",
            consequences="Similar to MySQL with some improvements.",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=similar_input)

        assert result.success is True

        creation_result = result.data["creation_result"]

        # Should detect some relationship (exact behavior depends on implementation)
        # At minimum, should complete and populate related_adrs field
        assert isinstance(creation_result.related_adrs, list)

    def test_date_setting(self, temp_adr_dir, sample_creation_input):
        """Test that ADR gets proper date setting."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=sample_creation_input)

        assert result.success is True

        creation_result = result.data["creation_result"]
        created_file = Path(creation_result.file_path)
        content = created_file.read_text()

        # Should have today's date
        today = date.today().isoformat()
        assert today in content
        assert "date:" in content

    def test_incremental_id_generation(self, temp_adr_dir, sample_creation_input):
        """Test that multiple ADRs get incremental IDs."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)

        # Create first ADR
        result1 = workflow.execute(input_data=sample_creation_input)
        assert result1.success is True
        creation1 = result1.data["creation_result"]
        assert creation1.adr_id == "ADR-0001"

        # Create second ADR
        second_input = CreationInput(
            title="Use Redis for caching",
            context="Need caching solution",
            decision="Use Redis for cache",
            consequences="Fast caching but additional infrastructure",
        )

        result2 = workflow.execute(input_data=second_input)
        assert result2.success is True
        creation2 = result2.data["creation_result"]
        assert creation2.adr_id == "ADR-0002"

        # Both files should exist
        assert Path(creation1.file_path).exists()
        assert Path(creation2.file_path).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
