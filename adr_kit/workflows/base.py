"""Base classes for internal workflow orchestration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class WorkflowStatus(str, Enum):
    """Status of workflow execution."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"  # Some steps succeeded, some failed
    FAILED = "failed"
    VALIDATION_ERROR = "validation_error"
    CONFLICT_ERROR = "conflict_error"


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow."""

    name: str
    status: WorkflowStatus
    message: str
    duration_ms: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    """Result of workflow execution."""

    success: bool
    status: WorkflowStatus
    message: str

    # Execution details
    steps: list[WorkflowStep] = field(default_factory=list)
    duration_ms: int = 0
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Output data (workflow-specific)
    data: dict[str, Any] = field(default_factory=dict)

    # Agent guidance
    next_steps: list[str] = field(default_factory=list)
    guidance: str = ""

    # Error handling
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_step(self, step: WorkflowStep) -> None:
        """Add a workflow step result."""
        self.steps.append(step)

    def add_error(self, error: str, step_name: str | None = None) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        if step_name:
            # Also add to the specific step if it exists
            for step in self.steps:
                if step.name == step_name:
                    step.errors.append(error)
                    break

    def add_warning(self, warning: str, step_name: str | None = None) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)
        if step_name:
            for step in self.steps:
                if step.name == step_name:
                    step.warnings.append(warning)
                    break

    def get_summary(self) -> str:
        """Get human-readable summary of workflow execution."""
        if self.success:
            successful_steps = len(
                [s for s in self.steps if s.status == WorkflowStatus.SUCCESS]
            )
            return f"✅ {self.message} ({successful_steps}/{len(self.steps)} steps completed)"
        else:
            failed_steps = len(
                [s for s in self.steps if s.status == WorkflowStatus.FAILED]
            )
            return f"❌ {self.message} ({failed_steps}/{len(self.steps)} steps failed)"

    def to_agent_response(self) -> dict[str, Any]:
        """Convert to agent-friendly response format."""
        return {
            "success": self.success,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "steps_completed": len(
                [s for s in self.steps if s.status == WorkflowStatus.SUCCESS]
            ),
            "total_steps": len(self.steps),
            "duration_ms": self.duration_ms,
            "next_steps": self.next_steps,
            "guidance": self.guidance,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": self.get_summary(),
        }


class WorkflowError(Exception):
    """Exception raised during workflow execution."""

    def __init__(
        self,
        message: str,
        step_name: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.step_name = step_name
        self.details = details or {}


class BaseWorkflow(ABC):
    """Base class for all internal workflows.

    Workflows are pure automation/orchestration that use existing components
    to accomplish complex tasks triggered by agent entry points.
    """

    def __init__(self, adr_dir: Path | str):
        self.adr_dir = Path(adr_dir)
        self.result = WorkflowResult(
            success=False, status=WorkflowStatus.FAILED, message=""
        )
        self._start_time: datetime | None = None

    @abstractmethod
    def execute(self, **kwargs: Any) -> WorkflowResult:
        """Execute the workflow with given parameters.

        This is the main entry point that agents call through MCP tools.
        Implementations should:
        1. Validate inputs
        2. Execute workflow steps in sequence
        3. Handle errors gracefully
        4. Return comprehensive results with agent guidance
        """
        pass

    def _start_workflow(self, workflow_name: str) -> None:
        """Initialize workflow execution."""
        self._start_time = datetime.now()
        self.result = WorkflowResult(
            success=False,
            status=WorkflowStatus.FAILED,
            message=f"{workflow_name} workflow started",
        )

    def _complete_workflow(
        self, success: bool, message: str, status: WorkflowStatus | None = None
    ) -> None:
        """Complete workflow execution."""
        if self._start_time:
            duration_ms = int(
                (datetime.now() - self._start_time).total_seconds() * 1000
            )
            self.result.duration_ms = self._ensure_minimum_duration(duration_ms)
        else:
            # Fallback: use a minimal duration if start time wasn't set
            self.result.duration_ms = 1

        self.result.success = success
        self.result.message = message

        if status:
            self.result.status = status
        else:
            self.result.status = (
                WorkflowStatus.SUCCESS if success else WorkflowStatus.FAILED
            )

    def _ensure_minimum_duration(self, duration_ms: int) -> int:
        """Ensure duration is at least 1ms for consistent timing."""
        return max(duration_ms, 1)

    def _execute_step(
        self, step_name: str, step_func: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Execute a single workflow step with error handling."""
        start_time = datetime.now()
        step = WorkflowStep(
            name=step_name, status=WorkflowStatus.FAILED, message="Step started"
        )

        try:
            result = step_func(*args, **kwargs)

            step.status = WorkflowStatus.SUCCESS
            step.message = f"{step_name} completed successfully"
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            step.duration_ms = self._ensure_minimum_duration(duration_ms)

            self.result.add_step(step)
            return result

        except Exception as e:
            step.status = WorkflowStatus.FAILED
            step.message = f"{step_name} failed: {str(e)}"
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            step.duration_ms = self._ensure_minimum_duration(duration_ms)
            step.errors.append(str(e))

            self.result.add_step(step)
            raise WorkflowError(
                f"{step_name} failed: {str(e)}", step_name, {"exception": str(e)}
            ) from e

    def _validate_adr_directory(self) -> None:
        """Validate that ADR directory exists and is accessible."""
        if not self.adr_dir.exists():
            raise WorkflowError(f"ADR directory does not exist: {self.adr_dir}")

        if not self.adr_dir.is_dir():
            raise WorkflowError(f"ADR path is not a directory: {self.adr_dir}")

        # Check if we can write to the directory
        try:
            test_file = self.adr_dir / ".adr_kit_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise WorkflowError(
                f"Cannot write to ADR directory: {self.adr_dir} - {e}"
            ) from e

    def _add_agent_guidance(self, guidance: str, next_steps: list[str]) -> None:
        """Add guidance for the agent on what to do next."""
        self.result.guidance = guidance
        self.result.next_steps = next_steps

    def _set_workflow_data(self, **data: Any) -> None:
        """Set workflow-specific output data."""
        self.result.data.update(data)
