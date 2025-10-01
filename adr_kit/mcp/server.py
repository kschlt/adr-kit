"""ADR Kit MCP Server - Agent-First Interface with Full Workflow Backend.

This is the proper MCP server that provides clean agent-friendly interfaces
while preserving all the sophisticated workflow automation and business logic.
"""

import logging
from typing import Any

from fastmcp import FastMCP

# Import the full workflow system (this is where the real business logic lives)
from ..workflows.analyze import AnalyzeProjectWorkflow
from ..workflows.approval import ApprovalInput, ApprovalWorkflow
from ..workflows.creation import CreationInput, CreationWorkflow
from ..workflows.planning import PlanningInput, PlanningWorkflow
from ..workflows.preflight import PreflightInput, PreflightWorkflow
from ..workflows.supersede import SupersedeInput, SupersedeWorkflow
from .models import (
    AnalyzeProjectRequest,
    ApproveADRRequest,
    CreateADRRequest,
    PlanningContextRequest,
    PreflightCheckRequest,
    SupersedeADRRequest,
    error_response,
    success_response,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server with proper name
mcp = FastMCP("ADR Kit")


@mcp.tool()
def adr_analyze_project(request: AnalyzeProjectRequest) -> dict[str, Any]:
    """
    Analyze existing project for ADR opportunities.

    WHEN TO USE: Starting ADR adoption in established codebase.
    RETURNS: Project analysis with suggested architectural decisions.
    """
    try:
        logger.info(f"Analyzing project: {request.project_path}")

        # Use the full workflow system (preserves all business logic)
        workflow = AnalyzeProjectWorkflow(adr_dir=request.adr_dir)
        result = workflow.execute(
            project_path=request.project_path, focus_areas=request.focus_areas
        )

        if result.success:
            return success_response(
                message=result.message,
                data=result.data,
                next_steps=result.next_steps,
                metadata={"duration_ms": result.duration_ms},
            )
        else:
            return error_response(
                error="Project analysis failed",
                details=result.errors[0] if result.errors else result.message,
                suggested_action="Check project path and permissions, then retry",
                error_code="ANALYSIS_FAILED",
            )

    except Exception as e:
        logger.error(f"Analyze project error: {e}")
        return error_response(
            error="Analysis failed",
            details=str(e),
            suggested_action="Verify project path exists and is accessible",
            error_code="ANALYSIS_ERROR",
        )


@mcp.tool()
def adr_preflight(request: PreflightCheckRequest) -> dict[str, Any]:
    """
    Check if technical choice requires ADR before proceeding.

    WHEN TO USE: Before implementing any technical choice.
    RETURNS: ALLOWED/REQUIRES_ADR/BLOCKED with guidance.
    """
    try:
        logger.info(f"Preflight check for: {request.choice}")

        # Use the full workflow system
        workflow = PreflightWorkflow(adr_dir=request.adr_dir)
        preflight_input = PreflightInput(
            choice=request.choice, context=request.context, category=request.category
        )

        result = workflow.execute(input_data=preflight_input)

        if result.success:
            decision = result.data["decision"]
            return success_response(
                message=f"Preflight check completed: {decision.status}",
                data={
                    "decision": decision.status,
                    "reasoning": decision.reasoning,
                    "next_steps": decision.next_steps,
                    "conflicting_adrs": decision.conflicting_adrs,
                    "related_adrs": decision.related_adrs,
                    "urgency": decision.urgency,
                },
                next_steps=(
                    [decision.next_steps]
                    if isinstance(decision.next_steps, str)
                    else decision.next_steps
                ),
                metadata={"choice": request.choice, "category": request.category},
            )
        else:
            return error_response(
                error="Preflight check failed",
                details=result.errors[0] if result.errors else result.message,
                suggested_action="Check ADR directory exists and contains valid ADRs",
                error_code="PREFLIGHT_FAILED",
            )

    except Exception as e:
        logger.error(f"Preflight check error: {e}")
        return error_response(
            error="Preflight check failed",
            details=str(e),
            suggested_action="Verify technical choice name and ADR directory",
            error_code="PREFLIGHT_ERROR",
        )


@mcp.tool()
def adr_create(request: CreateADRRequest) -> dict[str, Any]:
    """
    Create a new architectural decision record.

    WHEN TO USE: Document significant technical decisions.
    RETURNS: Created ADR details in 'proposed' status.
    """
    try:
        logger.info(f"Creating ADR: {request.title}")

        # Use the full workflow system
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

        if result.success:
            creation_result = result.data["creation_result"]
            return success_response(
                message=f"ADR {creation_result.adr_id} created successfully",
                data={
                    "adr_id": creation_result.adr_id,
                    "file_path": str(creation_result.file_path),
                    "status": "proposed",
                    "conflicts": creation_result.conflicts_detected,
                    "related_adrs": creation_result.related_adrs,
                    "validation_warnings": creation_result.validation_warnings,
                },
                next_steps=(
                    [creation_result.next_steps]
                    if isinstance(creation_result.next_steps, str)
                    else creation_result.next_steps
                ),
                metadata={"adr_id": creation_result.adr_id},
            )
        else:
            return error_response(
                error="ADR creation failed",
                details=result.errors[0] if result.errors else result.message,
                suggested_action="Check all required fields are provided and ADR directory is writable",
                error_code="CREATE_FAILED",
            )

    except Exception as e:
        logger.error(f"ADR creation error: {e}")
        return error_response(
            error="ADR creation failed",
            details=str(e),
            suggested_action="Verify ADR directory exists and is writable",
            error_code="CREATE_ERROR",
        )


@mcp.tool()
def adr_approve(request: ApproveADRRequest) -> dict[str, Any]:
    """
    Approve ADR and activate policies.

    WHEN TO USE: Only after explicit human approval.
    RETURNS: Approval results with activated policies.
    """
    try:
        logger.info(f"Approving ADR: {request.adr_id}")

        # Use the full workflow system (includes all policy automation)
        workflow = ApprovalWorkflow(adr_dir=request.adr_dir)
        approval_input = ApprovalInput(
            adr_id=request.adr_id,
            approval_notes=request.approval_notes,
            force_approve=request.force_approve,
        )

        result = workflow.execute(input_data=approval_input)

        if result.success:
            approval_result = result.data["approval_result"]
            return success_response(
                message=f"ADR {approval_result.adr_id} approved and policies activated",
                data={
                    "adr_id": approval_result.adr_id,
                    "status": "approved",
                    "policies_activated": approval_result.policy_rules_applied,
                    "configurations_updated": approval_result.configurations_updated,
                    "warnings": approval_result.warnings,
                },
                next_steps=(
                    [approval_result.next_steps]
                    if isinstance(approval_result.next_steps, str)
                    else approval_result.next_steps
                ),
                metadata={"adr_id": request.adr_id},
            )
        else:
            return error_response(
                error="ADR approval failed",
                details=result.errors[0] if result.errors else result.message,
                suggested_action="Check ADR ID exists and is in 'proposed' status",
                error_code="APPROVAL_FAILED",
            )

    except Exception as e:
        logger.error(f"ADR approval error: {e}")
        return error_response(
            error="ADR approval failed",
            details=str(e),
            suggested_action="Verify ADR exists and you have write permissions",
            error_code="APPROVAL_ERROR",
        )


@mcp.tool()
def adr_supersede(request: SupersedeADRRequest) -> dict[str, Any]:
    """
    Replace existing ADR with new decision.

    WHEN TO USE: Architectural decision has fundamentally changed.
    RETURNS: Old and new ADR details with relationship updates.
    """
    try:
        logger.info(f"Superseding ADR: {request.old_adr_id}")

        # Use the full workflow system
        workflow = SupersedeWorkflow(adr_dir=request.adr_dir)

        # Convert request to workflow inputs
        new_proposal = CreationInput(
            title=request.new_title,
            context=request.new_context,
            decision=request.new_decision,
            consequences=request.new_consequences,
            deciders=request.new_deciders,
            tags=request.new_tags,
            policy=request.new_policy,
            alternatives=request.new_alternatives,
        )

        supersede_input = SupersedeInput(
            old_adr_id=request.old_adr_id,
            new_proposal=new_proposal,
            supersede_reason=request.supersede_reason,
            auto_approve=request.auto_approve,
        )

        result = workflow.execute(input_data=supersede_input)

        if result.success:
            supersede_result = result.data["supersede_result"]
            return success_response(
                message=f"Successfully superseded {supersede_result.old_adr_id} with {supersede_result.new_adr_id}",
                data={
                    "old_adr_id": supersede_result.old_adr_id,
                    "new_adr_id": supersede_result.new_adr_id,
                    "old_status": supersede_result.old_adr_status,
                    "new_status": supersede_result.new_adr_status,
                    "relationships_updated": supersede_result.relationships_updated,
                },
                next_steps=(
                    [supersede_result.next_steps]
                    if isinstance(supersede_result.next_steps, str)
                    else supersede_result.next_steps
                ),
                metadata={
                    "old_adr": request.old_adr_id,
                    "new_adr": supersede_result.new_adr_id,
                },
            )
        else:
            return error_response(
                error="Supersede failed",
                details=result.errors[0] if result.errors else result.message,
                suggested_action="Check that the old ADR ID exists and new ADR details are valid",
                error_code="SUPERSEDE_FAILED",
            )

    except Exception as e:
        logger.error(f"Supersede error: {e}")
        return error_response(
            error="Supersede failed",
            details=str(e),
            suggested_action="Verify the old ADR exists and new ADR details are valid",
            error_code="SUPERSEDE_ERROR",
        )


@mcp.tool()
def adr_planning_context(request: PlanningContextRequest) -> dict[str, Any]:
    """
    Get architectural context for agent tasks.

    WHEN TO USE: Before implementing features to understand constraints.
    RETURNS: Relevant ADRs, constraints, and guidance for your task.
    """
    try:
        logger.info(f"Getting planning context for: {request.task_description}")

        # Use the full workflow system
        workflow = PlanningWorkflow(adr_dir=request.adr_dir)
        planning_input = PlanningInput(
            task_description=request.task_description,
            context_type=request.context_type,
            domain_hints=request.domain_hints,
            priority_level=request.priority_level,
        )

        result = workflow.execute(input_data=planning_input)

        if result.success:
            context = result.data["architectural_context"]
            return success_response(
                message=f"Planning context provided with {len(context.relevant_adrs)} relevant ADRs",
                data={
                    "relevant_adrs": context.relevant_adrs,
                    "constraints": context.applicable_constraints,
                    "guidance": context.guidance_prompts,
                    "use_technologies": context.technology_recommendations.get(
                        "use", []
                    ),
                    "avoid_technologies": context.technology_recommendations.get(
                        "avoid", []
                    ),
                    "patterns": context.architecture_patterns,
                    "checklist": context.compliance_checklist,
                    "related_decisions": context.related_decisions,
                },
                next_steps=[
                    "Review relevant ADRs before implementation",
                    "Follow technology recommendations",
                    "Create new ADRs for significant decisions",
                ],
                metadata={
                    "task": request.task_description,
                    "context_type": request.context_type,
                    "relevant_count": len(context.relevant_adrs),
                },
            )
        else:
            return error_response(
                error="Planning context failed",
                details=result.errors[0] if result.errors else result.message,
                suggested_action="Provide a clear task description and verify ADR directory exists",
                error_code="PLANNING_FAILED",
            )

    except Exception as e:
        logger.error(f"Planning context error: {e}")
        return error_response(
            error="Planning context failed",
            details=str(e),
            suggested_action="Check task description format and ADR directory access",
            error_code="PLANNING_ERROR",
        )


# Resource for ADR index (proper structured data)
@mcp.resource("adr://index")
def adr_index_resource() -> dict[str, Any]:
    """
    Read-only access to ADR index with structured data.
    """
    try:
        from ..index.json_index import generate_adr_index

        # Use default ADR directory
        adr_dir = "docs/adr"
        adr_index = generate_adr_index(adr_directory=adr_dir, validate=False)
        index_data = adr_index.to_dict()

        return index_data  # Return structured data, not JSON string

    except Exception as e:
        logger.error(f"ADR index resource failed: {e}")
        return {
            "error": f"Failed to load ADR index: {str(e)}",
            "adrs": [],
            "metadata": {"error": True},
        }


def run_stdio_server() -> None:
    """Run the MCP server over stdio for agent integration."""
    import sys

    try:
        logger.info("Starting ADR Kit MCP Server with full workflow backend")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        sys.exit(1)


def run_server() -> None:
    """Main entry point for the MCP server."""
    run_stdio_server()


if __name__ == "__main__":
    run_server()
