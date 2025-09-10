"""Unit tests for workflow base classes and infrastructure."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import asdict

from adr_kit.workflows.base import (
    WorkflowStatus,
    WorkflowStep,
    WorkflowResult,
    WorkflowError,
    BaseWorkflow,
)


class TestWorkflowStatus:
    """Test WorkflowStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert WorkflowStatus.SUCCESS == "success"
        assert WorkflowStatus.PARTIAL_SUCCESS == "partial_success"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.VALIDATION_ERROR == "validation_error"
        assert WorkflowStatus.CONFLICT_ERROR == "conflict_error"


class TestWorkflowStep:
    """Test WorkflowStep data class."""

    def test_workflow_step_creation(self):
        """Test creating a workflow step."""
        step = WorkflowStep(
            name="test_step",
            status=WorkflowStatus.SUCCESS,
            message="Step completed",
            duration_ms=100,
            details={"key": "value"},
            errors=["error1"],
            warnings=["warning1"],
        )

        assert step.name == "test_step"
        assert step.status == WorkflowStatus.SUCCESS
        assert step.message == "Step completed"
        assert step.duration_ms == 100
        assert step.details == {"key": "value"}
        assert step.errors == ["error1"]
        assert step.warnings == ["warning1"]

    def test_workflow_step_defaults(self):
        """Test workflow step with default values."""
        step = WorkflowStep(
            name="test_step", status=WorkflowStatus.FAILED, message="Step failed"
        )

        assert step.duration_ms is None
        assert step.details == {}
        assert step.errors == []
        assert step.warnings == []


class TestWorkflowResult:
    """Test WorkflowResult data class."""

    def test_workflow_result_creation(self):
        """Test creating a workflow result."""
        result = WorkflowResult(
            success=True, status=WorkflowStatus.SUCCESS, message="Workflow completed"
        )

        assert result.success is True
        assert result.status == WorkflowStatus.SUCCESS
        assert result.message == "Workflow completed"
        assert isinstance(result.executed_at, datetime)
        assert result.steps == []
        assert result.data == {}
        assert result.next_steps == []
        assert result.guidance == ""
        assert result.errors == []
        assert result.warnings == []

    def test_add_step(self):
        """Test adding steps to workflow result."""
        result = WorkflowResult(
            success=True, status=WorkflowStatus.SUCCESS, message="Test"
        )

        step = WorkflowStep(
            name="step1", status=WorkflowStatus.SUCCESS, message="Step 1 completed"
        )

        result.add_step(step)
        assert len(result.steps) == 1
        assert result.steps[0] == step

    def test_add_error(self):
        """Test adding errors to workflow result."""
        result = WorkflowResult(
            success=False, status=WorkflowStatus.FAILED, message="Test"
        )

        result.add_error("General error")
        assert "General error" in result.errors

    def test_add_error_with_step(self):
        """Test adding error to specific step."""
        result = WorkflowResult(
            success=False, status=WorkflowStatus.FAILED, message="Test"
        )

        step = WorkflowStep(
            name="test_step", status=WorkflowStatus.FAILED, message="Failed"
        )
        result.add_step(step)

        result.add_error("Step error", "test_step")
        assert "Step error" in result.errors
        assert "Step error" in result.steps[0].errors

    def test_add_warning(self):
        """Test adding warnings to workflow result."""
        result = WorkflowResult(
            success=True, status=WorkflowStatus.SUCCESS, message="Test"
        )

        result.add_warning("General warning")
        assert "General warning" in result.warnings

    def test_get_summary_success(self):
        """Test get_summary for successful workflow."""
        result = WorkflowResult(
            success=True,
            status=WorkflowStatus.SUCCESS,
            message="Workflow completed successfully",
        )

        # Add some steps
        for i in range(3):
            step = WorkflowStep(
                name=f"step{i}",
                status=WorkflowStatus.SUCCESS,
                message=f"Step {i} completed",
            )
            result.add_step(step)

        summary = result.get_summary()
        assert "✅" in summary
        assert "3/3" in summary
        assert "completed" in summary

    def test_get_summary_failure(self):
        """Test get_summary for failed workflow."""
        result = WorkflowResult(
            success=False, status=WorkflowStatus.FAILED, message="Workflow failed"
        )

        # Add mixed steps
        success_step = WorkflowStep("step1", WorkflowStatus.SUCCESS, "Success")
        failed_step = WorkflowStep("step2", WorkflowStatus.FAILED, "Failed")

        result.add_step(success_step)
        result.add_step(failed_step)

        summary = result.get_summary()
        assert "❌" in summary
        assert "1/2" in summary
        assert "failed" in summary

    def test_to_agent_response(self):
        """Test converting workflow result to agent response."""
        result = WorkflowResult(
            success=True,
            status=WorkflowStatus.SUCCESS,
            message="Test workflow",
            duration_ms=500,
        )

        # Add a successful step
        step = WorkflowStep("test_step", WorkflowStatus.SUCCESS, "Completed")
        result.add_step(step)

        result.next_steps = ["Next action"]
        result.guidance = "Follow these steps"
        result.data = {"key": "value"}

        agent_response = result.to_agent_response()

        assert agent_response["success"] is True
        assert agent_response["status"] == "success"
        assert agent_response["message"] == "Test workflow"
        assert agent_response["data"] == {"key": "value"}
        assert agent_response["steps_completed"] == 1
        assert agent_response["total_steps"] == 1
        assert agent_response["duration_ms"] == 500
        assert agent_response["next_steps"] == ["Next action"]
        assert agent_response["guidance"] == "Follow these steps"
        assert "summary" in agent_response


