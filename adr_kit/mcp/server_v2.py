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
    project_path: Optional[str] = None,
    focus_areas: Optional[List[str]] = None,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    **WHEN TO USE:** Start here when user asks to "analyze project for ADRs", "identify architectural decisions", or "document existing architecture decisions".
    
    **WHAT THIS DOES:** Scans project files and generates a customized analysis prompt for you to identify architectural decisions that should become ADRs.
    
    **CALL THIS WHEN:**
    - User mentions documenting existing architecture
    - Starting ADR adoption in an established codebase  
    - User wants to identify what decisions need ADRs
    
    **BACKGROUND PROCESSING:**
    - Scans package.json, requirements.txt, Cargo.toml, etc.
    - Detects frameworks, databases, cloud services
    - Identifies existing ADR files to avoid duplicates
    - Generates project-specific analysis questions
    
    **YOUR NEXT STEPS AFTER CALLING:**
    1. Read the returned `analysis_prompt` carefully
    2. Examine the codebase following the prompt's guidance
    3. For each architectural decision you identify, call `adr_create()`
    4. Present your findings to user for confirmation before creating ADRs
    
    **PARAMETERS:**
    - project_path: Path to analyze (default: current directory)  
    - focus_areas: ["frontend", "backend", "database", "deployment"] to narrow scope
    - adr_dir: Where ADR files live (default: "docs/adr")
    
    **RETURNS:** 
    - analysis_prompt: Specific questions to guide your codebase analysis
    - project_context: Technical stack details discovered
    - guidance: Step-by-step instructions for your analysis
    """
    try:
        workflow = AnalyzeProjectWorkflow(adr_dir=adr_dir)
        
        result = workflow.execute(
            project_path=project_path or str(Path.cwd()),
            focus_areas=focus_areas or []
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
    choice: str,
    context: Optional[Dict[str, Any]] = None,
    category: Optional[str] = None,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    **WHEN TO USE:** Call BEFORE implementing any technical choice. Think of this as "asking permission" from existing architectural decisions.
    
    **WHAT THIS DOES:** Checks if your intended technical choice conflicts with existing ADRs and provides guidance on how to proceed.
    
    **CALL THIS WHEN:**
    - About to add a new dependency/library
    - Choosing database, framework, or architecture pattern  
    - User asks "can we use X technology?"
    - Before making any significant technical decision
    
    **BACKGROUND PROCESSING:**
    - Scans all approved ADRs for relevant policies
    - Checks import restrictions and architectural boundaries
    - Identifies conflicting decisions and related ADRs
    - Generates specific guidance based on conflicts found
    
    **DECISION RESPONSES:**
    - **ALLOWED**: Go ahead, no conflicts detected
    - **REQUIRES_ADR**: Choice is significant, create ADR first with `adr_create()`
    - **BLOCKED**: Conflicts with existing decisions, review alternatives
    
    **YOUR NEXT STEPS AFTER CALLING:**
    - ALLOWED: Proceed with implementation
    - REQUIRES_ADR: Call `adr_create()` to document the decision first
    - BLOCKED: Present conflicts to user, suggest alternatives from guidance
    
    **PARAMETERS:**
    - choice: Technology/pattern name (e.g., "PostgreSQL", "microservices", "React")
    - context: Additional details about intended use
    - category: Hint like "database", "frontend", "architecture" 
    - adr_dir: Where ADR files live (default: "docs/adr")
    
    **RETURNS:**
    - decision: ALLOWED/REQUIRES_ADR/BLOCKED
    - guidance: Specific next steps for your decision
    - conflicts: Any conflicting ADRs found
    - related_adrs: Relevant existing decisions
    """
    try:
        workflow = PreflightWorkflow(adr_dir=adr_dir)
        
        preflight_input = PreflightInput(
            choice=choice,
            context=context,
            category=category
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
    title: str,
    context: str,
    decision: str,
    consequences: str,
    deciders: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    policy: Optional[Dict[str, Any]] = None,
    alternatives: Optional[str] = None,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    **WHEN TO USE:** Create a new architectural decision record when making any significant technical choice.
    
    **WHAT THIS DOES:** Creates a proposed ADR file with unique ID, validates against existing decisions, and prepares for human approval.
    
    **CALL THIS WHEN:**
    - `adr_preflight()` returned "REQUIRES_ADR"
    - User makes architectural decisions (database choice, framework, patterns)
    - You identified decisions during `adr_analyze_project()`
    - User explicitly asks to document a decision
    
    **BACKGROUND PROCESSING:**
    - Auto-generates unique ADR-NNNN ID
    - Performs semantic search against existing ADRs
    - Detects conflicts with approved decisions
    - Validates MADR format and policy structure
    - Creates proposed ADR file (NOT approved yet)
    
    **CRITICAL:** ADRs start as "proposed" status. Use `adr_approve()` after human review.
    
    **YOUR NEXT STEPS AFTER CALLING:**
    1. Review any conflicts reported in the response
    2. Present the ADR file path to user for review
    3. If user approves, call `adr_approve()` with the ADR ID
    4. If conflicts exist, discuss alternatives or superseding with user
    
    **PARAMETERS:**
    - title: Clear decision title (e.g., "Use PostgreSQL for primary database")
    - context: WHY this decision is needed (problem/situation)
    - decision: WHAT was decided (the actual choice made)
    - consequences: Expected positive/negative outcomes
    - deciders: People who made the decision (optional)
    - tags: Categorization tags like ["database", "backend"] (optional)
    - policy: Enforcement rules (optional, see docs for format)
    - alternatives: Other options considered (optional)
    - adr_dir: Where ADR files live (default: "docs/adr")
    
    **RETURNS:**
    - adr_id: Generated unique ID (e.g., "ADR-0005")
    - file_path: Path to created ADR file
    - conflicts: Any conflicting ADRs detected
    - related_adrs: Similar existing ADRs found
    - next_steps: What to do next (always includes human review)
    """
    try:
        workflow = CreationWorkflow(adr_dir=adr_dir)
        
        creation_input = CreationInput(
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
            deciders=deciders,
            tags=tags,
            policy=policy,
            alternatives=alternatives
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
    adr_id: str,
    approval_notes: Optional[str] = None,
    force_approve: bool = False,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    **WHEN TO USE:** Only after human has reviewed and approved a proposed ADR. This finalizes the decision and activates all policies.
    
    **WHAT THIS DOES:** Changes ADR status to "accepted", activates all policies, and triggers automation to enforce the decision.
    
    **CALL THIS WHEN:**
    - User explicitly approves a proposed ADR
    - User says "yes, approve that ADR" or similar confirmation
    - **NEVER call without explicit human approval**
    
    **BACKGROUND PROCESSING (LOTS OF AUTOMATION):**
    - Changes ADR status from "proposed" to "accepted" 
    - Activates all policy rules defined in the ADR
    - Generates ESLint/Ruff configuration files for enforcement
    - Updates architectural constraint contracts
    - Rebuilds ADR indexes with new decision
    - Validates existing codebase against new policies
    - Creates content digest for tamper detection
    
    **CRITICAL:** This activates real policy enforcement. Only use with explicit human approval.
    
    **YOUR NEXT STEPS AFTER CALLING:**
    1. Review all automation results reported
    2. Check for any warnings or enforcement failures
    3. Inform user that policies are now active
    4. If automation failed partially, guide user on fixes needed
    
    **PARAMETERS:**
    - adr_id: The ADR ID to approve (e.g., "ADR-0005")
    - approval_notes: Human's approval comments (optional)
    - force_approve: Override conflicts/warnings (use carefully)
    - adr_dir: Where ADR files live (default: "docs/adr")
    
    **RETURNS:**
    - status: approval success/failure
    - automation_results: All automation that was triggered
    - policy_activation: Which policies are now active
    - enforcement_files: Generated config files (ESLint, Ruff, etc.)
    - warnings: Any issues encountered during automation
    - next_steps: What user should do next
    """
    try:
        workflow = ApprovalWorkflow(adr_dir=adr_dir)
        
        approval_input = ApprovalInput(
            adr_id=adr_id,
            approval_notes=approval_notes,
            force_approve=force_approve
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
    old_adr_id: str,
    new_title: str,
    new_context: str,
    new_decision: str,
    new_consequences: str,
    supersede_reason: str,
    new_deciders: Optional[List[str]] = None,
    new_tags: Optional[List[str]] = None,
    new_policy: Optional[Dict[str, Any]] = None,
    new_alternatives: Optional[str] = None,
    auto_approve: bool = False,
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    **WHEN TO USE:** Replace an existing ADR when the architectural decision has fundamentally changed.
    
    **WHAT THIS DOES:** Creates a new ADR that replaces an old one, maintaining proper relationships and optionally auto-approving.
    
    **CALL THIS WHEN:**
    - User wants to change an existing architectural decision
    - Technology choice has evolved (e.g., migrating from MySQL to PostgreSQL)
    - Original ADR no longer applies but the decision area is still relevant
    - **NOT when adding new unrelated decisions** (use `adr_create()` instead)
    
    **BACKGROUND PROCESSING:**
    - Creates new ADR with fresh ID using all the new_* parameters
    - Marks old ADR as "superseded" (but keeps it for history)
    - Creates bidirectional links: old ADR ← superseded_by → new ADR
    - Updates any other ADRs that reference the old one
    - Optionally auto-approves if auto_approve=True
    - Transfers relevant policies from old to new ADR
    
    **SUPERSEDE vs. NEW ADR:** Use supersede when replacing a decision in the same problem domain.
    
    **YOUR NEXT STEPS AFTER CALLING:**
    1. Review the relationship updates reported
    2. Check that old ADR is properly marked as superseded
    3. If auto_approve=False, call `adr_approve()` after human review
    4. Verify that dependent systems are updated to follow new decision
    
    **PARAMETERS:**
    - old_adr_id: ID of ADR being replaced (e.g., "ADR-0003")
    - new_title: Title of the replacement decision
    - new_context: WHY the replacement is needed 
    - new_decision: WHAT the new decision is
    - new_consequences: Expected outcomes of the new decision
    - supersede_reason: WHY the old ADR is being replaced
    - new_deciders: Who made the new decision (optional)
    - new_tags: Tags for the new ADR (optional)
    - new_policy: Policy rules for the new decision (optional)
    - new_alternatives: Other options considered (optional)
    - auto_approve: Automatically approve new ADR without human review
    - adr_dir: Where ADR files live (default: "docs/adr")
    
    **RETURNS:**
    - old_adr_id: The superseded ADR ID
    - new_adr_id: The new replacement ADR ID  
    - relationship_updates: What links were updated
    - approval_status: Whether new ADR was auto-approved
    - next_steps: What to do next
    """
    try:
        workflow = SupersedeWorkflow(adr_dir=adr_dir)
        
        # Convert parameters to workflow inputs
        new_proposal = CreationInput(
            title=new_title,
            context=new_context,
            decision=new_decision,
            consequences=new_consequences,
            deciders=new_deciders,
            tags=new_tags,
            policy=new_policy,
            alternatives=new_alternatives
        )
        
        supersede_input = SupersedeInput(
            old_adr_id=old_adr_id,
            new_proposal=new_proposal,
            supersede_reason=supersede_reason,
            auto_approve=auto_approve
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
    task_description: str,
    context_type: str = "implementation",
    domain_hints: Optional[List[str]] = None,
    priority_level: str = "normal",
    adr_dir: str = "docs/adr"
) -> Dict[str, Any]:
    """
    **WHEN TO USE:** Before starting any technical implementation to understand architectural constraints and get guidance.
    
    **WHAT THIS DOES:** Analyzes your task and provides relevant architectural context, constraints, and guidance from existing ADRs.
    
    **CALL THIS WHEN:**
    - About to implement a new feature or component
    - User gives you a technical task to complete
    - Need to understand architectural constraints before coding
    - Want to ensure your approach aligns with existing decisions
    - Starting refactoring or system changes
    
    **BACKGROUND PROCESSING:**
    - Analyzes your task description using semantic matching
    - Finds ADRs most relevant to your specific task
    - Extracts technology recommendations and restrictions
    - Builds a compliance checklist tailored to your task
    - Generates actionable guidance based on existing decisions
    - Creates technology "use/avoid" lists from ADR policies
    
    **PLANNING vs. PREFLIGHT:** Use this for broad planning context, use `adr_preflight()` for specific tech choices.
    
    **YOUR NEXT STEPS AFTER CALLING:**
    1. Review the relevant_adrs to understand existing decisions
    2. Follow the technology_recommendations (use/avoid lists)
    3. Apply architectural_patterns suggested for your task type
    4. Use compliance_checklist to validate your implementation
    5. If you make new significant decisions, call `adr_create()`
    
    **PARAMETERS:**
    - task_description: What you're trying to implement (be specific)
    - context_type: "implementation", "refactoring", "debugging", "feature"
    - domain_hints: Areas involved like ["frontend", "database", "api"]
    - priority_level: "low", "normal", "high" (affects detail level)
    - adr_dir: Where ADR files live (default: "docs/adr")
    
    **RETURNS:**
    - relevant_adrs: ADRs that apply to your task
    - technology_recommendations: What to use/avoid
    - architectural_patterns: Suggested patterns for your task
    - constraints: Hard restrictions from approved ADRs  
    - compliance_checklist: Steps to ensure ADR compliance
    - guidance: Specific advice for your task context
    """
    try:
        workflow = PlanningWorkflow(adr_dir=adr_dir)
        
        planning_input = PlanningInput(
            task_description=task_description,
            context_type=context_type,
            domain_hints=domain_hints,
            priority_level=priority_level
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


def run_stdio_server():
    """Run the MCP server over stdio for Cursor/Claude Code integration."""
    import asyncio
    import sys
    
    # Set up stdio transport for MCP
    async def stdio_server():
        # FastMCP automatically handles stdio when no port is specified
        await mcp.run(transport="stdio")
    
    # Ensure clean stdio handling
    try:
        asyncio.run(stdio_server())
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        sys.exit(0)


# Main server instance
def run_server():
    """Run the ADR Kit MCP Server V2."""
    mcp.run()


if __name__ == "__main__":
    run_server()