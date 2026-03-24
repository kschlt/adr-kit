"""Workflow orchestration — shim for backward compatibility."""

from adr_kit.decision.workflows.analyze import AnalyzeProjectWorkflow
from adr_kit.decision.workflows.approval import ApprovalWorkflow
from adr_kit.decision.workflows.base import (
    BaseWorkflow,
    WorkflowError,
    WorkflowResult,
    WorkflowStatus,
)
from adr_kit.decision.workflows.creation import CreationWorkflow
from adr_kit.decision.workflows.preflight import PreflightWorkflow
from adr_kit.decision.workflows.supersede import SupersedeWorkflow

from .planning import PlanningWorkflow

__all__ = [
    "BaseWorkflow",
    "WorkflowResult",
    "WorkflowError",
    "WorkflowStatus",
    "ApprovalWorkflow",
    "CreationWorkflow",
    "PreflightWorkflow",
    "PlanningWorkflow",
    "SupersedeWorkflow",
    "AnalyzeProjectWorkflow",
]
