"""Internal workflow orchestration system.

This module contains the internal workflow orchestrators that are triggered by MCP entry points.
These workflows handle all the complex automation and orchestration that was previously exposed
as separate MCP tools.

Key Design Principles:
- Workflows are pure automation/orchestration (no intelligence)
- Intelligence comes only from agents calling entry points
- Each entry point triggers comprehensive internal workflows
- Workflows use existing components (contract, gate, context, guardrail systems)
- Rich status reporting guides agent next actions
"""

from .analyze import AnalyzeProjectWorkflow
from .approval import ApprovalWorkflow
from .base import BaseWorkflow, WorkflowError, WorkflowResult, WorkflowStatus
from .creation import CreationWorkflow
from .planning import PlanningWorkflow
from .preflight import PreflightWorkflow
from .supersede import SupersedeWorkflow

__all__ = [
    # Base classes
    "BaseWorkflow",
    "WorkflowResult",
    "WorkflowError",
    "WorkflowStatus",
    # Workflow implementations
    "ApprovalWorkflow",
    "CreationWorkflow",
    "PreflightWorkflow",
    "PlanningWorkflow",
    "SupersedeWorkflow",
    "AnalyzeProjectWorkflow",
]