class TestWorkflowError:
    """Test WorkflowError exception class."""

    def test_workflow_error_creation(self):
        """Test creating workflow error."""
        error = WorkflowError(
            message="Test error", step_name="test_step", details={"context": "test"}
        )

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.step_name == "test_step"
        assert error.details == {"context": "test"}

    def test_workflow_error_defaults(self):
        """Test workflow error with minimal parameters."""
        error = WorkflowError("Simple error")

        assert str(error) == "Simple error"
        assert error.message == "Simple error"
        assert error.step_name is None
        assert error.details == {}


class ConcreteWorkflow(BaseWorkflow):
    """Concrete implementation of BaseWorkflow for testing."""

    def __init__(self, adr_dir):
        super().__init__(adr_dir)
        self.test_steps_executed = []

    def execute(self, should_fail=False, step_count=3):
        """Test execution method."""
        self._start_workflow("Test Workflow")

        try:
            for i in range(step_count):
                if should_fail and i == 1:
                    self._execute_step(f"failing_step_{i}", self._failing_step, i)
                else:
                    self._execute_step(f"test_step_{i}", self._successful_step, i)

            self._complete_workflow(True, "Test workflow completed successfully")

        except WorkflowError as e:
            self._complete_workflow(False, f"Test workflow failed: {e.message}")

        return self.result

    def _successful_step(self, step_index):
        """A step that always succeeds."""
        self.test_steps_executed.append(f"step_{step_index}")
        return f"result_{step_index}"

    def _failing_step(self, step_index):
        """A step that always fails."""
        raise Exception(f"Step {step_index} deliberately failed")


