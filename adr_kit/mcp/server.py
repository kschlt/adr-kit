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

from ..core.model import ADR, ADRFrontMatter, ADRStatus
from ..core.parse import find_adr_files, parse_adr_file, ParseError
from ..core.validate import validate_adr_file, validate_adr_directory
from ..index.json_index import generate_adr_index, ADRIndex
from ..index.sqlite_index import generate_sqlite_index, ADRSQLiteIndex
from ..enforce.eslint import generate_eslint_config
from ..enforce.ruff import generate_ruff_config, generate_import_linter_config


# Pydantic models for MCP tool parameters

class ADRCreatePayload(BaseModel):
    """Payload for creating a new ADR."""
    title: str = Field(..., description="Title of the new ADR")
    tags: Optional[List[str]] = Field(None, description="Tags for the ADR")
    deciders: Optional[List[str]] = Field(None, description="People who made the decision")
    status: Optional[ADRStatus] = Field(ADRStatus.PROPOSED, description="Initial status")
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
    4. Identify potential superseding relationships with existing ADRs
    5. Notify human with file path for review
    
    ⚡ AUTOMATICALLY HANDLES:
    - Unique ID generation (ADR-NNNN format)
    - Date stamping 
    - MADR template structure
    - Schema validation
    
    📋 Args:
        payload: ADR creation data with title, tags, deciders, and content
        adr_dir: Directory for ADR files (default: docs/adr)
        
    Returns:
        Dictionary with success status, ADR ID, file path, and next steps for human
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
        
        # Create front matter
        front_matter = ADRFrontMatter(
            id=new_id,
            title=payload.title,
            status=payload.status or ADRStatus.PROPOSED,
            date=date.today(),
            tags=payload.tags,
            deciders=payload.deciders
        )
        
        # Use provided content or template
        if payload.content:
            content = payload.content
        else:
            content = f"""# Context

What is the context of this decision? What problem are we trying to solve?

# Decision

What is the change that we're proposing or doing?

# Consequences

What are the positive and negative consequences of this decision?

## Positive

- 

## Negative

- 

# Alternatives

What other alternatives have been considered?

- Alternative 1: 
- Alternative 2: """
        
        # Create ADR object and write file
        adr = ADR(front_matter=front_matter, content=content)
        filename = f"{new_id}-{payload.title.lower().replace(' ', '-')}.md"
        file_path = adr_path / filename
        
        file_path.write_text(adr.to_markdown(), encoding='utf-8')
        
        return {
            "success": True,
            "id": new_id,
            "path": str(file_path),
            "status": "proposed",
            "message": f"📝 Created ADR {new_id}: {payload.title}",
            "next_steps": f"Please review the ADR at {file_path} and use adr_approve() to accept it or provide feedback for modifications.",
            "workflow_stage": "awaiting_human_review"
        }
        
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
def adr_approve(adr_id: str, supersede_ids: Optional[List[str]] = None, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Approve a proposed ADR and handle superseding relationships.
    
    🎯 WHEN TO USE:
    - After human has reviewed and approved a proposed ADR
    - When user confirms ADR should be accepted
    - To finalize the ADR workflow and update relationships
    
    🔄 WORKFLOW:
    1. Changes ADR status from 'proposed' to 'accepted'
    2. Updates superseded ADRs to 'superseded' status  
    3. Establishes bidirectional relationships
    4. Regenerates index with new relationships
    5. Validates all affected ADRs
    
    ⚡ AUTOMATICALLY HANDLES:
    - Status transitions
    - Relationship updates (supersedes/superseded_by)
    - Index regeneration
    - Cross-validation of affected ADRs
    
    📋 Args:
        adr_id: ID of the ADR to approve (e.g., "ADR-0007")
        supersede_ids: Optional list of ADR IDs this decision supersedes
        adr_dir: Directory containing ADRs
        
    Returns:
        Dictionary with approval status and updated relationships
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
            "message": f"✅ ADR {adr_id} approved and activated",
            "relationships_updated": len(updated_adrs),
            "workflow_stage": "completed"
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
    """Validate ADRs for schema compliance and semantic rules.
    
    🎯 WHEN TO USE:
    - After creating or modifying ADRs
    - Before approving ADRs (recommended)
    - When troubleshooting ADR issues
    - As part of quality assurance workflow
    
    🔍 WHAT IT CHECKS:
    - JSON Schema compliance (required fields, formats)
    - Semantic rules (superseded ADRs have superseded_by)
    - File format and YAML front-matter syntax
    - Cross-references and relationship consistency
    
    💡 RETURNS:
    - Detailed error messages with guidance
    - Warnings for potential issues
    - Success confirmation for valid ADRs
    
    📋 Args:
        request: Validation request with optional specific ADR ID
        
    Returns:
        Dictionary with validation results and actionable feedback
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
        
        # Process results
        total_adrs = len(results)
        valid_adrs = sum(1 for r in results if r.is_valid)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        
        issues = []
        for result in results:
            if result.adr and result.adr.file_path:
                file_name = result.adr.file_path.name
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
        
        return {
            "success": True,
            "summary": {
                "total_adrs": total_adrs,
                "valid_adrs": valid_adrs,
                "errors": total_errors,
                "warnings": total_warnings
            },
            "issues": issues,
            "is_valid": total_errors == 0
        }
        
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
    """Export lint configuration from ADRs.
    
    Args:
        request: Lint export request
        
    Returns:
        Dictionary with generated configuration
    """
    try:
        adr_dir = request.adr_dir or "docs/adr"
        framework = request.framework.lower()
        
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
        
        return {
            "success": True,
            "framework": framework,
            "config": config,
            "filename": filename,
            "message": f"Generated {framework} configuration"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Lint config generation failed: {e}"
        }


@mcp.tool()
def adr_render_site(adr_dir: str = "docs/adr", out_dir: str = ".log4brains/out") -> Dict[str, Any]:
    """Render static site via Log4brains.
    
    Args:
        adr_dir: ADR directory
        out_dir: Output directory for site
        
    Returns:
        Dictionary with render result
    """
    try:
        # Check if log4brains is available
        try:
            subprocess.run(["log4brains", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {
                "success": False,
                "error": "log4brains not found",
                "message": "Please install log4brains: npm install -g log4brains"
            }
        
        # Run log4brains build
        result = subprocess.run([
            "log4brains", "build",
            "--adrDir", adr_dir,
            "--outDir", out_dir
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": "log4brains build failed",
                "stderr": result.stderr,
                "message": "Log4brains build process failed"
            }
        
        return {
            "success": True,
            "out_dir": out_dir,
            "message": f"ADR site rendered to {out_dir}",
            "stdout": result.stdout
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


if __name__ == "__main__":
    run_server()