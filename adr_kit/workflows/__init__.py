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

from .base import BaseWorkflow, WorkflowResult, WorkflowError, WorkflowStatus
from .approval import ApprovalWorkflow
from .creation import CreationWorkflow  
from .preflight import PreflightWorkflow
from .planning import PlanningWorkflow
from .supersede import SupersedeWorkflow
from .analyze import AnalyzeProjectWorkflow

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
    "AnalyzeProjectWorkflow"
]