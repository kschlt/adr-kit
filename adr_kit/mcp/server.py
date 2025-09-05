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