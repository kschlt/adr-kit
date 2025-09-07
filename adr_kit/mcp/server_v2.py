"""ADR Kit MCP Server V2 - 6 Entry Point Architecture.

This is the refactored MCP server implementing the new 6-entry-point architecture
where agents make intelligent decisions and workflows handle all automation.

Design Principles:
- Only 6 entry points for agents to call
- Each entry point triggers comprehensive internal workflows
- No intelligence in tools - only automation and orchestration
- Clear agent guidance with actionable next steps
- Rich contextual information without overwhelming complexity
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Import our new workflow system
from ..workflows.analyze import AnalyzeProjectWorkflow
from ..workflows.preflight import PreflightWorkflow, PreflightInput
from ..workflows.creation import CreationWorkflow, CreationInput
from ..workflows.approval import ApprovalWorkflow, ApprovalInput
from ..workflows.supersede import SupersedeWorkflow, SupersedeInput
from ..workflows.planning import PlanningWorkflow, PlanningInput


# Pydantic models for the new 6-entry-point MCP tools

class AnalyzeProjectRequest(BaseModel):
    """Request for analyzing existing project for ADR opportunities."""
    project_path: Optional[str] = Field(None, description="Path to project root (default: current directory)")
    focus_areas: Optional[List[str]] = Field(None, description="Specific areas to focus on (frontend, backend, database, etc.)")


class PreflightCheckRequest(BaseModel):
    """Request for checking if technical choice requires ADR."""
    choice: str = Field(..., description="Technical choice being evaluated (e.g., 'postgresql', 'react', 'microservices')")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context about the choice")
    category: Optional[str] = Field(None, description="Category hint (database, frontend, architecture, etc.)")


class CreateADRRequest(BaseModel):
    """Request for creating new ADR proposal."""
    title: str = Field(..., description="Title of the new ADR")
    context: str = Field(..., description="The problem/situation that prompted this decision")
    decision: str = Field(..., description="The architectural decision being made")
    consequences: str = Field(..., description="Expected positive and negative consequences")
    deciders: Optional[List[str]] = Field(None, description="People who made the decision")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    policy: Optional[Dict[str, Any]] = Field(None, description="Structured policy block for enforcement")
    alternatives: Optional[str] = Field(None, description="Alternative options considered")


class ApproveADRRequest(BaseModel):
    """Request for approving ADR and triggering automation."""
    adr_id: str = Field(..., description="ID of the ADR to approve")
    approval_notes: Optional[str] = Field(None, description="Human approval notes")
    force_approve: bool = Field(False, description="Override conflicts and warnings")


class SupersedeADRRequest(BaseModel):
    """Request for superseding existing ADR with new decision."""
    old_adr_id: str = Field(..., description="ID of the ADR to be superseded")
    new_proposal: CreateADRRequest = Field(..., description="New ADR proposal")
    supersede_reason: str = Field(..., description="Why the old ADR is being replaced")
    auto_approve: bool = Field(False, description="Whether to auto-approve the new ADR")


class PlanningContextRequest(BaseModel):
    """Request for architectural context for agent tasks."""
    task_description: str = Field(..., description="Description of what the agent is trying to do")
    context_type: str = Field("implementation", description="Type of task (implementation, refactoring, debugging, feature)")
    domain_hints: Optional[List[str]] = Field(None, description="Domain hints (frontend, backend, database, etc.)")
    priority_level: str = Field("normal", description="Priority level (low, normal, high) - affects detail level")


# Initialize FastMCP server
mcp = FastMCP("ADR Kit V2")


@mcp.tool()
def adr_analyze_project(
    request: AnalyzeProjectRequest, 
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    🔍 **Entry Point 1: Analyze Existing Project**
    
    Triggers agent analysis of existing codebase to identify architectural decisions
    that should be documented as ADRs. This is the starting point for existing projects
    wanting to adopt ADR governance.
    
    🎯 **AGENT INTELLIGENCE REQUIRED:**
    - Analyze codebase for architectural patterns
    - Identify significant technical decisions
    - Propose specific ADRs for each decision
    - Wait for human confirmation before creating ADRs
    
    ⚡ **INTERNAL AUTOMATION:**
    - Scans project structure and technology stack
    - Identifies existing ADRs to avoid duplication
    - Generates analysis prompt with specific guidance
    
    📋 **Agent Workflow:**
    1. Call this tool to get analysis prompt
    2. Follow the prompt to analyze the project
    3. Use adr_create() for each proposed ADR
    4. Wait for human review and approval
    
    Args:
        request: Analysis configuration
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Analysis prompt and project context for agent to act on
    """
    try:
        workflow = AnalyzeProjectWorkflow(adr_dir=adr_dir)
        
        result = workflow.execute(
            project_path=request.project_path or str(Path.cwd()),
            focus_areas=request.focus_areas or []
        )
        
        if result.status.value == "success":
            return {
                "success": True,
                "analysis_prompt": result.data["analysis_prompt"],
                "project_context": result.data["project_context"],
                "guidance": result.data["guidance"],
                "message": result.message
            }
        else:
            return {
                "success": False,
                "error": result.error.error_message if result.error else result.message,
                "message": "Failed to generate project analysis"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Project analysis failed"
        }


