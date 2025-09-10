"""Standard MCP response models for consistent tool responses."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MCPStatus(str, Enum):
    """Standard status codes for MCP responses."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    REQUIRES_ACTION = "requires_action"


class MCPResponse(BaseModel):
    """Standard successful response format for all MCP tools."""

    status: MCPStatus = MCPStatus.SUCCESS
    message: str = Field(..., description="Human-readable success message")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Tool-specific result data"
    )
    next_steps: list[str] = Field(
        default_factory=list, description="Suggested actions for agent"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class MCPErrorResponse(BaseModel):
    """Standard error response format for all MCP tools."""

    status: MCPStatus = MCPStatus.ERROR
    error: str = Field(..., description="Brief error description")
    details: str = Field(..., description="Detailed error explanation")
    suggested_action: str = Field(..., description="What the agent should try next")
    error_code: str | None = Field(None, description="Machine-readable error code")


# Request Models for Tool Parameters


class AnalyzeProjectRequest(BaseModel):
    """Parameters for analyzing existing project for ADR opportunities."""

    project_path: str | None = Field(
        None, description="Path to project root (default: current directory)"
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Specific areas to focus on (frontend, backend, database, etc.)",
    )
    adr_dir: str = Field("docs/adr", description="ADR directory path")


class PreflightCheckRequest(BaseModel):
    """Parameters for checking if technical choice requires ADR."""

    choice: str = Field(
        ...,
        description="Technical choice being evaluated (e.g., 'postgresql', 'react', 'microservices')",
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context about the choice"
    )
    category: str | None = Field(
        None, description="Category hint (database, frontend, architecture, etc.)"
    )
    adr_dir: str = Field("docs/adr", description="ADR directory path")


class CreateADRRequest(BaseModel):
    """Parameters for creating new ADR proposal."""

    title: str = Field(..., description="Title of the new ADR")
    context: str = Field(
        ..., description="The problem/situation that prompted this decision"
    )
    decision: str = Field(..., description="The architectural decision being made")
    consequences: str = Field(
        ..., description="Expected positive and negative consequences"
    )
    deciders: list[str] = Field(
        default_factory=list, description="People who made the decision"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    policy: dict[str, Any] = Field(
        default_factory=dict, description="Structured policy block for enforcement"
    )
    alternatives: str | None = Field(None, description="Alternative options considered")
    adr_dir: str = Field("docs/adr", description="ADR directory path")


class ApproveADRRequest(BaseModel):
    """Parameters for approving ADR and triggering automation."""

    adr_id: str = Field(..., description="ID of the ADR to approve")
    approval_notes: str | None = Field(None, description="Human approval notes")
    force_approve: bool = Field(False, description="Override conflicts and warnings")
    adr_dir: str = Field("docs/adr", description="ADR directory path")


class SupersedeADRRequest(BaseModel):
    """Parameters for superseding existing ADR with new decision."""

    old_adr_id: str = Field(..., description="ID of the ADR to be superseded")
    new_title: str = Field(..., description="Title of the replacement decision")
    new_context: str = Field(..., description="WHY the replacement is needed")
    new_decision: str = Field(..., description="WHAT the new decision is")
    new_consequences: str = Field(
        ..., description="Expected outcomes of the new decision"
    )
    supersede_reason: str = Field(..., description="Why the old ADR is being replaced")
    new_deciders: list[str] = Field(
        default_factory=list, description="Who made the new decision"
    )
    new_tags: list[str] = Field(
        default_factory=list, description="Tags for the new ADR"
    )
    new_policy: dict[str, Any] = Field(
        default_factory=dict, description="Policy rules for the new decision"
    )
    new_alternatives: str | None = Field(None, description="Other options considered")
    auto_approve: bool = Field(
        False, description="Automatically approve new ADR without human review"
    )
    adr_dir: str = Field("docs/adr", description="ADR directory path")


class PlanningContextRequest(BaseModel):
    """Parameters for architectural context for agent tasks."""

    task_description: str = Field(
        ..., description="Description of what the agent is trying to do"
    )
    context_type: str = Field(
        "implementation",
        description="Type of task (implementation, refactoring, debugging, feature)",
    )
    domain_hints: list[str] = Field(
        default_factory=list,
        description="Domain hints (frontend, backend, database, etc.)",
    )
    priority_level: str = Field(
        "normal",
        description="Priority level (low, normal, high) - affects detail level",
    )
    adr_dir: str = Field("docs/adr", description="ADR directory path")


# Response Data Models for Tool-Specific Data


class AnalyzeProjectData(BaseModel):
    """Data returned by adr_analyze_project tool."""

    analysis_prompt: str = Field(
        ..., description="Specific questions to guide codebase analysis"
    )
    project_context: dict[str, Any] = Field(
        ..., description="Technical stack details discovered"
    )
    existing_adrs: list[str] = Field(
        ..., description="ADRs already found in the project"
    )
    suggested_decisions: list[str] = Field(
        default_factory=list, description="Potential decisions needing ADRs"
    )


class PreflightCheckData(BaseModel):
    """Data returned by adr_preflight tool."""

    decision: str = Field(..., description="ALLOWED/REQUIRES_ADR/BLOCKED")
    reasoning: str = Field(..., description="Why this decision was made")
    conflicting_adrs: list[str] = Field(
        default_factory=list, description="ADR IDs that conflict with this choice"
    )
    related_adrs: list[str] = Field(
        default_factory=list, description="ADR IDs that are related but don't conflict"
    )
    urgency: str = Field("MEDIUM", description="Priority level (LOW/MEDIUM/HIGH)")


class CreateADRData(BaseModel):
    """Data returned by adr_create tool."""

    adr_id: str = Field(..., description="Generated unique ID (e.g., 'ADR-0005')")
    file_path: str = Field(..., description="Path to created ADR file")
    status: str = Field("proposed", description="Always 'proposed' (requires approval)")
    conflicts: list[str] = Field(
        default_factory=list, description="Any conflicting ADRs detected"
    )
    related_adrs: list[str] = Field(
        default_factory=list, description="Similar existing ADRs found"
    )
    validation_warnings: list[str] = Field(
        default_factory=list, description="Validation warnings if any"
    )


class ApproveADRData(BaseModel):
    """Data returned by adr_approve tool."""

    adr_id: str = Field(..., description="The approved ADR ID")
    status: str = Field(
        "approved", description="Always 'approved' after successful approval"
    )
    policies_activated: list[str] = Field(
        default_factory=list, description="List of policy rules now active"
    )
    configurations_updated: list[str] = Field(
        default_factory=list, description="Config files that were updated"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Any issues encountered during automation"
    )


class SupersedeADRData(BaseModel):
    """Data returned by adr_supersede tool."""

    old_adr_id: str = Field(..., description="The superseded ADR ID")
    new_adr_id: str = Field(..., description="The new replacement ADR ID")
    old_status: str = Field(..., description="Status of the old ADR (now 'superseded')")
    new_status: str = Field(
        ..., description="Status of the new ADR (usually 'proposed')"
    )
    relationships_updated: list[str] = Field(
        default_factory=list, description="What links were updated"
    )


class PlanningContextData(BaseModel):
    """Data returned by adr_planning_context tool."""

    relevant_adrs: list[dict[str, Any]] = Field(
        default_factory=list, description="ADRs that apply to your task"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Hard restrictions from approved ADRs"
    )
    guidance: str = Field("", description="Specific advice for your task context")
    use_technologies: list[str] = Field(
        default_factory=list, description="Technologies recommended for your task"
    )
    avoid_technologies: list[str] = Field(
        default_factory=list, description="Technologies to avoid based on ADRs"
    )
    patterns: list[str] = Field(
        default_factory=list,
        description="Architectural patterns suggested for your task",
    )
    checklist: list[str] = Field(
        default_factory=list, description="Steps to ensure ADR compliance"
    )


# Helper functions for creating responses


def success_response(
    message: str,
    data: dict[str, Any] | BaseModel,
    next_steps: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a standard success response."""
    if isinstance(data, BaseModel):
        data = data.model_dump()

    response = MCPResponse(
        message=message, data=data, next_steps=next_steps or [], metadata=metadata or {}
    )
    return response.model_dump()


def error_response(
    error: str, details: str, suggested_action: str, error_code: str | None = None
) -> dict[str, Any]:
    """Create a standard error response."""
    response = MCPErrorResponse(
        error=error,
        details=details,
        suggested_action=suggested_action,
        error_code=error_code,
    )
    return response.model_dump()
