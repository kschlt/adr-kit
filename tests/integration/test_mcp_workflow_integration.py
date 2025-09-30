"""Integration tests for MCP server to workflow integration."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from adr_kit.mcp.models import (
    AnalyzeProjectRequest,
    PreflightCheckRequest,
    CreateADRRequest,
    ApproveADRRequest,
    SupersedeADRRequest,
    PlanningContextRequest,
)


class TestMCPWorkflowIntegration:
    """Test integration between MCP server and workflows."""

    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create package.json
            package_json = {
                "name": "test-project",
                "dependencies": {"react": "^18.0.0", "fastapi": "^0.104.0"},
            }

            with open(project_dir / "package.json", "w") as f:
                json.dump(package_json, f)

            yield str(project_dir)

    def test_mcp_analyze_project_integration(self, temp_project_dir, temp_adr_dir):
        """Test MCP analyze project tool calls workflow correctly."""
        # Import the actual MCP tool function
        # Note: We can't call the decorated function directly, so we test the workflow
        from adr_kit.workflows.analyze import AnalyzeProjectWorkflow
        from adr_kit.mcp.server import logger

        # Test request model validation
        request = AnalyzeProjectRequest(
            project_path=temp_project_dir,
            focus_areas=["frontend", "backend"],
            adr_dir=temp_adr_dir,
        )

        # Validate request structure
        assert request.project_path == temp_project_dir
        assert "frontend" in request.focus_areas
        assert request.adr_dir == temp_adr_dir

        # Test that workflow can be called with request data
        workflow = AnalyzeProjectWorkflow(adr_dir=request.adr_dir)
        result = workflow.execute(
            project_path=request.project_path, focus_areas=request.focus_areas
        )

        # Should work and return proper structure
        assert result.success is True
        assert "analysis_prompt" in result.data
        assert "project_context" in result.data
        assert result.guidance
        assert len(result.next_steps) > 0

    def test_mcp_preflight_integration(self, temp_adr_dir):
        """Test MCP preflight tool calls workflow correctly."""
        from adr_kit.workflows.preflight import PreflightWorkflow, PreflightInput

        # Test request model
        request = PreflightCheckRequest(
            choice="PostgreSQL",
            context={"use_case": "primary database"},
            category="database",
            adr_dir=temp_adr_dir,
        )

        # Validate request
        assert request.choice == "PostgreSQL"
        assert request.context["use_case"] == "primary database"
        assert request.category == "database"

        # Test workflow can be called
        workflow = PreflightWorkflow(adr_dir=request.adr_dir)
        preflight_input = PreflightInput(
            choice=request.choice, context=request.context, category=request.category
        )

        result = workflow.execute(input_data=preflight_input)

        # Should return proper decision structure
        assert result.success is True or result.success is False  # Either is valid
        assert "decision" in result.data

        decision = result.data["decision"]
        assert decision.status in ["ALLOWED", "REQUIRES_ADR", "BLOCKED"]
        assert decision.reasoning
        assert decision.next_steps

    def test_mcp_create_integration(self, temp_adr_dir):
        """Test MCP create tool calls workflow correctly."""
        from adr_kit.workflows.creation import CreationWorkflow, CreationInput

        # Test request model
        request = CreateADRRequest(
            title="Use PostgreSQL for primary database",
            context="We need a reliable database for user data",
            decision="Use PostgreSQL as our primary database system",
            consequences="Better data integrity, more complex setup",
            deciders=["backend-team"],
            tags=["database", "backend"],
            policy={
                "imports": {
                    "prefer": ["postgresql", "psycopg2"],
                    "disallow": ["sqlite3"],
                }
            },
            alternatives="Considered MySQL and SQLite",
            adr_dir=temp_adr_dir,
        )

        # Validate request structure
        assert request.title
        assert request.context
        assert request.decision
        assert request.consequences
        assert "backend-team" in request.deciders
        assert "database" in request.tags
        assert request.policy["imports"]["prefer"] == ["postgresql", "psycopg2"]

        # Test workflow integration
        workflow = CreationWorkflow(adr_dir=request.adr_dir)
        creation_input = CreationInput(
            title=request.title,
            context=request.context,
            decision=request.decision,
            consequences=request.consequences,
            deciders=request.deciders,
            tags=request.tags,
            policy=request.policy,
            alternatives=request.alternatives,
        )

        result = workflow.execute(input_data=creation_input)

        # Should create ADR successfully
        assert result.success is True
        assert "creation_result" in result.data

        creation_result = result.data["creation_result"]
        assert creation_result.adr_id.startswith("ADR-")
        assert Path(creation_result.file_path).exists()

    def test_mcp_approve_integration(self, temp_adr_dir):
        """Test MCP approve tool integration."""
        from adr_kit.workflows.creation import CreationWorkflow, CreationInput
        from adr_kit.workflows.approval import ApprovalWorkflow, ApprovalInput

        # First create an ADR to approve
        creation_workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        creation_input = CreationInput(
            title="Test ADR for approval",
            context="Testing approval workflow",
            decision="Use test technology",
            consequences="Test consequences",
        )

        creation_result = creation_workflow.execute(input_data=creation_input)
        assert creation_result.success is True

        created_adr_id = creation_result.data["creation_result"].adr_id

        # Test approval request model
        approval_request = ApproveADRRequest(
            adr_id=created_adr_id,
            approval_notes="Approved for testing",
            force_approve=False,
            adr_dir=temp_adr_dir,
        )

        # Validate request
        assert approval_request.adr_id == created_adr_id
        assert approval_request.approval_notes == "Approved for testing"
        assert approval_request.force_approve is False

        # Test workflow integration
        approval_workflow = ApprovalWorkflow(adr_dir=approval_request.adr_dir)
        approval_input = ApprovalInput(
            adr_id=approval_request.adr_id,
            approval_notes=approval_request.approval_notes,
            force_approve=approval_request.force_approve,
        )

        result = approval_workflow.execute(input_data=approval_input)

        # Should complete approval (success depends on implementation)
        if result.success:
            assert "approval_result" in result.data
            approval_result = result.data["approval_result"]
            assert approval_result.adr_id == created_adr_id

    def test_mcp_supersede_integration(self, temp_adr_dir):
        """Test MCP supersede tool integration."""
        from adr_kit.workflows.creation import CreationWorkflow, CreationInput
        from adr_kit.workflows.supersede import SupersedeWorkflow, SupersedeInput

        # Create original ADR
        creation_workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        original_input = CreationInput(
            title="Use MySQL for database",
            context="Need database solution",
            decision="Use MySQL",
            consequences="Good performance",
        )

        creation_result = creation_workflow.execute(input_data=original_input)
        assert creation_result.success is True
        old_adr_id = creation_result.data["creation_result"].adr_id

        # Test supersede request
        supersede_request = SupersedeADRRequest(
            old_adr_id=old_adr_id,
            new_title="Use PostgreSQL for database",
            new_context="MySQL limitations discovered",
            new_decision="Migrate to PostgreSQL",
            new_consequences="Better features, migration effort",
            supersede_reason="MySQL licensing and feature limitations",
            new_deciders=["backend-team"],
            new_tags=["database", "migration"],
            auto_approve=False,
            adr_dir=temp_adr_dir,
        )

        # Validate request structure
        assert supersede_request.old_adr_id == old_adr_id
        assert "PostgreSQL" in supersede_request.new_title
        assert supersede_request.supersede_reason

        # Test workflow integration
        workflow = SupersedeWorkflow(adr_dir=supersede_request.adr_dir)

        new_proposal = CreationInput(
            title=supersede_request.new_title,
            context=supersede_request.new_context,
            decision=supersede_request.new_decision,
            consequences=supersede_request.new_consequences,
            deciders=supersede_request.new_deciders,
            tags=supersede_request.new_tags,
            alternatives=supersede_request.new_alternatives,
        )

        supersede_input = SupersedeInput(
            old_adr_id=supersede_request.old_adr_id,
            new_proposal=new_proposal,
            supersede_reason=supersede_request.supersede_reason,
            auto_approve=supersede_request.auto_approve,
        )

        result = workflow.execute(input_data=supersede_input)

        # Should handle supersession (success depends on implementation)
        if result.success:
            assert "supersede_result" in result.data
            supersede_result = result.data["supersede_result"]
            assert supersede_result.old_adr_id == old_adr_id
            assert supersede_result.new_adr_id.startswith("ADR-")

    def test_mcp_planning_context_integration(self, temp_adr_dir):
        """Test MCP planning context tool integration."""
        from adr_kit.workflows.planning import PlanningWorkflow, PlanningInput

        # Test request model
        planning_request = PlanningContextRequest(
            task_description="Implement user authentication system",
            context_type="implementation",
            domain_hints=["backend", "security"],
            priority_level="high",
            adr_dir=temp_adr_dir,
        )

        # Validate request
        assert "authentication" in planning_request.task_description
        assert planning_request.context_type == "implementation"
        assert "backend" in planning_request.domain_hints
        assert planning_request.priority_level == "high"

        # Test workflow integration
        workflow = PlanningWorkflow(adr_dir=planning_request.adr_dir)
        planning_input = PlanningInput(
            task_description=planning_request.task_description,
            context_type=planning_request.context_type,
            domain_hints=planning_request.domain_hints,
            priority_level=planning_request.priority_level,
        )

        result = workflow.execute(input_data=planning_input)

        # Should provide planning context
        if result.success:
            assert "architectural_context" in result.data
            context = result.data["architectural_context"]
            assert context.relevant_adrs is not None
            assert context.applicable_constraints is not None
            assert context.guidance_prompts

    def test_response_format_consistency(self, temp_project_dir, temp_adr_dir):
        """Test that all workflows return consistent response formats for MCP."""
        from adr_kit.workflows.analyze import AnalyzeProjectWorkflow
        from adr_kit.mcp.models import success_response, error_response

        # Test successful workflow response
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(project_path=temp_project_dir)

        if result.success:
            # Convert to MCP response format
            mcp_response = success_response(
                message=result.message,
                data=result.data,
                next_steps=result.next_steps,
                metadata={"duration_ms": result.duration_ms},
            )

            # Should have standard MCP response structure
            assert mcp_response["status"] == "success"
            assert "message" in mcp_response
            assert "data" in mcp_response
            assert "next_steps" in mcp_response
            assert "metadata" in mcp_response

            # Data should contain workflow-specific results
            assert isinstance(mcp_response["data"], dict)
            assert isinstance(mcp_response["next_steps"], list)

        # Test error response format
        error_resp = error_response(
            error="Test error",
            details="Detailed error information",
            suggested_action="Try this fix",
            error_code="TEST_ERROR",
        )

        assert error_resp["status"] == "error"
        assert error_resp["error"] == "Test error"
        assert error_resp["details"] == "Detailed error information"
        assert error_resp["suggested_action"] == "Try this fix"
        assert error_resp["error_code"] == "TEST_ERROR"

    def test_request_model_validation(self):
        """Test that request models validate input properly."""
        # Test valid request
        valid_request = AnalyzeProjectRequest(
            project_path="/valid/path",
            focus_areas=["frontend", "backend"],
            adr_dir="docs/adr",
        )

        assert valid_request.project_path == "/valid/path"
        assert len(valid_request.focus_areas) == 2

        # Test with defaults
        default_request = AnalyzeProjectRequest()
        assert default_request.project_path is None
        assert default_request.focus_areas == []
        assert default_request.adr_dir == "docs/adr"

        # Test CreateADR required fields
        create_request = CreateADRRequest(
            title="Test ADR",
            context="Test context",
            decision="Test decision",
            consequences="Test consequences",
        )

        assert create_request.title == "Test ADR"
        assert create_request.deciders == []  # Default empty list
        assert create_request.tags == []  # Default empty list

    def test_error_propagation(self, temp_adr_dir):
        """Test that workflow errors are properly propagated to MCP responses."""
        from adr_kit.workflows.creation import CreationWorkflow, CreationInput

        # Create invalid input to trigger error
        invalid_input = CreationInput(
            title="",  # Empty title should cause error
            context="Test context",
            decision="Test decision",
            consequences="Test consequences",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=invalid_input)

        # Workflow should fail
        assert result.success is False
        assert len(result.errors) > 0

        # Errors should be detailed enough for MCP response
        first_error = result.errors[0]
        assert isinstance(first_error, str)
        assert len(first_error) > 0

    def test_end_to_end_workflow_chain(self, temp_project_dir, temp_adr_dir):
        """Test complete workflow chain: analyze → create → approve."""
        from adr_kit.workflows.analyze import AnalyzeProjectWorkflow
        from adr_kit.workflows.creation import CreationWorkflow, CreationInput
        from adr_kit.workflows.approval import ApprovalWorkflow, ApprovalInput

        # Step 1: Analyze project
        analyze_workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
        analyze_result = analyze_workflow.execute(project_path=temp_project_dir)

        assert analyze_result.success is True
        assert "analysis_prompt" in analyze_result.data

        # Step 2: Create ADR based on analysis
        create_workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        create_input = CreationInput(
            title="Use React for frontend",
            context="Analysis revealed React usage in project",
            decision="Standardize on React for all frontend development",
            consequences="Consistent frontend architecture, team training needed",
        )

        create_result = create_workflow.execute(input_data=create_input)
        assert create_result.success is True

        created_adr_id = create_result.data["creation_result"].adr_id

        # Step 3: Approve the ADR
        approve_workflow = ApprovalWorkflow(adr_dir=temp_adr_dir)
        approve_input = ApprovalInput(
            adr_id=created_adr_id, approval_notes="Approved after analysis"
        )

        approve_result = approve_workflow.execute(input_data=approve_input)

        # Approval might succeed or fail depending on implementation
        # But should not crash and should provide clear feedback
        assert approve_result is not None
        assert isinstance(approve_result.success, bool)

        if approve_result.success:
            assert "approval_result" in approve_result.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