class TestBaseWorkflow:
    """Test BaseWorkflow abstract base class."""

    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)

    def test_workflow_initialization(self, temp_adr_dir):
        """Test workflow initialization."""
        workflow = ConcreteWorkflow(temp_adr_dir)

        assert workflow.adr_dir == Path(temp_adr_dir)
        assert workflow.result.success is False
        assert workflow.result.status == WorkflowStatus.FAILED
        assert workflow._start_time is None

    def test_successful_workflow_execution(self, temp_adr_dir):
        """Test successful workflow execution."""
        workflow = ConcreteWorkflow(temp_adr_dir)
        result = workflow.execute(should_fail=False, step_count=3)

        # Check overall result
        assert result.success is True
        assert result.status == WorkflowStatus.SUCCESS
        assert "completed successfully" in result.message
        assert result.duration_ms >= 0

        # Check steps
        assert len(result.steps) == 3
        for i, step in enumerate(result.steps):
            assert step.name == f"test_step_{i}"
            assert step.status == WorkflowStatus.SUCCESS
            assert step.duration_ms >= 0

        # Check internal tracking
        assert len(workflow.test_steps_executed) == 3
        assert workflow.test_steps_executed == ["step_0", "step_1", "step_2"]

    def test_failed_workflow_execution(self, temp_adr_dir):
        """Test workflow execution with failure."""
        workflow = ConcreteWorkflow(temp_adr_dir)
        result = workflow.execute(should_fail=True, step_count=3)

        # Check overall result
        assert result.success is False
        assert result.status == WorkflowStatus.FAILED
        assert "failed" in result.message

        # Check steps - should have 2 steps (0 success, 1 failed)
        assert len(result.steps) == 2

        # First step should be successful
        assert result.steps[0].status == WorkflowStatus.SUCCESS
        assert result.steps[0].name == "test_step_0"

        # Second step should be failed
        assert result.steps[1].status == WorkflowStatus.FAILED
        assert result.steps[1].name == "failing_step_1"
        assert "deliberately failed" in result.steps[1].message
        assert len(result.steps[1].errors) > 0

        # Only first step should have executed
        assert len(workflow.test_steps_executed) == 1
        assert workflow.test_steps_executed == ["step_0"]

    def test_workflow_step_timing(self, temp_adr_dir):
        """Test that workflow steps are timed correctly."""
        workflow = ConcreteWorkflow(temp_adr_dir)
        result = workflow.execute(should_fail=False, step_count=1)

        assert result.duration_ms >= 0
        assert result.steps[0].duration_ms >= 0

        # Workflow duration should be >= step duration
        assert result.duration_ms >= result.steps[0].duration_ms

    def test_validate_adr_directory_exists(self, temp_adr_dir):
        """Test validating existing ADR directory."""
        workflow = ConcreteWorkflow(temp_adr_dir)

        # Should not raise exception
        workflow._validate_adr_directory()

    def test_validate_adr_directory_missing(self):
        """Test validating non-existent ADR directory."""
        workflow = ConcreteWorkflow("/nonexistent/path")

        with pytest.raises(WorkflowError) as exc_info:
            workflow._validate_adr_directory()

        assert "does not exist" in str(exc_info.value)

    def test_validate_adr_directory_not_dir(self, temp_adr_dir):
        """Test validating ADR path that's not a directory."""
        # Create a file instead of directory
        file_path = Path(temp_adr_dir).parent / "not_a_dir"
        file_path.write_text("test")

        workflow = ConcreteWorkflow(str(file_path))

        with pytest.raises(WorkflowError) as exc_info:
            workflow._validate_adr_directory()

        assert "not a directory" in str(exc_info.value)

    def test_add_agent_guidance(self, temp_adr_dir):
        """Test adding agent guidance to workflow."""
        workflow = ConcreteWorkflow(temp_adr_dir)

        guidance = "Follow these steps carefully"
        next_steps = ["Step 1", "Step 2", "Step 3"]

        workflow._add_agent_guidance(guidance, next_steps)

        assert workflow.result.guidance == guidance
        assert workflow.result.next_steps == next_steps

    def test_set_workflow_data(self, temp_adr_dir):
        """Test setting workflow-specific data."""
        workflow = ConcreteWorkflow(temp_adr_dir)

        test_data = {"key1": "value1", "key2": {"nested": "value"}}

        workflow._set_workflow_data(**test_data)

        assert workflow.result.data["key1"] == "value1"
        assert workflow.result.data["key2"]["nested"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
