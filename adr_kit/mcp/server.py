"""MCP server for ADR Kit using FastMCP.

Design decisions:
- Use FastMCP for modern MCP server implementation
- Expose all tools specified in 05_MCP_SPEC.md
- Provide both tools (actions) and resources (data access)
- Handle errors gracefully with clear messages for coding agents
- Rich contextual descriptions for autonomous AI agent operation
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..core.model import ADR, ADRFrontMatter, ADRStatus, PolicyModel
from ..core.parse import find_adr_files, parse_adr_file, ParseError
from ..core.validate import validate_adr_file, validate_adr_directory
from ..core.policy_extractor import PolicyExtractor
from ..core.immutability import ImmutabilityManager
from ..semantic.retriever import SemanticIndex
from ..guard.detector import GuardSystem, PolicyViolation, CodeAnalysisResult
from ..index.json_index import generate_adr_index, ADRIndex
from ..index.sqlite_index import generate_sqlite_index, ADRSQLiteIndex
from ..enforce.eslint import generate_eslint_config, StructuredESLintGenerator
from ..enforce.ruff import generate_ruff_config, generate_import_linter_config
from ..contract import ConstraintsContractBuilder, ContractBuildError
from ..gate import PolicyGate, GateDecision, TechnicalChoice, create_technical_choice
from ..context import PlanningContext, PlanningConfig, TaskHint


# Pydantic models for MCP tool parameters

class ADRCreatePayload(BaseModel):
    """Payload for creating a new ADR."""
    title: str = Field(..., description="Title of the new ADR")
    tags: Optional[List[str]] = Field(None, description="Tags for the ADR")
    deciders: Optional[List[str]] = Field(None, description="People who made the decision")
    status: Optional[ADRStatus] = Field(ADRStatus.PROPOSED, description="Initial status")
    policy: Optional[PolicyModel] = Field(None, description="Structured policy for enforcement")
    content: Optional[str] = Field(None, description="Custom content for the ADR")


class ADRSupersedePayload(BaseModel):
    """Payload for superseding an ADR."""
    old_id: str = Field(..., description="ID of the ADR to supersede")
    payload: ADRCreatePayload = Field(..., description="Data for the new ADR")


class ADRValidateRequest(BaseModel):
    """Request for ADR validation."""
    id: Optional[str] = Field(None, description="Specific ADR ID to validate")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRIndexRequest(BaseModel):
    """Request for ADR indexing."""
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRExportLintRequest(BaseModel):
    """Request for lint config export."""
    framework: str = Field(..., description="Lint framework (eslint, ruff, import-linter)")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRSemanticIndexRequest(BaseModel):
    """Request for semantic index building."""
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")
    force_rebuild: Optional[bool] = Field(False, description="Force complete rebuild")


class ADRSemanticMatchRequest(BaseModel):
    """Request for semantic matching."""
    text: str = Field(..., description="Query text for semantic matching")
    k: Optional[int] = Field(5, description="Number of results to return")
    filter_status: Optional[List[str]] = Field(None, description="Filter by ADR status")


class ADRGuardRequest(BaseModel):
    """Request for ADR policy guard analysis of code changes."""
    diff_text: str = Field(..., description="Git diff output to analyze for policy violations")
    build_index: bool = Field(True, description="Whether to rebuild the semantic index before analysis")


class ADRContractRequest(BaseModel):
    """Request for constraints contract operations."""
    force_rebuild: Optional[bool] = Field(False, description="Force rebuild contract from scratch")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRContractValidateRequest(BaseModel):
    """Request for validating a policy against the current contract."""
    policy: dict = Field(..., description="Policy data to validate")
    adr_id: str = Field(..., description="ADR ID for the policy being validated")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRPreflightRequest(BaseModel):
    """Request for preflight evaluation of a technical choice."""
    choice_name: str = Field(..., description="Name of the technical choice (e.g., 'react', 'axios')")
    context: str = Field(..., description="Context or reason for this choice")
    choice_type: Optional[str] = Field("dependency", description="Type of choice: dependency, framework, tool, etc.")
    ecosystem: Optional[str] = Field("npm", description="Package ecosystem (npm, pypi, gem, etc.)")
    is_dev_dependency: Optional[bool] = Field(False, description="Whether this is a development dependency")
    alternatives_considered: Optional[List[str]] = Field(None, description="Other options that were considered")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRPreflightBulkRequest(BaseModel):
    """Request for bulk preflight evaluation of multiple choices."""
    choices: List[Dict[str, Any]] = Field(..., description="List of technical choices to evaluate")
    context: str = Field(..., description="Overall context for these choices")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRGateConfigRequest(BaseModel):
    """Request for gate configuration operations."""
    action: str = Field(..., description="Action: 'get', 'update', 'reset'")
    config_updates: Optional[Dict[str, Any]] = Field(None, description="Configuration updates")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRPlanningContextRequest(BaseModel):
    """Request for planning context generation."""
    task_description: str = Field(..., description="What the agent is trying to accomplish")
    changed_files: Optional[List[str]] = Field(None, description="Files being modified")
    technologies_mentioned: Optional[List[str]] = Field(None, description="Technologies mentioned in task")
    task_type: Optional[str] = Field(None, description="Type of task: feature, bugfix, refactor, etc.")
    priority: Optional[str] = Field("medium", description="Task priority: low, medium, high, critical")
    max_relevant_adrs: Optional[int] = Field(5, description="Maximum number of relevant ADRs to include")
    max_tokens: Optional[int] = Field(800, description="Maximum token budget for context packet")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


class ADRPlanningBulkRequest(BaseModel):
    """Request for bulk planning context generation."""
    tasks: List[Dict[str, Any]] = Field(..., description="List of task descriptions and metadata")
    adr_dir: Optional[str] = Field("docs/adr", description="ADR directory")


def load_adr_template() -> str:
    """Load the standard ADR template."""
    template_path = Path(__file__).parent.parent.parent / "VersionV3" / "templates" / "adr_template.md"
    
    if template_path.exists():
        # Load the actual template content (without front-matter)
        content = template_path.read_text(encoding='utf-8')
        # Extract only the content part (after ---)
        if '---' in content:
            parts = content.split('---', 2)
            if len(parts) >= 3:
                return parts[2].strip()
    
    # Fallback template matching your V3 spec
    return """## Context

## Decision

## Consequences

## Alternatives"""


# Initialize FastMCP server
mcp = FastMCP("ADR Kit")


