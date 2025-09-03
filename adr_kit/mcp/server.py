"""MCP server for ADR Kit using FastMCP.

Design decisions:
- Use FastMCP for modern MCP server implementation
- Expose all tools specified in 05_MCP_SPEC.md
- Provide both tools (actions) and resources (data access)
- Handle errors gracefully with clear messages for coding agents
"""

import json
import subprocess
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
    """Create a new ADR.
    
    Args:
        payload: ADR creation data
        adr_dir: Directory for ADR files
        
    Returns:
        Dictionary with created ADR ID and path
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
            "message": f"Created ADR {new_id}: {payload.title}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create ADR: {e}"
        }


@mcp.tool()
def adr_supersede(request: ADRSupersedePayload, adr_dir: str = "docs/adr") -> Dict[str, Any]:
    """Create a new ADR that supersedes an existing one.
    
    Args:
        request: Supersede request data
        adr_dir: Directory for ADR files
        
    Returns:
        Dictionary with operation result
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
            "message": f"Created ADR {new_id} superseding {request.old_id}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to supersede ADR: {e}"
        }


@mcp.tool()
def adr_validate(request: ADRValidateRequest) -> Dict[str, Any]:
    """Validate ADRs.
    
    Args:
        request: Validation request
        
    Returns:
        Dictionary with validation results
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
    """Generate or query ADR index.
    
    Args:
        request: Index request
        
    Returns:
        Dictionary with ADR index data
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


# MCP Resources

@mcp.resource("adr.index.json")
def adr_index_resource() -> str:
    """Provide ADR index as a resource."""
    try:
        index = ADRIndex("docs/adr")
        index.build_index(validate=True)
        return index.to_json()
    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to load ADR index"})


def run_server():
    """Run the MCP server."""
    import asyncio
    asyncio.run(mcp.run())


if __name__ == "__main__":
    run_server()