@mcp.tool()
def adr_preflight(
    request: PreflightCheckRequest,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    🚦 **Entry Point 2: Preflight Check**
    
    Validates technical choices against existing ADRs before implementation.
    This prevents architectural violations and guides agents toward compliant choices.
    
    🎯 **AGENT INTELLIGENCE REQUIRED:**
    - Understanding technical choice implications
    - Deciding whether to proceed, create ADR, or find alternatives
    - Interpreting conflict guidance and taking appropriate action
    
    ⚡ **INTERNAL AUTOMATION:**
    - Loads constraints contract from approved ADRs
    - Checks policy gates and existing decisions
    - Detects conflicts and related ADRs
    - Generates decision with actionable guidance
    
    📋 **Agent Workflow:**
    1. Call this before making technical choices
    2. If ALLOWED → proceed with implementation
    3. If REQUIRES_ADR → use adr_create() first
    4. If BLOCKED → review conflicts and consider alternatives
    
    Args:
        request: Technical choice to evaluate
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Decision (ALLOWED/REQUIRES_ADR/BLOCKED) with guidance and context
    """
    try:
        workflow = PreflightWorkflow(adr_dir=adr_dir)
        
        preflight_input = PreflightInput(
            choice=request.choice,
            context=request.context,
            category=request.category
        )
        
        result = workflow.execute(preflight_input)
        
        if result.status.value == "success":
            decision = result.data["decision"]
            return {
                "success": True,
                "status": decision.status,
                "reasoning": decision.reasoning,
                "next_steps": decision.next_steps,
                "urgency": decision.urgency,
                "conflicting_adrs": decision.conflicting_adrs,
                "related_adrs": decision.related_adrs,
                "guidance": result.data["guidance"],
                "message": result.message
            }
        else:
            return {
                "success": False,
                "error": result.error.error_message if result.error else result.message,
                "message": "Preflight check failed"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Preflight check failed"
        }


@mcp.tool()
def adr_create(
    request: CreateADRRequest,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    📝 **Entry Point 3: Create ADR Proposal**
    
    Creates new ADR proposal with conflict detection and validation.
    Always creates ADRs in 'proposed' status requiring human review.
    
    🎯 **AGENT INTELLIGENCE REQUIRED:**
    - Writing comprehensive ADR content (context, decision, consequences)
    - Understanding architectural implications
    - Structuring policies for enforcement
    - Responding to conflict detection results
    
    ⚡ **INTERNAL AUTOMATION:**
    - Generates unique ADR ID
    - Queries related ADRs using semantic search
    - Detects conflicts with existing decisions
    - Validates ADR structure and policy format
    - Creates MADR-formatted file
    
    📋 **Agent Workflow:**
    1. Always check adr_preflight() first
    2. Create comprehensive ADR content
    3. Include structured policy for enforceable decisions
    4. Review conflict detection results
    5. Use adr_approve() after human review
    
    Args:
        request: ADR creation data
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        ADR ID, file path, conflicts detected, and next steps guidance
    """
    try:
        workflow = CreationWorkflow(adr_dir=adr_dir)
        
        creation_input = CreationInput(
            title=request.title,
            context=request.context,
            decision=request.decision,
            consequences=request.consequences,
            deciders=request.deciders,
            tags=request.tags,
            policy=request.policy,
            alternatives=request.alternatives
        )
        
        result = workflow.execute(creation_input)
        
        if result.status.value == "success":
            creation_result = result.data["creation_result"]
            return {
                "success": True,
                "adr_id": creation_result.adr_id,
                "file_path": creation_result.file_path,
                "conflicts_detected": creation_result.conflicts_detected,
                "related_adrs": creation_result.related_adrs,
                "validation_warnings": creation_result.validation_warnings,
                "review_required": creation_result.review_required,
                "next_steps": creation_result.next_steps,
                "message": result.message
            }
        else:
            return {
                "success": False,
                "error": result.error.error_message if result.error else result.message,
                "message": "ADR creation failed"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "ADR creation failed"
        }


@mcp.tool()
def adr_approve(
    request: ApproveADRRequest,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    ✅ **Entry Point 4: Approve ADR (Trigger All Automation)**
    
    Approves ADR and triggers comprehensive automation pipeline.
    This is where all the policy enforcement and configuration updates happen.
    
    🎯 **AGENT INTELLIGENCE REQUIRED:**
    - Understanding approval workflow and its implications
    - Interpreting automation results and warnings
    - Deciding how to handle partial automation failures
    
    ⚡ **INTERNAL AUTOMATION:**
    - Updates ADR status to 'accepted'
    - Rebuilds constraints contract with new ADR
    - Applies guardrails and updates configurations
    - Generates enforcement rules (ESLint, Ruff, etc.)
    - Updates indexes and catalogs
    - Validates codebase compliance (lightweight check)
    
    📋 **Agent Workflow:**
    1. Only use after human has reviewed proposed ADR
    2. Monitor automation results for failures
    3. Review any warnings or partial failures
    4. All policies are now active and enforced
    
    Args:
        request: Approval configuration
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Comprehensive approval report with automation results and next steps
    """
    try:
        workflow = ApprovalWorkflow(adr_dir=adr_dir)
        
        approval_input = ApprovalInput(
            adr_id=request.adr_id,
            approval_notes=request.approval_notes,
            force_approve=request.force_approve
        )
        
        result = workflow.execute(approval_input)
        
        if result.status.value == "success":
            approval_result = result.data["approval_result"]
            return {
                "success": True,
                "adr_id": approval_result.adr_id,
                "previous_status": approval_result.previous_status,
                "new_status": approval_result.new_status,
                "content_digest": approval_result.content_digest,
                "policy_rules_applied": approval_result.policy_rules_applied,
                "configurations_updated": approval_result.configurations_updated,
                "warnings": approval_result.warnings,
                "next_steps": approval_result.next_steps,
                "automation_summary": result.data["full_report"]["automation_summary"],
                "policy_enforcement": result.data["full_report"]["policy_enforcement"],
                "message": result.message
            }
        else:
            return {
                "success": False,
                "error": result.error.error_message if result.error else result.message,
                "automation_results": result.error.context.get("automation_results", {}) if result.error else {},
                "message": "ADR approval failed"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "ADR approval failed"
        }


@mcp.tool()
def adr_supersede(
    request: SupersedeADRRequest,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    🔄 **Entry Point 5: Supersede ADR**
    
    Replaces existing ADR with new decision while maintaining proper relationships
    and optionally triggering approval automation.
    
    🎯 **AGENT INTELLIGENCE REQUIRED:**
    - Understanding when superseding is appropriate vs. creating new ADR
    - Writing comprehensive replacement decision
    - Deciding whether to auto-approve or require human review
    
    ⚡ **INTERNAL AUTOMATION:**
    - Creates new ADR proposal using CreationWorkflow
    - Updates old ADR status to 'superseded'
    - Maintains bidirectional relationships (supersedes/superseded_by)
    - Updates related ADR references
    - Optionally triggers ApprovalWorkflow
    
    📋 **Agent Workflow:**
    1. Use when replacing existing architectural decisions
    2. Provide clear reasoning for superseding
    3. Include comprehensive new decision content
    4. Consider auto_approve=true for minor updates
    5. Monitor relationship updates and automation results
    
    Args:
        request: Superseding configuration with old ADR ID and new proposal
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Superseding results with new ADR ID, relationship updates, and automation status
    """
    try:
        workflow = SupersedeWorkflow(adr_dir=adr_dir)
        
        # Convert request to workflow inputs
        new_proposal = CreationInput(
            title=request.new_proposal.title,
            context=request.new_proposal.context,
            decision=request.new_proposal.decision,
            consequences=request.new_proposal.consequences,
            deciders=request.new_proposal.deciders,
            tags=request.new_proposal.tags,
            policy=request.new_proposal.policy,
            alternatives=request.new_proposal.alternatives
        )
        
        supersede_input = SupersedeInput(
            old_adr_id=request.old_adr_id,
            new_proposal=new_proposal,
            supersede_reason=request.supersede_reason,
            auto_approve=request.auto_approve
        )
        
        result = workflow.execute(supersede_input)
        
        if result.status.value == "success":
            supersede_result = result.data["supersede_result"]
            return {
                "success": True,
                "old_adr_id": supersede_result.old_adr_id,
                "new_adr_id": supersede_result.new_adr_id,
                "old_adr_status": supersede_result.old_adr_status,
                "new_adr_status": supersede_result.new_adr_status,
                "relationships_updated": supersede_result.relationships_updated,
                "automation_triggered": supersede_result.automation_triggered,
                "conflicts_resolved": supersede_result.conflicts_resolved,
                "next_steps": supersede_result.next_steps,
                "message": result.message
            }
        else:
            return {
                "success": False,
                "error": result.error.error_message if result.error else result.message,
                "message": "ADR superseding failed"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "ADR superseding failed"
        }


@mcp.tool()
def adr_planning_context(
    request: PlanningContextRequest,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    🗺️ **Entry Point 6: Get Architectural Planning Context**
    
    Provides curated architectural context for agent tasks. This helps agents
    make informed decisions that align with existing architectural decisions.
    
    🎯 **AGENT INTELLIGENCE REQUIRED:**
    - Understanding task context and architectural implications
    - Following guidance prompts and compliance checklists
    - Making technology choices based on recommendations
    - Applying architectural patterns appropriately
    
    ⚡ **INTERNAL AUTOMATION:**
    - Analyzes task description to extract key concepts
    - Loads constraints contract and finds relevant ADRs
    - Ranks ADRs by relevance to the specific task
    - Generates technology recommendations and constraints
    - Creates task-specific guidance prompts
    - Builds compliance checklist for the task
    
    📋 **Agent Workflow:**
    1. Call this before starting any significant technical task
    2. Review relevant ADRs and their guidance
    3. Follow technology recommendations (use/avoid lists)
    4. Apply suggested architectural patterns
    5. Use compliance checklist to verify alignment
    6. Create new ADRs if significant decisions emerge
    
    Args:
        request: Task description and context preferences
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Curated architectural context with ADRs, constraints, guidance, and checklist
    """
    try:
        workflow = PlanningWorkflow(adr_dir=adr_dir)
        
        planning_input = PlanningInput(
            task_description=request.task_description,
            context_type=request.context_type,
            domain_hints=request.domain_hints,
            priority_level=request.priority_level
        )
        
        result = workflow.execute(planning_input)
        
        if result.status.value == "success":
            context = result.data["architectural_context"]
            return {
                "success": True,
                "relevant_adrs": context.relevant_adrs,
                "applicable_constraints": context.applicable_constraints,
                "guidance_prompts": context.guidance_prompts,
                "technology_recommendations": context.technology_recommendations,
                "architecture_patterns": context.architecture_patterns,
                "compliance_checklist": context.compliance_checklist,
                "related_decisions": context.related_decisions,
                "task_analysis": result.data["task_analysis"],
                "message": result.message
            }
        else:
            return {
                "success": False,
                "error": result.error.error_message if result.error else result.message,
                "message": "Planning context generation failed"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Planning context generation failed"
        }


# Resource for accessing ADR index (read-only data)
@mcp.resource("adr://index")
def adr_index_resource() -> str:
    """
    📚 **Resource: ADR Index**
    
    Provides read-only access to the ADR index for quick overview.
    This is supplementary data - use the 6 entry points for all actions.
    
    Returns:
        JSON index of all ADRs with metadata
    """
    try:
        from ..index.json_index import JSONIndexBuilder
        
        # Use default ADR directory
        adr_dir = "docs/adr"
        builder = JSONIndexBuilder(adr_dir=adr_dir)
        index_data = builder.build()
        
        return json.dumps(index_data, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to load ADR index: {str(e)}",
            "adrs": [],
            "metadata": {"error": True}
        }, indent=2)


# Main server instance
def run_server():
    """Run the ADR Kit MCP Server V2."""
    mcp.run()


if __name__ == "__main__":
    run_server()