@mcp.tool()
def adr_create(payload: ADRCreatePayload, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Create a new ADR when architectural decisions are identified.
    
    🎯 WHEN TO USE:
    - User mentions switching technologies (e.g., "use PostgreSQL instead of MySQL")  
    - Code analysis reveals architectural patterns needing documentation
    - New technical decisions are made that affect system design
    - You identify decisions that should be formally recorded
    
    🔄 WORKFLOW:
    1. ALWAYS check existing ADRs first using adr_query_related() 
    2. Create ADR with status 'proposed' for human review
    3. Auto-populate technical context based on conversation/codebase
    4. Include structured policy if enforceable decisions detected
    5. Identify potential superseding relationships with existing ADRs
    6. Notify human with file path for review
    
    ⚡ AUTOMATICALLY HANDLES:
    - Unique ID generation (ADR-NNNN format)
    - Date stamping 
    - MADR template structure
    - Schema and policy validation
    
    💡 POLICY INTEGRATION:
    - Include structured policy for library/framework decisions
    - Auto-detect import restrictions from conversation context
    - Generate enforcement-ready rules for accepted ADRs
    - Support ESLint, Ruff, and import-linter generation
    
    📋 Args:
        payload: ADR creation data with title, tags, deciders, content, and policy
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Dictionary with success status, ADR ID, file path, policy validation, and next steps
    """
    try:
        adr_path = Path(adr_dir)
        adr_path.mkdir(parents=True, exist_ok=True)
        
        # Get next ADR ID
        adr_files = find_adr_files(adr_path)
        max_num = 0
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.id.startswith("ADR-"):
                    num_str = adr.front_matter.id[4:]
                    if num_str.isdigit():
                        max_num = max(max_num, int(num_str))
            except ParseError:
                continue
        
        new_id = f"ADR-{max_num + 1:04d}"
        
        # Create front matter with policy support
        front_matter = ADRFrontMatter(
            id=new_id,
            title=payload.title,
            status=payload.status or ADRStatus.PROPOSED,
            date=date.today(),
            tags=payload.tags,
            deciders=payload.deciders,
            policy=payload.policy
        )
        
        # Use provided content or load from template
        if payload.content:
            content = payload.content
        else:
            content = load_adr_template()
        
        # Create ADR object and validate policy
        adr = ADR(front_matter=front_matter, content=content)
        
        # Policy validation and enhancement
        policy_extractor = PolicyExtractor()
        extracted_policy = policy_extractor.extract_policy(adr)
        policy_validation = []
        
        if payload.policy or policy_extractor.has_extractable_policy(adr):
            policy_validation.extend(policy_extractor.validate_policy_completeness(adr))
        
        filename = f"{new_id}-{payload.title.lower().replace(' ', '-')}.md"
        file_path = adr_path / filename
        
        file_path.write_text(adr.to_markdown(), encoding='utf-8')
        
        # Enhanced response with policy information
        response = {
            "success": True,
            "id": new_id,
            "path": str(file_path),
            "status": "proposed",
            "message": f"📝 Created ADR {new_id}: {payload.title}",
            "next_steps": f"Please review the ADR at {file_path} and use adr_approve() to accept it or provide feedback for modifications.",
            "workflow_stage": "awaiting_human_review"
        }
        
        # Add policy information if present
        if extracted_policy and (extracted_policy.imports or extracted_policy.boundaries or extracted_policy.python):
            response["policy_detected"] = True
            response["policy_summary"] = {
                "imports": bool(extracted_policy.imports),
                "boundaries": bool(extracted_policy.boundaries), 
                "python": bool(extracted_policy.python)
            }
            response["enforcement_ready"] = not bool(policy_validation)
            if not policy_validation:
                response["lint_generation_tip"] = f"After approval, use adr_export_lint_config() to generate enforcement rules"
        
        if policy_validation:
            response["policy_warnings"] = policy_validation
        
        return response
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create ADR: {e}"
        }


@mcp.tool()
def adr_query_related(topic: str, tags: Optional[List[str]] = None, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Query existing ADRs related to a topic or decision area.
    
    🎯 WHEN TO USE:
    - BEFORE creating any new ADR (mandatory first step)
    - When user mentions architectural changes
    - To detect potential conflicts with existing decisions
    - To understand current architectural landscape
    
    🔍 WHAT IT FINDS:
    - ADRs with similar topics, tags, or content
    - Potentially conflicting decisions
    - Related architectural choices that might be affected
    - Dependencies and relationships
    
    💡 USE RESULTS TO:
    - Identify ADRs that might need superseding
    - Understand existing context for new decisions  
    - Detect conflicts before they occur
    - Inform content of new ADRs
    
    📋 Args:
        topic: Keywords describing the decision area (e.g., "database", "frontend framework")
        tags: Optional specific tags to filter by
        adr_dir: Directory containing ADRs
        
    Returns:
        Dictionary with matching ADRs and conflict analysis
    """
    try:
        # Find and parse all ADRs
        adr_files = find_adr_files(Path(adr_dir))
        related_adrs = []
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if not adr:
                    continue
                
                # Check if ADR is related to topic
                is_related = False
                relevance_score = 0
                reasons = []
                
                # Check title and content for topic keywords
                topic_lower = topic.lower()
                if topic_lower in adr.front_matter.title.lower():
                    is_related = True
                    relevance_score += 3
                    reasons.append("title_match")
                
                if topic_lower in adr.content.lower():
                    is_related = True
                    relevance_score += 2
                    reasons.append("content_match")
                
                # Check tags
                if tags and adr.front_matter.tags:
                    matching_tags = set(tags) & set(adr.front_matter.tags)
                    if matching_tags:
                        is_related = True
                        relevance_score += len(matching_tags)
                        reasons.append(f"tag_match: {list(matching_tags)}")
                
                # Check if ADR tags overlap with topic
                if adr.front_matter.tags:
                    for tag in adr.front_matter.tags:
                        if tag.lower() in topic_lower or topic_lower in tag.lower():
                            is_related = True
                            relevance_score += 1
                            reasons.append(f"tag_overlap: {tag}")
                
                if is_related:
                    related_adrs.append({
                        "id": adr.front_matter.id,
                        "title": adr.front_matter.title,
                        "status": str(adr.front_matter.status),
                        "tags": adr.front_matter.tags or [],
                        "file_path": str(file_path),
                        "relevance_score": relevance_score,
                        "match_reasons": reasons,
                        "content_preview": adr.content[:200] + "..." if len(adr.content) > 200 else adr.content
                    })
                    
            except ParseError:
                continue
        
        # Sort by relevance
        related_adrs.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Analyze conflicts
        conflicts = []
        for adr in related_adrs:
            if adr["status"] == "accepted":
                conflicts.append({
                    "adr_id": adr["id"], 
                    "title": adr["title"],
                    "conflict_type": "potential_superseding",
                    "reason": f"Existing accepted decision about {topic} - may need superseding"
                })
        
        return {
            "success": True,
            "topic": topic,
            "related_adrs": related_adrs[:10],  # Limit to top 10
            "total_found": len(related_adrs),
            "conflicts": conflicts,
            "recommendation": "Review related ADRs before proceeding. Consider superseding conflicting decisions." if conflicts else "No conflicts detected. Safe to proceed with new ADR."
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to query related ADRs: {e}",
            "guidance": "Check that ADR directory exists and contains valid ADR files"
        }


@mcp.tool()
def adr_approve(adr_id: str, supersede_ids: Optional[List[str]] = None, adr_dir: str = "docs/adr", make_readonly: bool = False) -> Dict[str, Any]:
    """Approve a proposed ADR with immutability protection and handle superseding relationships.
    
    🎯 WHEN TO USE:
    - After human has reviewed and approved a proposed ADR
    - When user confirms ADR should be accepted
    - To finalize the ADR workflow and update relationships
    
    🔄 ENHANCED WORKFLOW (V3 - Immutability):
    1. Validates ADR schema and policy completeness
    2. Changes ADR status from 'proposed' to 'accepted'
    3. **Computes content digest** for immutability tracking
    4. **Stores digest** in .project-index/adr-locks.json
    5. **Optional**: Makes file read-only (chmod 0444)
    6. Updates superseded ADRs to 'superseded' status  
    7. Establishes bidirectional relationships
    8. Regenerates index with new relationships
    
    ⚡ AUTOMATICALLY HANDLES:
    - **Immutability Protection**: Approved ADRs become tamper-resistant
    - **Content Digests**: SHA-256 hashing for integrity verification
    - **Lock Storage**: Persistent immutability tracking
    - Status transitions and relationship updates
    - Index regeneration and cross-validation
    
    🛡️ SECURITY FEATURES:
    - Content digest prevents unauthorized modifications
    - Optional read-only file protection
    - Only status and supersession fields remain mutable
    - Tamper detection in validation workflow
    
    📋 Args:
        adr_id: ID of the ADR to approve (e.g., "ADR-0007")
        supersede_ids: Optional list of ADR IDs this decision supersedes
        adr_dir: Directory containing ADRs
        make_readonly: Whether to make the ADR file read-only (default: False)
        
    Returns:
        Dictionary with approval status, immutability info, and updated relationships
    """
    try:
        adr_files = find_adr_files(Path(adr_dir))
        target_adr = None
        target_file = None
        
        # Find the ADR to approve
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.id == adr_id:
                    target_adr = adr
                    target_file = file_path
                    break
            except ParseError:
                continue
        
        if not target_adr:
            return {
                "success": False,
                "error": f"ADR {adr_id} not found",
                "message": f"Could not find ADR with ID {adr_id} for approval",
                "guidance": "Verify the ADR ID exists and is spelled correctly"
            }
        
        if target_adr.front_matter.status.value == "accepted":
            return {
                "success": False,
                "error": "ADR already accepted",
                "message": f"ADR {adr_id} is already in 'accepted' status",
                "guidance": "No action needed - ADR is already approved"
            }
        
        # Initialize immutability manager
        immutability_manager = ImmutabilityManager(Path(adr_dir).parent.parent)
        
        # Validate ADR before approval (including policy requirements)
        validation_result = validate_adr_file(target_file)
        if not validation_result.is_valid:
            return {
                "success": False,
                "error": "ADR validation failed",
                "validation_issues": [
                    {
                        "level": issue.level,
                        "message": issue.message,
                        "field": issue.field,
                        "rule": issue.rule
                    } for issue in validation_result.issues
                ],
                "message": f"ADR {adr_id} must pass validation before approval",
                "guidance": "Fix validation issues and try again"
            }
        
        # Update target ADR to accepted
        target_adr.front_matter.status = ADRStatus.ACCEPTED
        
        # Handle superseding relationships
        updated_adrs = []
        if supersede_ids:
            target_adr.front_matter.supersedes = supersede_ids
            
            # Update superseded ADRs
            for supersede_id in supersede_ids:
                for file_path in adr_files:
                    try:
                        old_adr = parse_adr_file(file_path, strict=False)
                        if old_adr and old_adr.front_matter.id == supersede_id:
                            old_adr.front_matter.status = ADRStatus.SUPERSEDED
                            old_adr.front_matter.superseded_by = [adr_id]
                            file_path.write_text(old_adr.to_markdown(), encoding='utf-8')
                            updated_adrs.append(supersede_id)
                            break
                    except ParseError:
                        continue
        
        # Save updated target ADR
        target_file.write_text(target_adr.to_markdown(), encoding='utf-8')
        
        # Create immutability lock (Phase 3 - V3 Feature)
        try:
            lock = immutability_manager.approve_adr(target_adr, make_readonly=make_readonly)
            immutability_info = {
                "digest": lock.digest,
                "locked_at": lock.locked_at,
                "is_readonly": lock.is_readonly,
                "locks_file": str(immutability_manager.locks_file)
            }
        except Exception as e:
            # Don't fail approval if immutability setup fails
            immutability_info = {
                "error": f"Immutability setup failed: {e}",
                "fallback": "ADR approved but not locked"
            }
        
        # Regenerate index
        try:
            from ..index.json_index import generate_adr_index
            generate_adr_index(adr_dir, f"{adr_dir}/adr-index.json", validate=False)
        except Exception:
            pass  # Index generation is optional
        
        return {
            "success": True,
            "adr_id": adr_id,
            "new_status": "accepted",
            "superseded_adrs": updated_adrs,
            "immutability": immutability_info,
            "message": f"✅ ADR {adr_id} approved, activated, and protected",
            "relationships_updated": len(updated_adrs),
            "workflow_stage": "completed",
            "security_features": [
                "Content digest computed for tamper detection",
                "Immutability lock stored in .project-index/adr-locks.json",
                "Only status transitions and supersession updates allowed",
                f"File read-only protection: {'enabled' if make_readonly else 'disabled'}"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to approve ADR: {e}",
            "guidance": "Check file permissions and ADR format validity"
        }


@mcp.tool()
def adr_supersede(request: ADRSupersedePayload, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Create a new ADR that supersedes an existing one.
    
    🎯 WHEN TO USE:
    - When an existing decision needs to be replaced/updated
    - User mentions changing from one technology to another
    - Architectural evolution requires updating previous decisions
    - After adr_query_related() identifies conflicts needing resolution
    
    🔄 WORKFLOW:
    1. Creates new ADR with 'proposed' status
    2. Establishes superseding relationship with old ADR
    3. Updates old ADR status to 'superseded' 
    4. Maintains bidirectional relationships
    5. Returns both ADRs for human review
    
    💡 TIP: Use adr_approve() afterward to finalize both ADRs
    
    📋 Args:
        request: Contains old_id and payload for new ADR
        adr_dir: Directory for ADR files
        
    Returns:
        Dictionary with new/old ADR details and next steps
    """
    try:
        adr_path = Path(adr_dir)
        
        # Find the old ADR
        adr_files = find_adr_files(adr_path)
        old_adr = None
        old_file_path = None
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.id == request.old_id:
                    old_adr = adr
                    old_file_path = file_path
                    break
            except ParseError:
                continue
        
        if not old_adr:
            return {
                "success": False,
                "error": f"ADR {request.old_id} not found",
                "message": f"Could not find ADR with ID {request.old_id}"
            }
        
        # Create new ADR
        create_result = adr_create(request.payload, adr_dir)
        if not create_result["success"]:
            return create_result
        
        new_id = create_result["id"]
        
        # Update the new ADR to include supersedes relationship
        new_file_path = Path(create_result["path"])
        new_adr = parse_adr_file(new_file_path, strict=False)
        new_adr.front_matter.supersedes = [request.old_id]
        new_file_path.write_text(new_adr.to_markdown(), encoding='utf-8')
        
        # Update old ADR to mark as superseded
        old_adr.front_matter.status = ADRStatus.SUPERSEDED
        old_adr.front_matter.superseded_by = [new_id]
        old_file_path.write_text(old_adr.to_markdown(), encoding='utf-8')
        
        return {
            "success": True,
            "new_id": new_id,
            "old_id": request.old_id,
            "new_path": str(new_file_path),
            "status": "proposed",
            "message": f"📝 Created superseding ADR {new_id} replacing {request.old_id}",
            "next_steps": f"Please review both ADRs and use adr_approve('{new_id}') to finalize the superseding relationship.",
            "workflow_stage": "awaiting_human_review"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to supersede ADR: {e}"
        }


@mcp.tool()
def adr_validate(request: ADRValidateRequest) -> Dict[str, Any]:
    """Validate ADRs for schema compliance, semantic rules, and policy requirements.
    
    🎯 WHEN TO USE:
    - After creating or modifying ADRs
    - Before approving ADRs (recommended - now includes policy validation)
    - When troubleshooting ADR issues
    - As part of quality assurance workflow
    
    🔍 WHAT IT CHECKS:
    - JSON Schema compliance (required fields, formats)
    - Semantic rules (superseded ADRs have superseded_by)
    - Policy completeness for accepted ADRs (V3 requirement)
    - Structured policy format validation
    - File format and YAML front-matter syntax
    - Cross-references and relationship consistency
    
    💡 ENHANCED VALIDATION:
    - Checks that accepted ADRs have extractable policies
    - Validates policy structure if present in front-matter
    - Provides actionable guidance for missing enforcement rules
    - Supports hybrid policy extraction (structured + pattern-based)
    
    📋 Args:
        request: Validation request with optional specific ADR ID
        
    Returns:
        Dictionary with validation results, policy analysis, and actionable feedback
    """
    try:
        adr_dir = request.adr_dir or "docs/adr"
        
        if request.id:
            # Validate specific ADR
            adr_files = find_adr_files(Path(adr_dir))
            target_file = None
            
            for file_path in adr_files:
                try:
                    adr = parse_adr_file(file_path, strict=False)
                    if adr and adr.front_matter.id == request.id:
                        target_file = file_path
                        break
                except ParseError:
                    continue
            
            if not target_file:
                return {
                    "success": False,
                    "error": f"ADR {request.id} not found",
                    "message": f"Could not find ADR with ID {request.id}"
                }
            
            result = validate_adr_file(target_file)
            results = [result]
        else:
            # Validate all ADRs
            results = validate_adr_directory(adr_dir)
        
        # Process results with policy analysis
        total_adrs = len(results)
        valid_adrs = sum(1 for r in results if r.is_valid)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        
        # Enhanced policy analysis
        policy_extractor = PolicyExtractor()
        policy_summary = {
            "adrs_with_policies": 0,
            "accepted_without_policies": 0,
            "enforcement_ready": 0
        }
        
        issues = []
        for result in results:
            if result.adr and result.adr.file_path:
                file_name = result.adr.file_path.name
                
                # Analyze policy status
                if result.adr.front_matter.status == ADRStatus.ACCEPTED:
                    has_policy = policy_extractor.has_extractable_policy(result.adr)
                    if has_policy:
                        policy_summary["adrs_with_policies"] += 1
                        extracted = policy_extractor.extract_policy(result.adr)
                        if extracted.imports or extracted.boundaries or extracted.python:
                            policy_summary["enforcement_ready"] += 1
                    else:
                        policy_summary["accepted_without_policies"] += 1
            else:
                file_name = "Unknown file"
            
            for issue in result.issues:
                issues.append({
                    "file": file_name,
                    "level": issue.level,
                    "message": issue.message,
                    "field": issue.field,
                    "rule": issue.rule
                })
        
        response = {
            "success": True,
            "summary": {
                "total_adrs": total_adrs,
                "valid_adrs": valid_adrs,
                "errors": total_errors,
                "warnings": total_warnings
            },
            "policy_analysis": policy_summary,
            "issues": issues,
            "is_valid": total_errors == 0
        }
        
        # Add policy guidance if needed
        if policy_summary["accepted_without_policies"] > 0:
            response["policy_guidance"] = f"{policy_summary['accepted_without_policies']} accepted ADRs lack extractable policies. Consider adding structured policy blocks or enhance content with decision rationales."
        
        if policy_summary["enforcement_ready"] > 0:
            response["enforcement_tip"] = f"{policy_summary['enforcement_ready']} ADRs are ready for lint rule generation. Use adr_export_lint_config() to create enforcement configurations."
        
        return response
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Validation failed: {e}"
        }


@mcp.tool()
def adr_index(request: ADRIndexRequest) -> Dict[str, Any]:
    """Generate or query comprehensive ADR index.
    
    🎯 WHEN TO USE:
    - To get overview of all ADRs in the system
    - After approving/updating ADRs (to refresh index)
    - When analyzing architectural decision patterns
    - For generating reports or dashboards
    
    🔍 PROVIDES:
    - Complete ADR catalog with metadata
    - Status distribution (proposed, accepted, superseded)
    - Tag-based categorization and counts
    - Relationship mappings between ADRs
    - Content previews for quick understanding
    
    📊 FILTERING:
    - By status (e.g., only 'accepted' decisions)
    - By tags (e.g., 'database', 'frontend')
    - By deciders (e.g., specific team or person)
    
    📋 Args:
        request: Index request with optional filters
        
    Returns:
        Dictionary with comprehensive ADR index and statistics
    """
    try:
        adr_dir = request.adr_dir or "docs/adr"
        
        # Generate fresh index
        index = ADRIndex(adr_dir)
        index.build_index(validate=True)
        
        # Apply filters if provided
        entries = index.entries
        if request.filters:
            filters = request.filters
            
            if "status" in filters:
                entries = [e for e in entries if str(e.adr.front_matter.status) in filters["status"]]
            
            if "tags" in filters:
                filter_tags = filters["tags"]
                entries = [e for e in entries 
                          if any(tag in (e.adr.front_matter.tags or []) for tag in filter_tags)]
            
            if "deciders" in filters:
                filter_deciders = filters["deciders"] 
                entries = [e for e in entries
                          if any(decider in (e.adr.front_matter.deciders or []) for decider in filter_deciders)]
        
        # Convert to serializable format
        adrs_data = [entry.to_dict() for entry in entries]
        
        return {
            "success": True,
            "metadata": index.metadata,
            "adrs": adrs_data,
            "count": len(adrs_data)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Index generation failed: {e}"
        }


@mcp.tool()
def adr_export_lint_config(request: ADRExportLintRequest) -> Dict[str, Any]:
    """Generate lint configurations from structured ADR policies using hybrid extraction.
    
    🎯 WHEN TO USE:
    - After approving ADRs with policy decisions
    - To enforce architectural decisions in development workflow
    - When setting up automated policy enforcement
    - To generate team-wide coding standards from ADRs
    
    🔧 WHAT IT GENERATES:
    - ESLint: no-restricted-imports rules with ADR citations
    - Ruff: Python import restrictions and style rules
    - import-linter: Architectural boundary enforcement
    - All configs include metadata linking back to source ADRs
    
    💡 HYBRID POLICY EXTRACTION:
    - Primary: Uses structured policy from ADR front-matter
    - Fallback: Pattern-based extraction from ADR content
    - Merges both sources for comprehensive rule coverage
    - Auto-detects library preferences and architectural boundaries
    
    🎯 AI AGENT WORKFLOW:
    1. Scans all accepted ADRs for policy information
    2. Extracts structured policies from front-matter
    3. Enhances with pattern-based extraction for legacy ADRs
    4. Generates framework-specific enforcement rules
    5. Includes ADR citations for traceability
    
    📋 Args:
        request: Framework type and ADR directory specification
        
    Returns:
        Generated configuration with ADR metadata, policy summary, and enforcement rules
    """
    try:
        adr_dir = request.adr_dir or "docs/adr"
        framework = request.framework.lower()
        
        # Enhanced policy analysis for lint generation
        policy_extractor = PolicyExtractor()
        adr_files = find_adr_files(Path(adr_dir))
        source_adrs = []
        total_policies = 0
        
        # Analyze ADRs for policy content
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.status == ADRStatus.ACCEPTED:
                    if policy_extractor.has_extractable_policy(adr):
                        extracted = policy_extractor.extract_policy(adr)
                        if extracted.imports or extracted.boundaries or extracted.python:
                            source_adrs.append(adr.front_matter.id)
                            total_policies += 1
            except ParseError:
                continue
        
        if framework == "eslint":
            config = generate_eslint_config(adr_dir)
            filename = ".eslintrc.adrs.json"
        elif framework == "ruff":
            config = generate_ruff_config(adr_dir)
            filename = "ruff.adrs.toml"
        elif framework == "import-linter":
            config = generate_import_linter_config(adr_dir)
            filename = ".import-linter.adrs.ini"
        else:
            return {
                "success": False,
                "error": f"Unsupported framework: {framework}",
                "supported": ["eslint", "ruff", "import-linter"]
            }
        
        response = {
            "success": True,
            "framework": framework,
            "config": config,
            "filename": filename,
            "message": f"Generated {framework} configuration from {total_policies} ADR policies",
            "policy_summary": {
                "source_adrs": source_adrs,
                "total_policies": total_policies,
                "extraction_method": "hybrid (structured + pattern-based)"
            }
        }
        
        # Add usage guidance
        if total_policies == 0:
            response["guidance"] = "No policies found in accepted ADRs. Ensure ADRs contain structured policy blocks or decision rationales in content."
        else:
            response["usage_tip"] = f"Save configuration to {filename} and integrate with your development workflow for automated policy enforcement."
        
        return response
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Lint config generation failed: {e}"
        }


@mcp.tool()
def adr_render_site(adr_dir: str = "docs/adr", out_dir: str = None) -> Dict[str, Any]:
    """Render beautiful static ADR site using Log4brains.
    
    🎯 WHEN TO USE:
    - After creating/updating ADRs to generate browsable site
    - To create documentation website for architectural decisions  
    - For sharing ADRs with team members and stakeholders
    - When preparing ADR documentation for deployment
    
    🌐 WHAT IT CREATES:
    - Static HTML site with timeline navigation
    - Searchable ADR interface with metadata
    - Automatic relationship mapping between ADRs
    - Mobile-friendly responsive design
    - Ready for deployment to GitHub Pages, etc.
    
    🔧 INTEGRATION:
    - Uses Log4brains for proven site generation
    - Preserves ADR Kit policy metadata  
    - Maintains compatibility with your ADR format
    - Outputs to easily discoverable location
    
    📋 Args:
        adr_dir: Directory containing ADR files (default: docs/adr)
        out_dir: Output directory for site (default: docs/adr/site/ for easy discovery)
        
    Returns:
        Dictionary with site generation results and local URL for browsing
    """
    try:
        # Use better default output directory (easily discoverable)
        if out_dir is None:
            out_dir = f"{adr_dir}/site"
        
        # Ensure output directory exists
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        # Check if log4brains is available
        try:
            subprocess.run(["log4brains", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {
                "success": False,
                "error": "log4brains not found", 
                "message": "Please install log4brains: npm install -g log4brains",
                "installation_help": "Log4brains generates beautiful ADR sites. Install with: npm install -g log4brains"
            }
        
        # Validate ADR directory exists
        adr_path = Path(adr_dir)
        if not adr_path.exists():
            return {
                "success": False,
                "error": "ADR directory not found",
                "message": f"ADR directory '{adr_dir}' does not exist. Use adr_init() first."
            }
        
        # Run log4brains build with better error handling
        result = subprocess.run([
            "log4brains", "build", 
            "--adrDir", adr_dir,
            "--outDir", out_dir
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": "log4brains build failed",
                "stderr": result.stderr,
                "stdout": result.stdout,
                "message": "Log4brains build process failed. Check ADR format compatibility."
            }
        
        # Check if site was actually generated
        site_index = Path(out_dir) / "index.html"
        if not site_index.exists():
            return {
                "success": False,
                "error": "site not generated",
                "message": "Log4brains completed but no site was generated"
            }
        
        return {
            "success": True,
            "out_dir": out_dir,
            "site_url": f"file://{site_index.absolute()}",
            "message": f"✅ ADR site rendered successfully to {out_dir}",
            "browse_instruction": f"Open {site_index} in your browser to view the site",
            "stdout": result.stdout,
            "adr_count": len([f for f in adr_path.glob("*.md") if f.name.startswith("ADR-")])
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Site rendering failed: {e}"
        }


@mcp.tool()
def adr_init(adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Initialize ADR structure in a repository.
    
    🎯 WHEN TO USE:
    - Setting up ADR system in a new project
    - First time using ADR Kit in a repository
    - Recreating ADR structure after cleanup
    
    🔧 WHAT IT CREATES:
    - ADR directory structure (docs/adr/)
    - Project index directory (.project-index/)
    - Initial JSON index file
    - Template directory structure
    
    💡 ONE-TIME SETUP:
    - Run once per project/repository
    - Safe to run multiple times (won't overwrite existing ADRs)
    
    📋 Args:
        adr_dir: Directory to create for ADR files (default: docs/adr)
        
    Returns:
        Dictionary with setup confirmation and next steps
    """
    try:
        adr_path = Path(adr_dir)
        index_path = Path(".project-index")
        
        # Create directories
        adr_path.mkdir(parents=True, exist_ok=True)
        index_path.mkdir(exist_ok=True)
        
        # Generate initial index
        try:
            from ..index.json_index import generate_adr_index
            generate_adr_index(adr_dir, f"{adr_dir}/adr-index.json", validate=False)
        except Exception:
            pass  # Index generation is optional during init
        
        return {
            "success": True,
            "adr_directory": str(adr_path),
            "index_directory": str(index_path),
            "message": "✅ ADR system initialized successfully",
            "next_steps": "Use adr_create() to create your first ADR or adr_query_related() to explore existing decisions",
            "ready_for_use": True
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to initialize ADR system: {e}",
            "guidance": "Check directory permissions and available disk space"
        }


@mcp.tool()
def adr_semantic_index(request: ADRSemanticIndexRequest, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Build or update semantic index for intelligent ADR discovery.
    
    🎯 WHEN TO USE:
    - After creating or updating multiple ADRs
    - When setting up semantic search capabilities
    - To enable intelligent ADR matching and discovery
    - Before using adr_semantic_match() for the first time
    
    🧠 WHAT IT DOES:
    - Chunks ADR content into semantic segments (title, sections, content)
    - Generates vector embeddings using sentence-transformers
    - Stores embeddings locally (.project-index/adr-vectors/)
    - Creates searchable semantic index for fast retrieval
    - Supports incremental updates (only processes new/changed ADRs)
    
    💾 STORAGE FORMAT:
    - chunks.jsonl: Semantic chunks with metadata
    - embeddings.npz: NumPy embeddings matrix
    - meta.idx.json: Mappings and index metadata
    
    🔧 AI AGENT USAGE:
    - Run after batch ADR operations
    - Use force_rebuild=True for fresh start
    - Index enables semantic matching and related ADR discovery
    - Required for adr_semantic_match() functionality
    
    📋 Args:
        request: Semantic indexing request with directory and options
        adr_dir: Directory containing ADR files (defaults to request.adr_dir)
        
    Returns:
        Dictionary with indexing statistics and semantic capabilities info
    """
    try:
        adr_directory = request.adr_dir or adr_dir
        
        # Initialize semantic index
        semantic_index = SemanticIndex(Path(adr_directory).parent.parent)
        
        # Build or update index
        stats = semantic_index.build_index(
            adr_dir=adr_directory,
            force_rebuild=request.force_rebuild or False
        )
        
        return {
            "success": True,
            "semantic_index": stats,
            "storage_location": str(semantic_index.vectors_dir),
            "capabilities": [
                "Semantic similarity search",
                "Intelligent ADR discovery", 
                "Content-aware matching",
                "Related ADR suggestions"
            ],
            "message": f"✅ Semantic index ready: {stats['total_chunks']} chunks from {stats['total_adrs']} ADRs",
            "next_steps": "Use adr_semantic_match() to perform intelligent ADR searches"
        }
        
    except ImportError as e:
        return {
            "success": False,
            "error": "Missing dependencies",
            "message": str(e),
            "guidance": "Install semantic search dependencies: pip install sentence-transformers"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Semantic indexing failed: {e}",
            "guidance": "Check ADR directory exists and contains valid ADR files"
        }


@mcp.tool() 
def adr_semantic_match(request: ADRSemanticMatchRequest, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Find semantically related ADRs using vector similarity.
    
    🎯 WHEN TO USE:
    - Before creating new ADRs (find related existing decisions)
    - When exploring architectural decision context
    - To discover ADRs related to specific topics or technologies
    - For intelligent ADR recommendations based on content
    
    🧠 HOW IT WORKS:
    - Converts query text to vector embedding
    - Computes cosine similarity with existing ADR embeddings  
    - Ranks results by semantic relevance
    - Returns ADRs with contextual excerpts and metadata
    - Supports status filtering (e.g., only 'accepted' ADRs)
    
    💡 QUERY EXAMPLES:
    - "database migration strategy"
    - "microservices communication patterns"  
    - "frontend state management"
    - "authentication and authorization"
    
    ⚡ AI AGENT WORKFLOW:
    1. Use before adr_create() to find related decisions
    2. Analyze returned matches for conflicts or dependencies
    3. Reference related ADRs in new ADR content
    4. Suggest superseding relationships when appropriate
    
    📋 Args:
        request: Semantic matching request with query and filters
        adr_dir: Directory containing ADRs (fallback)
        
    Returns:
        Dictionary with semantically matched ADRs, scores, and excerpts
    """
    try:
        # Initialize semantic index
        semantic_index = SemanticIndex(Path(adr_dir).parent.parent)
        
        # Convert filter status to set if provided
        filter_status = set(request.filter_status) if request.filter_status else None
        
        # Perform semantic search
        matches = semantic_index.search(
            query=request.text,
            k=request.k or 5,
            filter_status=filter_status
        )
        
        if not matches:
            return {
                "success": True,
                "matches": [],
                "query": request.text,
                "total_found": 0,
                "message": "No semantically related ADRs found",
                "guidance": "Try broader search terms or run adr_semantic_index() first"
            }
        
        # Convert matches to serializable format
        match_data = []
        for match in matches:
            match_info = {
                "adr_id": match.adr_id,
                "title": match.title,
                "status": match.status,
                "similarity_score": match.score,
                "excerpt": match.excerpt,
                "matching_sections": [
                    {
                        "type": chunk.chunk_type,
                        "section": chunk.section_name,
                        "content_preview": chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
                    }
                    for chunk in match.chunks[:2]  # Top 2 matching sections
                ]
            }
            match_data.append(match_info)
        
        return {
            "success": True,
            "matches": match_data,
            "query": request.text,
            "total_found": len(matches),
            "semantic_analysis": {
                "avg_similarity": sum(m.score for m in matches) / len(matches),
                "top_score": max(m.score for m in matches),
                "confidence": "high" if matches[0].score > 0.7 else "medium" if matches[0].score > 0.5 else "low"
            },
            "message": f"🎯 Found {len(matches)} semantically related ADRs",
            "workflow_suggestions": [
                "Review matches for potential conflicts before creating new ADRs",
                "Consider superseding relationships with highly similar decisions",
                "Reference related ADRs in new architectural decisions"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Semantic search failed: {e}",
            "guidance": "Ensure adr_semantic_index() has been run to build the semantic index"
        }


@mcp.tool()
def adr_guard(request: ADRGuardRequest, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Analyze code changes for ADR policy violations using semantic context.
    
    This powerful tool examines git diffs against your ADR policies to detect violations
    before they reach production. It combines semantic understanding with policy rules
    to provide contextual, actionable feedback for maintaining architectural compliance.
    
    Key capabilities:
    - Parses git diffs to extract imports and file changes
    - Uses semantic similarity to find relevant ADRs for the changed code
    - Checks imports against disallow/prefer lists from ADR policies
    - Validates architectural boundaries and layer violations
    - Provides specific violation details with ADR references
    - Suggests concrete fixes and alternatives
    
    Perfect for:
    - Pre-commit hooks to enforce architectural decisions
    - Code review automation to catch policy violations
    - CI/CD integration for architectural governance
    - Developer guidance during feature development
    
    Args:
        request: Contains git diff text and configuration options
        adr_dir: Directory containing ADR files to check against
    
    Returns:
        Comprehensive analysis with violations, suggestions, and relevant ADRs
    """
    try:
        # Initialize guard system
        project_root = Path(adr_dir).parent.parent
        guard = GuardSystem(project_root=project_root, adr_dir=adr_dir)
        
        # Analyze the diff
        result = guard.analyze_diff(
            diff_text=request.diff_text,
            build_index=request.build_index
        )
        
        # Format violations for agent consumption
        violations_data = []
        for violation in result.violations:
            violations_data.append({
                "type": violation.violation_type,
                "severity": violation.severity,
                "message": violation.message,
                "file": violation.file_path,
                "line": violation.line_number,
                "adr_id": violation.adr_id,
                "adr_title": violation.adr_title,
                "suggested_fix": violation.suggested_fix,
                "context": violation.context
            })
        
        # Format relevant ADRs
        relevant_adrs_data = []
        for adr_match in result.relevant_adrs:
            relevant_adrs_data.append({
                "adr_id": adr_match.adr_id,
                "title": adr_match.title,
                "status": adr_match.status,
                "relevance_score": adr_match.score,
                "excerpt": adr_match.excerpt
            })
        
        return {
            "success": True,
            "analysis": {
                "summary": result.summary,
                "violations": violations_data,
                "analyzed_files": result.analyzed_files,
                "relevant_adrs": relevant_adrs_data,
                "has_errors": result.has_errors,
                "has_warnings": result.has_warnings,
                "total_violations": len(result.violations)
            },
            "message": f"Analyzed {len(result.analyzed_files)} files for policy compliance",
            "guidance": "Review violations and apply suggested fixes. Consider updating ADRs if policies need adjustment."
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to analyze code changes for policy violations",
            "guidance": "Check that git diff is valid and ADR directory exists with policy-enabled ADRs"
        }


@mcp.tool()
def adr_contract_build(request: ADRContractRequest) -> Dict[str, Any]:
    """Build the unified constraints contract from all accepted ADRs.
    
    🎯 THE KEYSTONE TOOL: Creates constraints_accepted.json - the single source of truth
    that agents use for all architectural decisions. This is the most important tool
    for establishing deterministic policy enforcement.
    
    💡 WHEN TO USE:
    - After approving new ADRs (adr_approve()) to update the contract
    - When setting up a new project to establish baseline constraints
    - After superseding ADRs to reflect new architectural decisions
    - To check current contract status and constraint counts
    - For debugging policy conflicts or enforcement issues
    
    ⚡ AUTOMATICALLY HANDLES:
    - Finds all accepted ADRs in the specified directory
    - Merges policies using "deny beats allow" conflict resolution
    - Respects supersede relationships (topological ordering)
    - Generates SHA-256 hash for change detection
    - Caches results for performance (rebuilt only when ADRs change)
    - Creates provenance mapping (each rule → source ADR)
    
    🔒 CONFLICT RESOLUTION:
    - Import conflicts: disallow beats prefer (safety first)
    - Boundary conflicts: later ADRs override earlier ones
    - Unresolvable conflicts cause build failure with clear error messages
    
    📊 RETURNS:
    - Contract metadata: hash, generation time, source ADRs
    - Constraint counts: imports, boundaries, Python rules
    - Cache information: hit/miss, performance metrics
    - Success/failure status with actionable error messages
    
    Args:
        request: Configuration for contract building
        
    Returns:
        Complete contract status with metadata, counts, and guidance
    """
    try:
        adr_dir = Path(request.adr_dir)
        builder = ConstraintsContractBuilder(adr_dir)
        
        # Build/rebuild the contract
        contract = builder.build_contract(force_rebuild=request.force_rebuild)
        summary = builder.get_contract_summary()
        
        # Get the contract file path for agent reference
        contract_path = builder.get_contract_file_path()
        
        return {
            "success": True,
            "contract": {
                "file_path": str(contract_path),
                "hash": contract.metadata.hash,
                "generated_at": contract.metadata.generated_at.isoformat(),
                "source_adrs": contract.metadata.source_adrs,
                "constraints_count": {
                    "total": sum([
                        len(contract.constraints.imports.disallow) if contract.constraints.imports and contract.constraints.imports.disallow else 0,
                        len(contract.constraints.imports.prefer) if contract.constraints.imports and contract.constraints.imports.prefer else 0,
                        len(contract.constraints.boundaries.rules) if contract.constraints.boundaries and contract.constraints.boundaries.rules else 0,
                        len(contract.constraints.python.disallow_imports) if contract.constraints.python and contract.constraints.python.disallow_imports else 0
                    ]),
                    "imports_disallow": len(contract.constraints.imports.disallow) if contract.constraints.imports and contract.constraints.imports.disallow else 0,
                    "imports_prefer": len(contract.constraints.imports.prefer) if contract.constraints.imports and contract.constraints.imports.prefer else 0,
                    "boundary_rules": len(contract.constraints.boundaries.rules) if contract.constraints.boundaries and contract.constraints.boundaries.rules else 0,
                    "python_disallow": len(contract.constraints.python.disallow_imports) if contract.constraints.python and contract.constraints.python.disallow_imports else 0
                }
            },
            "cache_info": summary.get("cache_info", {}),
            "message": f"✅ Built constraints contract from {len(contract.metadata.source_adrs)} accepted ADRs",
            "guidance": [
                f"Contract available at {contract_path} - this is your definitive policy source",
                "Use this contract hash for change detection in CI/automation",
                "All agent decisions should reference this contract, not individual ADRs",
                f"Run adr_export_lint_config() to apply {summary.get('total_constraints', 0)} constraints as lint rules"
            ]
        }
        
    except ContractBuildError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "ContractBuildError",
            "message": "❌ Contract build failed due to policy conflicts",
            "guidance": [
                "Review the conflicting ADRs listed in the error",
                "Consider superseding older ADRs that conflict with newer decisions",
                "Use explicit policy precedence in newer ADRs to resolve conflicts",
                "Check that ADR relationships (supersedes/superseded_by) are correctly set"
            ]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Contract building failed",
            "guidance": [
                "Ensure ADR directory exists and contains valid ADRs",
                "Check that accepted ADRs have valid policy front-matter",
                "Verify file permissions allow reading ADRs and writing cache"
            ]
        }


@mcp.tool() 
def adr_contract_validate_policy(request: ADRContractValidateRequest) -> Dict[str, Any]:
    """Validate a policy against the current constraints contract.
    
    🎯 PROACTIVE CONFLICT PREVENTION: Check if a new policy would conflict with 
    existing architectural decisions BEFORE creating or accepting an ADR.
    
    💡 WHEN TO USE:
    - Before adr_create() when policy is included - prevent conflicts upfront
    - During ADR review process to validate policy compatibility  
    - When updating existing ADRs to ensure no new conflicts
    - For policy design guidance - understand current constraint landscape
    
    🔍 VALIDATION CHECKS:
    - Import conflicts: new disallow vs existing prefer (and vice versa)
    - Boundary conflicts: architectural layer violations
    - Python-specific conflicts: import restrictions
    - Supersede relationship impacts on policy precedence
    
    ⚡ AUTOMATICALLY HANDLES:
    - Loads current constraints_accepted.json contract
    - Parses and validates policy structure
    - Identifies specific conflicting rules with source ADR references
    - Provides actionable resolution suggestions
    
    📊 RETURNS:
    - Validation status: valid/invalid with detailed conflict descriptions
    - Conflicting ADR references: which decisions would be violated
    - Resolution suggestions: how to resolve conflicts
    - Current contract hash: for cache validation
    
    Args:
        request: Policy data and ADR ID to validate
        
    Returns:
        Detailed validation results with conflict resolution guidance
    """
    try:
        adr_dir = Path(request.adr_dir)
        builder = ConstraintsContractBuilder(adr_dir)
        
        # Validate the policy
        validation_result = builder.validate_new_policy(request.policy, request.adr_id)
        
        if validation_result["valid"]:
            return {
                "success": True,
                "valid": True,
                "conflicts": [],
                "contract_hash": validation_result["contract_hash"],
                "message": f"✅ Policy for {request.adr_id} is compatible with existing constraints",
                "guidance": [
                    "Policy validation passed - no conflicts detected",
                    "Safe to proceed with ADR creation/acceptance",
                    "Policy will be included in next contract rebuild"
                ]
            }
        else:
            return {
                "success": True,
                "valid": False,
                "conflicts": validation_result["conflicts"],
                "contract_hash": validation_result["contract_hash"],
                "message": f"❌ Policy conflicts detected for {request.adr_id}",
                "guidance": [
                    "Review conflicts and consider policy modifications",
                    "Use supersede relationships to override conflicting decisions",
                    "Consider if existing ADRs should be deprecated/superseded",
                    "Ensure policy precedence is clearly established"
                ]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "valid": False,
            "message": "Policy validation failed",
            "guidance": [
                "Check that policy structure matches PolicyModel schema",
                "Ensure constraints contract exists (run adr_contract_build())",
                "Verify ADR directory path and permissions"
            ]
        }


@mcp.tool()
def adr_contract_status(request: ADRContractRequest) -> Dict[str, Any]:
    """Get current status and metadata of the constraints contract.
    
    🎯 CONTRACT VISIBILITY: Understand the current state of your architectural
    constraints without rebuilding. Perfect for debugging and status checking.
    
    💡 WHEN TO USE:
    - Before making architectural decisions to understand current constraints
    - For debugging policy enforcement issues  
    - To check if contract needs rebuilding (hash changed)
    - For CI/CD status reporting on architectural governance
    - When investigating why certain policies aren't being enforced
    
    ⚡ PROVIDES:
    - Contract metadata: hash, generation time, source ADRs
    - Constraint statistics: counts by type (imports, boundaries, Python)
    - Cache status: hit/miss rates, performance metrics  
    - File locations: where contract and cache files are stored
    - Validation status: are all constraints properly formed
    
    📊 RETURNS:
    - Complete contract summary with all metadata
    - Actionable guidance based on current state
    - Performance and caching information
    - File paths for manual inspection if needed
    
    Args:
        request: Configuration for status checking
        
    Returns:
        Comprehensive contract status and metadata
    """
    try:
        adr_dir = Path(request.adr_dir)
        builder = ConstraintsContractBuilder(adr_dir)
        
        # Get comprehensive status
        summary = builder.get_contract_summary()
        contract_path = builder.get_contract_file_path()
        
        if summary["success"]:
            return {
                "success": True,
                "contract": {
                    "exists": contract_path.exists(),
                    "file_path": str(contract_path),
                    "hash": summary["contract_hash"],
                    "generated_at": summary["generated_at"],
                    "source_adrs": summary["source_adrs"]
                },
                "constraints": summary["constraint_counts"],
                "statistics": {
                    "total_constraints": summary["total_constraints"],
                    "source_adr_count": len(summary["source_adrs"]),
                    "provenance_entries": summary["provenance_entries"]
                },
                "cache": summary["cache_info"],
                "message": f"📊 Contract contains {summary['total_constraints']} constraints from {len(summary['source_adrs'])} ADRs",
                "guidance": [
                    f"Contract hash: {summary['contract_hash'][:8]}... (use for change detection)",
                    f"Source ADRs: {', '.join(summary['source_adrs'])}",
                    "Use adr_contract_build() to rebuild if ADRs have changed",
                    "Reference this contract for all architectural decisions"
                ]
            }
        else:
            return {
                "success": False,
                "error": summary.get("error", "Unknown error"),
                "cache": summary.get("cache_info", {}),
                "message": "Contract status check failed",
                "guidance": [
                    "Run adr_contract_build() to create initial contract",
                    "Ensure ADR directory exists and contains accepted ADRs",
                    "Check file permissions for cache directory"
                ]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get contract status",
            "guidance": [
                "Verify ADR directory path is correct",
                "Ensure sufficient permissions to read ADR files",
                "Check that ADR directory structure is properly initialized"
            ]
        }


@mcp.tool()
def adr_preflight(request: ADRPreflightRequest) -> Dict[str, Any]:
    """Evaluate a technical choice through the preflight policy gate.
    
    🎯 THE CONTROL POINT: This is where agents check if a technical decision
    requires human approval BEFORE implementation. The gate prevents policy
    violations and ensures architectural decisions follow the established
    governance process.
    
    💡 WHEN TO USE (CRITICAL - USE THIS FIRST):
    - BEFORE adding any new dependency to package.json/requirements.txt/etc.
    - BEFORE adopting a new framework or major library
    - BEFORE making any significant technical choice
    - When user mentions "use X", "switch to Y", "try Z", "install ABC"
    - For ANY choice that could affect architecture or team standards
    
    ⚡ AUTOMATICALLY HANDLES:
    - Checks against existing constraints contract (constraints_accepted.json)
    - Applies "require ADR" default for runtime dependencies
    - Categorizes choices (dependency/framework/tool) with smart defaults
    - Normalizes names and handles aliases (react-query → @tanstack/react-query)
    - Detects conflicts with existing ADR policies
    - Provides clear guidance: PROCEED, DRAFT ADR, or BLOCKED
    
    🔍 EVALUATION LOGIC:
    1. Always-allow list: Proceed immediately (dev tools, pre-approved choices)
    2. Always-deny list: Block immediately (banned libraries/patterns)
    3. Contract conflicts: Block if conflicts with accepted ADR policies
    4. Default policies: Apply "require ADR" for runtime deps/frameworks
    
    📊 RETURNS:
    - Clear decision: ALLOWED, REQUIRES_ADR, BLOCKED, or CONFLICT
    - Human-readable reasoning explaining the decision
    - Agent guidance: specific next steps based on decision
    - Metadata: choice category, normalized name, evaluation details
    
    🚀 AGENT WORKFLOW:
    ```
    result = adr_preflight({
        "choice_name": "axios", 
        "context": "need HTTP client for API calls",
        "choice_type": "dependency"
    })
    
    if result.should_proceed:
        # ✅ Implement immediately
    elif result.requires_human_approval:
        # 🛑 Draft ADR first: adr_create() with the choice details
    else:
        # ❌ Blocked - find alternative or update existing ADRs
    ```
    
    Args:
        request: Technical choice details and context
        
    Returns:
        Gate evaluation result with decision and actionable guidance
    """
    try:
        adr_dir = Path(request.adr_dir)
        gate = PolicyGate(adr_dir)
        
        # Create technical choice from request
        choice = create_technical_choice(
            choice_type=request.choice_type,
            name=request.choice_name,
            context=request.context,
            ecosystem=request.ecosystem,
            is_dev_dependency=request.is_dev_dependency,
            alternatives_considered=request.alternatives_considered or []
        )
        
        # Evaluate through the gate
        result = gate.evaluate(choice)
        
        # Get recommendations for context
        recommendations = gate.get_recommendations_for_choice(request.choice_name)
        
        # Build response with clear agent guidance
        response = {
            "success": True,
            "decision": result.decision.value,
            "should_proceed": result.should_proceed,
            "requires_human_approval": result.requires_human_approval, 
            "is_blocked": result.is_blocked,
            "choice": {
                "name": result.choice.name,
                "type": result.choice.choice_type.value,
                "context": result.choice.context,
                "category": result.metadata.get("category"),
                "normalized_name": result.metadata.get("normalized_name")
            },
            "reasoning": result.reasoning,
            "agent_guidance": result.get_agent_guidance(),
            "recommendations": recommendations,
            "evaluated_at": result.evaluated_at.isoformat()
        }
        
        # Add decision-specific guidance
        if result.decision == GateDecision.ALLOWED:
            response["message"] = f"✅ '{request.choice_name}' approved - you may proceed"
            response["next_steps"] = [
                "Implement the choice as planned",
                "Document the implementation in code comments if needed",
                "Consider if this choice should be added to preferred alternatives"
            ]
        
        elif result.decision == GateDecision.REQUIRES_ADR:
            response["message"] = f"🛑 '{request.choice_name}' requires ADR approval first"
            response["next_steps"] = [
                "Use adr_create() to draft an ADR for this choice",
                "Include the context and alternatives in the ADR",
                "Request human review and approval",
                "DO NOT implement until ADR is accepted"
            ]
        
        elif result.decision == GateDecision.BLOCKED:
            response["message"] = f"❌ '{request.choice_name}' is blocked by policy"
            response["next_steps"] = [
                "Do not implement this choice",
                "Consider the recommended alternatives",
                "If strongly needed, discuss with team lead to update policies"
            ]
        
        elif result.decision == GateDecision.CONFLICT:
            response["message"] = f"⚠️ '{request.choice_name}' conflicts with existing ADRs"
            response["next_steps"] = [
                "Review the conflicting ADR policies listed",
                "Use the recommended alternatives if suitable",
                "If this choice is truly needed, consider superseding conflicting ADRs",
                "Draft ADR explaining why existing decisions should be changed"
            ]
        
        return response
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "decision": "error",
            "message": "Preflight evaluation failed",
            "agent_guidance": "Unable to evaluate choice - check ADR directory and try again",
            "guidance": [
                "Ensure ADR directory exists and is accessible",
                "Check that policy gate configuration is valid",
                "Verify choice name and type are provided correctly"
            ]
        }


@mcp.tool()
def adr_preflight_bulk(request: ADRPreflightBulkRequest) -> Dict[str, Any]:
    """Evaluate multiple technical choices through the preflight gate.
    
    🎯 BULK EVALUATION: Perfect for evaluating entire dependency lists,
    technology stacks, or multiple related choices in one operation.
    
    💡 WHEN TO USE:
    - Planning a new project with multiple dependencies
    - Evaluating an existing project's dependencies against new policies
    - Technology stack decisions (frontend + backend + database + tools)
    - Migration scenarios where multiple choices change together
    - Reviewing package.json, requirements.txt, or similar manifests
    
    📊 RETURNS:
    - Individual results for each choice with decisions and guidance
    - Summary statistics: allowed/blocked/requiring ADR counts
    - Batch recommendations for addressing blocked or conflicting choices
    - Prioritized action list for choices requiring ADRs
    
    Args:
        request: List of technical choices and overall context
        
    Returns:
        Bulk evaluation results with summary and individual decisions
    """
    try:
        adr_dir = Path(request.adr_dir)
        gate = PolicyGate(adr_dir)
        
        results = []
        summary = {
            "total": len(request.choices),
            "allowed": 0,
            "requires_adr": 0,
            "blocked": 0,
            "conflicts": 0,
            "errors": 0
        }
        
        # Evaluate each choice
        for choice_data in request.choices:
            try:
                # Create technical choice
                choice = create_technical_choice(
                    choice_type=choice_data.get("choice_type", "dependency"),
                    name=choice_data["choice_name"],
                    context=choice_data.get("context", request.context),
                    **{k: v for k, v in choice_data.items() 
                       if k not in ["choice_name", "choice_type", "context"]}
                )
                
                # Evaluate
                result = gate.evaluate(choice)
                
                # Add to results
                results.append({
                    "choice_name": choice_data["choice_name"],
                    "decision": result.decision.value,
                    "reasoning": result.reasoning,
                    "should_proceed": result.should_proceed,
                    "requires_human_approval": result.requires_human_approval,
                    "is_blocked": result.is_blocked,
                    "agent_guidance": result.get_agent_guidance(),
                    "metadata": result.metadata
                })
                
                # Update summary
                if result.decision == GateDecision.ALLOWED:
                    summary["allowed"] += 1
                elif result.decision == GateDecision.REQUIRES_ADR:
                    summary["requires_adr"] += 1
                elif result.decision == GateDecision.BLOCKED:
                    summary["blocked"] += 1
                elif result.decision == GateDecision.CONFLICT:
                    summary["conflicts"] += 1
                    
            except Exception as e:
                results.append({
                    "choice_name": choice_data.get("choice_name", "unknown"),
                    "decision": "error", 
                    "reasoning": f"Evaluation failed: {e}",
                    "error": str(e)
                })
                summary["errors"] += 1
        
        # Generate action recommendations
        action_plan = []
        if summary["requires_adr"] > 0:
            action_plan.append(f"📋 Draft {summary['requires_adr']} ADRs for choices requiring approval")
        if summary["blocked"] > 0:
            action_plan.append(f"🚫 Review {summary['blocked']} blocked choices - find alternatives")
        if summary["conflicts"] > 0:
            action_plan.append(f"⚠️ Resolve {summary['conflicts']} policy conflicts")
        if summary["allowed"] > 0:
            action_plan.append(f"✅ Proceed with {summary['allowed']} approved choices")
        
        return {
            "success": True,
            "results": results,
            "summary": summary,
            "action_plan": action_plan,
            "message": f"Evaluated {summary['total']} choices: {summary['allowed']} approved, {summary['requires_adr']} need ADR, {summary['blocked']} blocked",
            "guidance": [
                "Review individual choice results for specific guidance",
                "Prioritize ADR creation for choices marked 'requires_adr'",
                "Address blocked/conflicting choices before proceeding",
                "Document approval reasoning in ADRs for future reference"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Bulk preflight evaluation failed",
            "guidance": [
                "Check that all choices have required fields",
                "Ensure ADR directory is accessible",
                "Verify choice data format is correct"
            ]
        }


@mcp.tool()
def adr_gate_config(request: ADRGateConfigRequest) -> Dict[str, Any]:
    """Manage preflight gate configuration.
    
    🎯 POLICY CONTROL: Configure the preflight gate's behavior, default
    policies, allow/deny lists, and categorization rules.
    
    💡 WHEN TO USE:
    - Initial project setup: configure default policies
    - Add frequently used libraries to allow-list
    - Block problematic libraries/patterns
    - Adjust policies as project evolves
    - Debug gate decisions by checking current configuration
    
    🔧 CONFIGURATION OPTIONS:
    - Default policies: require_adr (default), allowed, blocked
    - Allow/deny lists: explicit overrides for specific choices
    - Development tools: typically allowed without ADR
    - Categories: how choices are classified
    - Name mappings: normalize aliases and variants
    
    Args:
        request: Configuration action and optional updates
        
    Returns:
        Current configuration state and update results
    """
    try:
        adr_dir = Path(request.adr_dir)
        gate = PolicyGate(adr_dir)
        
        if request.action == "get":
            # Return current configuration
            status = gate.get_gate_status()
            return {
                "success": True,
                "action": "get",
                "configuration": status,
                "message": "Current gate configuration retrieved",
                "guidance": [
                    "Review default policies for different choice types",
                    "Check allow/deny lists for explicit overrides",
                    "Verify development tools are properly categorized",
                    "Use 'update' action to modify configuration"
                ]
            }
        
        elif request.action == "update":
            if not request.config_updates:
                return {
                    "success": False,
                    "error": "No configuration updates provided",
                    "message": "Update action requires config_updates"
                }
            
            # Apply configuration updates
            updates_applied = []
            
            # Update allow list
            if "add_to_allow" in request.config_updates:
                for choice in request.config_updates["add_to_allow"]:
                    gate.engine.add_to_allow_list(choice)
                    updates_applied.append(f"Added '{choice}' to allow list")
            
            # Update deny list
            if "add_to_deny" in request.config_updates:
                for choice in request.config_updates["add_to_deny"]:
                    gate.engine.add_to_deny_list(choice)
                    updates_applied.append(f"Added '{choice}' to deny list")
            
            # Update default policies
            if "default_policies" in request.config_updates:
                for choice_type, policy in request.config_updates["default_policies"].items():
                    gate.engine.update_default_policy(choice_type, GateDecision(policy))
                    updates_applied.append(f"Updated default {choice_type} policy to {policy}")
            
            return {
                "success": True,
                "action": "update",
                "updates_applied": updates_applied,
                "configuration": gate.get_gate_status(),
                "message": f"Applied {len(updates_applied)} configuration updates",
                "guidance": [
                    "Configuration changes take effect immediately",
                    "Test updated policies with adr_preflight()",
                    "Document significant policy changes in ADRs"
                ]
            }
        
        elif request.action == "reset":
            # Reset to default configuration
            # This would require implementing a reset method
            return {
                "success": False,
                "error": "Reset action not yet implemented",
                "message": "Configuration reset is not available in this version",
                "guidance": [
                    "Manually delete .adr/policy.json to reset to defaults",
                    "Use 'update' action to modify specific settings"
                ]
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {request.action}",
                "message": "Valid actions are: get, update, reset"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Gate configuration operation failed",
            "guidance": [
                "Ensure ADR directory exists and is writable", 
                "Check that configuration updates are valid",
                "Verify action parameter is correct"
            ]
        }


@mcp.tool()
def adr_planning_context(request: ADRPlanningContextRequest) -> Dict[str, Any]:
    """Generate curated planning context for specific tasks.
    
    🎯 THE PLANNING REVOLUTION: Instead of agents searching through all ADRs,
    this tool provides exactly what they need: constraints + relevant decisions
    + contextual guidance, all optimized for the specific task at hand.
    
    💡 WHEN TO USE (CRITICAL - USE AT START OF PLANNING):
    - Beginning any new feature, bugfix, or refactor work
    - When user describes what they want to accomplish
    - Before making architectural decisions or technical choices
    - When you need to understand "what do I need to know for this task?"
    - After running preflight checks and needing detailed context
    
    ⚡ AUTOMATICALLY HANDLES:
    - Analyzes task to understand architectural scope and requirements
    - Loads current constraints contract for hard rules
    - Ranks ALL ADRs by relevance to this specific task
    - Curates shortlist of most relevant decisions (3-5 ADRs max)
    - Generates contextual guidance specific to task type and complexity
    - Optimizes for token efficiency (target: 800 tokens)
    - Creates agent-ready prompt with actionable guidance
    
    🔍 INTELLIGENCE LAYERS:
    1. Task Analysis: Understands what you're trying to accomplish
    2. Technology Detection: Identifies relevant tech stack components
    3. Relevance Ranking: Scores ADRs by overlap with task requirements
    4. Context Curation: Selects most important architectural guidance
    5. Guidance Generation: Creates specific promptlets for the task
    6. Token Optimization: Fits within agent working memory limits
    
    📊 RETURNS:
    - Hard constraints: Non-negotiable rules from constraints contract
    - Relevant ADRs: 3-5 most important decisions with summaries
    - Contextual guidance: Task-specific instructions and warnings
    - Agent-ready prompt: Formatted for direct use in agent context
    - Token count: Estimated usage for budget management
    
    🚀 AGENT WORKFLOW TRANSFORMATION:
    ```
    # OLD WAY - Overwhelming
    results = search_all_adrs("authentication")  # 50+ results
    agent_struggles_to_understand_what_matters()
    
    # NEW WAY - Curated Intelligence  
    context = adr_planning_context({
        "task_description": "implement OAuth2 login flow",
        "technologies_mentioned": ["react", "oauth2", "jwt"]
    })
    # Gets exactly what's needed:
    # - "Don't use basic auth (ADR-0003)"
    # - "JWT structure defined in ADR-0007" 
    # - "OAuth provider preference: Auth0 (ADR-0012)"
    # - Focused, actionable, complete
    ```
    
    Args:
        request: Task details and configuration options
        
    Returns:
        Curated context packet with constraints, relevant ADRs, and guidance
    """
    try:
        adr_dir = Path(request.adr_dir)
        
        # Create planning context service
        config = PlanningConfig(
            adr_dir=adr_dir,
            max_relevant_adrs=request.max_relevant_adrs,
            max_token_budget=request.max_tokens
        )
        planner = PlanningContext(config)
        
        # Create task hint
        task_hint = TaskHint(
            task_description=request.task_description,
            changed_files=request.changed_files,
            technologies_mentioned=request.technologies_mentioned,
            task_type=request.task_type,
            priority=request.priority
        )
        
        # Generate context packet
        context_packet = planner.create_context_packet(task_hint)
        
        # Format response with rich context
        return {
            "success": True,
            "context_packet": {
                "task_description": context_packet.task_description,
                "task_type": context_packet.task_type,
                "hard_constraints": context_packet.hard_constraints,
                "relevant_adrs": [
                    {
                        "id": adr.id,
                        "title": adr.title,
                        "status": adr.status.value,
                        "summary": adr.summary,
                        "relevance_score": adr.relevance_score,
                        "relevance_reason": adr.relevance_reason,
                        "key_constraints": adr.key_constraints,
                        "related_technologies": adr.related_technologies
                    }
                    for adr in context_packet.relevant_adrs
                ],
                "guidance": [
                    {
                        "type": g.guidance_type,
                        "priority": g.priority,
                        "message": g.message,
                        "source_adrs": g.source_adrs,
                        "actionable": g.actionable
                    }
                    for g in context_packet.guidance
                ],
                "summary": context_packet.summary,
                "token_estimate": context_packet.token_estimate,
                "contract_hash": context_packet.contract_hash
            },
            "agent_prompt": context_packet.to_agent_prompt(),
            "cited_adrs": context_packet.get_cited_adrs(),
            "statistics": {
                "total_relevant_adrs": len(context_packet.relevant_adrs),
                "guidance_items": len(context_packet.guidance),
                "hard_constraints": len(context_packet.hard_constraints),
                "token_usage": context_packet.token_estimate,
                "token_budget": request.max_tokens
            },
            "message": f"📋 Generated context for '{request.task_description}' with {len(context_packet.relevant_adrs)} relevant ADRs",
            "workflow_guidance": [
                "Use the agent_prompt directly in your planning context",
                "Reference cited_adrs for detailed information when needed",
                "Follow hard_constraints as non-negotiable requirements",
                "Apply contextual guidance based on priority levels",
                f"Token usage: {context_packet.token_estimate}/{request.max_tokens}"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to generate planning context",
            "guidance": [
                "Ensure ADR directory exists and contains valid ADRs",
                "Check that task description is clear and specific",
                "Verify file paths in changed_files are valid if provided",
                "Consider reducing max_relevant_adrs if encountering issues"
            ]
        }


@mcp.tool()
def adr_planning_bulk(request: ADRPlanningBulkRequest) -> Dict[str, Any]:
    """Generate planning context for multiple related tasks.
    
    🎯 BATCH PLANNING: Perfect for planning complex features with multiple
    sub-tasks, or understanding architectural context across related work items.
    
    💡 WHEN TO USE:
    - Planning complex features broken into multiple tasks
    - Understanding context across related user stories or tickets
    - Batch processing multiple development work items
    - Getting consistent architectural guidance across a project phase
    
    📊 RETURNS:
    - Individual context packets for each task
    - Consolidated guidance across all tasks
    - Common constraints that apply to all tasks
    - Optimization recommendations for related work
    
    Args:
        request: List of tasks and their details
        
    Returns:
        Bulk context results with individual and consolidated guidance
    """
    try:
        adr_dir = Path(request.adr_dir)
        config = PlanningConfig(adr_dir=adr_dir)
        planner = PlanningContext(config)
        
        context_packets = []
        all_cited_adrs = set()
        all_technologies = set()
        
        # Generate context for each task
        for task_data in request.tasks:
            task_hint = TaskHint(
                task_description=task_data["task_description"],
                changed_files=task_data.get("changed_files"),
                technologies_mentioned=task_data.get("technologies_mentioned"),
                task_type=task_data.get("task_type"),
                priority=task_data.get("priority", "medium")
            )
            
            try:
                context_packet = planner.create_context_packet(task_hint)
                context_packets.append({
                    "task_description": task_data["task_description"],
                    "context_packet": context_packet,
                    "success": True
                })
                all_cited_adrs.update(context_packet.get_cited_adrs())
                for adr in context_packet.relevant_adrs:
                    all_technologies.update(adr.related_technologies)
                    
            except Exception as e:
                context_packets.append({
                    "task_description": task_data["task_description"],
                    "error": str(e),
                    "success": False
                })
        
        # Generate consolidated guidance
        successful_packets = [cp for cp in context_packets if cp["success"]]
        consolidated_guidance = self._consolidate_guidance(successful_packets)
        
        return {
            "success": True,
            "individual_contexts": [
                {
                    "task": cp["task_description"],
                    "success": cp["success"],
                    **({"agent_prompt": cp["context_packet"].to_agent_prompt(),
                        "relevant_adrs": len(cp["context_packet"].relevant_adrs),
                        "token_estimate": cp["context_packet"].token_estimate}
                       if cp["success"] else {"error": cp.get("error")})
                }
                for cp in context_packets
            ],
            "consolidated": {
                "common_adrs": list(all_cited_adrs),
                "common_technologies": list(all_technologies),
                "guidance": consolidated_guidance,
                "total_tasks": len(request.tasks),
                "successful_contexts": len(successful_packets)
            },
            "message": f"Generated planning context for {len(successful_packets)}/{len(request.tasks)} tasks",
            "workflow_guidance": [
                "Review individual contexts for task-specific guidance",
                "Apply consolidated guidance across all related tasks",
                "Reference common ADRs for consistent architectural decisions",
                "Consider task dependencies based on shared constraints"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Bulk planning context generation failed",
            "guidance": [
                "Check that all tasks have valid task_description fields",
                "Ensure ADR directory is accessible",
                "Verify task data structure matches expected format"
            ]
        }


@mcp.tool()
def adr_planning_status(request: ADRPlanningContextRequest) -> Dict[str, Any]:
    """Get status of the planning context service.
    
    🎯 SERVICE HEALTH: Check the readiness and capabilities of the planning
    context system, useful for debugging and understanding current state.
    
    💡 WHEN TO USE:
    - Debugging planning context issues
    - Understanding available ADRs and their status
    - Checking service configuration
    - Validating setup before using planning context tools
    
    Args:
        request: Configuration for status check
        
    Returns:
        Service status, statistics, and configuration details
    """
    try:
        adr_dir = Path(request.adr_dir)
        config = PlanningConfig(
            adr_dir=adr_dir,
            max_relevant_adrs=request.max_relevant_adrs,
            max_token_budget=request.max_tokens
        )
        planner = PlanningContext(config)
        
        # Get service status
        status = planner.get_service_status()
        
        return {
            "success": True,
            "service_status": status,
            "capabilities": {
                "task_analysis": "Understands task types and extracts technologies",
                "relevance_ranking": "Scores ADRs by relevance to specific tasks",
                "guidance_generation": "Creates contextual promptlets and warnings",
                "token_optimization": "Fits context within specified budget",
                "bulk_processing": "Handles multiple related tasks"
            },
            "configuration": {
                "adr_directory": str(adr_dir),
                "max_relevant_adrs": config.max_relevant_adrs,
                "max_token_budget": config.max_token_budget,
                "ranking_strategy": config.ranking_strategy.value,
                "include_superseded": config.include_superseded
            },
            "message": "Planning context service status retrieved",
            "guidance": [
                "Service ready" if status["service_ready"] else "Service needs attention",
                f"Found {status.get('statistics', {}).get('total_adrs', 0)} total ADRs",
                f"Found {status.get('statistics', {}).get('accepted_adrs', 0)} accepted ADRs",
                "Use adr_planning_context() to generate curated guidance for tasks"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get planning context service status",
            "guidance": [
                "Check ADR directory path and permissions",
                "Ensure ADR directory contains valid ADR files",
                "Verify planning context service dependencies are available"
            ]
        }


def _consolidate_guidance(context_packets: List[Dict]) -> List[str]:
    """Helper function to consolidate guidance across multiple context packets."""
    guidance_counts = {}
    
    for packet_data in context_packets:
        if packet_data["success"]:
            context_packet = packet_data["context_packet"]
            for guidance in context_packet.guidance:
                key = f"{guidance.guidance_type}:{guidance.message}"
                if key not in guidance_counts:
                    guidance_counts[key] = {"count": 0, "guidance": guidance}
                guidance_counts[key]["count"] += 1
    
    # Return most common guidance items
    sorted_guidance = sorted(
        guidance_counts.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )
    
    return [
        f"{item[1]['guidance'].message} (applies to {item[1]['count']} tasks)"
        for item in sorted_guidance[:5]
    ]


# MCP Resources

@mcp.resource("file://adr.index.json")
def adr_index_resource() -> str:
    """Provide current ADR index as a resource for agent consumption."""
    try:
        index = ADRIndex("docs/adr")
        index.build_index(validate=True)
        return index.to_json()
    except Exception as e:
        return json.dumps({
            "error": str(e), 
            "message": "Failed to load ADR index",
            "guidance": "Ensure ADRs exist and run adr_init() if needed"
        })


def run_server():
    """Run the MCP server using FastMCP."""
    import asyncio
    asyncio.run(mcp.run())


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
    except Exception as e:
        # Log errors to stderr so they don't interfere with MCP protocol
        print(f"MCP Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Default to stdio server for better integration
    run_stdio_server()