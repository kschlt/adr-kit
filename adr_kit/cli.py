"""CLI interface for ADR Kit using Typer.

Design decisions:
- Use Typer for modern CLI with automatic help generation
- Use Rich for colored output and better formatting
- Provide all CLI commands specified in 04_CLI_SPEC.md
- Exit codes match specification (0=success, 1=validation, 2=schema, 3=IO)
"""

from datetime import date
from pathlib import Path
from typing import List, Optional

import sys
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from .core.model import ADR, ADRFrontMatter, ADRStatus
from .core.parse import parse_adr_file, find_adr_files, ParseError
from .core.validate import validate_adr_directory, validate_adr_file, ValidationResult
from .index.json_index import generate_adr_index
from .index.sqlite_index import generate_sqlite_index


app = typer.Typer(
    name="adr-kit",
    help="A toolkit for managing Architectural Decision Records (ADRs) in MADR format. Most functionality is available via MCP server for AI agents.",
    add_completion=False
)
console = Console()


def get_next_adr_id(adr_dir: Path = Path("docs/adr")) -> str:
    """Get the next available ADR ID."""
    if not adr_dir.exists():
        return "ADR-0001"
    
    adr_files = find_adr_files(adr_dir)
    if not adr_files:
        return "ADR-0001"
    
    # Extract numbers from existing ADR files
    max_num = 0
    for file_path in adr_files:
        try:
            adr = parse_adr_file(file_path, strict=False)
            if adr and adr.front_matter.id.startswith("ADR-"):
                num_str = adr.front_matter.id[4:]  # Remove "ADR-" prefix
                if num_str.isdigit():
                    max_num = max(max_num, int(num_str))
        except ParseError:
            continue
    
    return f"ADR-{max_num + 1:04d}"


@app.command()
def init(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory to initialize")
):
    """Initialize ADR structure in repository."""
    try:
        # Create ADR directory
        adr_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .project-index directory  
        index_dir = Path(".project-index")
        index_dir.mkdir(exist_ok=True)
        
        console.print(f"✅ Initialized ADR structure:")
        console.print(f"   📁 {adr_dir} (for ADR files)")
        console.print(f"   📁 {index_dir} (for indexes)")
        
        # Generate initial index files
        try:
            generate_adr_index(adr_dir, adr_dir / "adr-index.json")
            console.print(f"   📄 {adr_dir / 'adr-index.json'} (JSON index)")
        except Exception as e:
            console.print(f"⚠️  Could not generate initial JSON index: {e}")
        
        sys.exit(0)
        
    except Exception as e:
        console.print(f"❌ Failed to initialize ADR structure: {e}")
        raise typer.Exit(code=3)


@app.command()
def mcp_server():
    """Start the MCP server for AI agent integration.
    
    This is the primary interface for ADR Kit. The MCP server provides
    rich contextual tools for AI agents to create, manage, and validate ADRs.
    """
    console.print("🚀 Starting ADR Kit MCP Server...")
    console.print("📡 AI agents can now access ADR management tools")
    console.print("💡 Use MCP tools: adr_create, adr_query_related, adr_approve, etc.")
    
    try:
        from .mcp.server import run_server
        run_server()
    except ImportError as e:
        console.print(f"❌ MCP server dependencies not available: {e}")
        console.print("💡 Install with: pip install 'adr-kit[mcp]'")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n👋 MCP server stopped")
        raise typer.Exit(code=0)


@app.command()
def validate(
    adr_id: Optional[str] = typer.Option(None, "--id", help="Specific ADR ID to validate"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed validation output")
):
    """Validate ADRs."""
    try:
        if adr_id:
            # Validate specific ADR
            adr_files = find_adr_files(adr_dir)
            target_file = None
            
            for file_path in adr_files:
                try:
                    adr = parse_adr_file(file_path, strict=False)
                    if adr and adr.front_matter.id == adr_id:
                        target_file = file_path
                        break
                except ParseError:
                    continue
            
            if not target_file:
                console.print(f"❌ ADR with ID {adr_id} not found")
                raise typer.Exit(code=3)
            
            result = validate_adr_file(target_file)
            results = [result]
        else:
            # Validate all ADRs
            results = validate_adr_directory(adr_dir)
        
        # Display results
        total_adrs = len(results)
        valid_adrs = sum(1 for r in results if r.is_valid)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        
        if verbose or total_errors > 0:
            for result in results:
                if result.adr and result.adr.file_path:
                    file_name = result.adr.file_path.name
                else:
                    file_name = "Unknown file"
                
                if result.is_valid:
                    console.print(f"✅ {file_name}: Valid")
                else:
                    console.print(f"❌ {file_name}: Invalid")
                
                for issue in result.issues:
                    if issue.level == 'error':
                        console.print(f"   ❌ {issue.message}")
                    else:
                        console.print(f"   ⚠️  {issue.message}")
        
        # Summary
        console.print("\n" + "="*50)
        console.print(f"📊 Validation Summary:")
        console.print(f"   Total ADRs: {total_adrs}")
        console.print(f"   Valid ADRs: {valid_adrs}")
        console.print(f"   Errors: {total_errors}")
        console.print(f"   Warnings: {total_warnings}")
        
        if total_errors > 0:
            raise typer.Exit(code=1)  # Validation errors
        else:
            raise typer.Exit(code=0)  # Success
            
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ Validation failed: {e}")
        raise typer.Exit(code=3)


@app.command()
def index(
    out: Path = typer.Option(Path("docs/adr/adr-index.json"), "--out", help="Output path for JSON index"),
    sqlite: Optional[Path] = typer.Option(None, "--sqlite", help="Output path for SQLite database"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    no_validate: bool = typer.Option(False, "--no-validate", help="Skip validation during indexing")
):
    """Generate ADR index files."""
    try:
        validate_adrs = not no_validate
        
        # Generate JSON index
        console.print(f"📝 Generating JSON index...")
        json_index = generate_adr_index(adr_dir, out, validate=validate_adrs)
        
        console.print(f"✅ JSON index generated: {out}")
        console.print(f"   📊 Total ADRs: {json_index.metadata['total_adrs']}")
        
        if json_index.metadata.get('validation_errors'):
            error_count = len(json_index.metadata['validation_errors'])
            console.print(f"   ⚠️  Validation errors: {error_count}")
        
        # Generate SQLite index if requested
        if sqlite:
            console.print(f"🗄️  Generating SQLite index...")
            sqlite_stats = generate_sqlite_index(adr_dir, sqlite, validate=validate_adrs)
            
            console.print(f"✅ SQLite index generated: {sqlite}")
            console.print(f"   📊 Indexed ADRs: {sqlite_stats['indexed']}")
            
            if sqlite_stats['errors']:
                console.print(f"   ⚠️  Errors: {len(sqlite_stats['errors'])}")
        
        raise typer.Exit(code=0)
        
    except Exception as e:
        console.print(f"❌ Index generation failed: {e}")
        raise typer.Exit(code=3)


@app.command()
def info():
    """Show ADR Kit information and MCP usage.
    
    Displays information about ADR Kit's AI-first approach and MCP integration.
    """
    console.print("\n🤖 [bold]ADR Kit - AI-First Architecture Decision Records[/bold]")
    console.print("\nADR Kit is designed for AI agents like Claude Code to autonomously manage")
    console.print("Architectural Decision Records with rich contextual understanding.")
    
    console.print("\n📡 [bold]MCP Server Tools Available:[/bold]")
    tools = [
        ("adr_init()", "Initialize ADR system in repository"),
        ("adr_query_related()", "Find related ADRs before making decisions"),
        ("adr_create()", "Create new ADRs with rich content"),
        ("adr_approve()", "Approve proposed ADRs and handle relationships"),
        ("adr_validate()", "Validate ADRs for compliance"),
        ("adr_index()", "Generate comprehensive ADR index"),
        ("adr_supersede()", "Replace existing decisions"),
    ]
    
    for tool, desc in tools:
        console.print(f"  • [cyan]{tool}[/cyan] - {desc}")
    
    console.print(f"\n🚀 [bold]Start MCP Server:[/bold]")
    console.print("   adr-kit mcp-server")
    
    console.print(f"\n💡 [bold]For AI agents:[/bold] Each MCP tool includes detailed")
    console.print("   contextual guidance on when and how to use it.")
    
    console.print(f"\n📚 [bold]Learn more:[/bold] https://github.com/kschlt/adr-kit")
    console.print()


# Keep only essential manual commands
@app.command()
def legacy():
    """Show legacy CLI commands (use MCP server instead).
    
    Most ADR Kit functionality is now available through the MCP server
    for better AI agent integration. Manual CLI commands are minimal.
    """
    console.print("⚠️  [yellow]Legacy CLI Mode[/yellow]")
    console.print("\nADR Kit is designed for AI agents. Consider using:")
    console.print("• [cyan]adr-kit mcp-server[/cyan] - Start MCP server for AI agents")
    console.print("• [cyan]adr-kit info[/cyan] - Show available MCP tools")
    
    console.print(f"\nMinimal CLI commands still available:")
    console.print("• [dim]adr-kit init[/dim] - Initialize ADR structure")
    console.print("• [dim]adr-kit validate[/dim] - Validate existing ADRs")
    
    console.print(f"\n💡 Use MCP tools for rich, contextual ADR management!")
    console.print()


if __name__ == "__main__":
    import sys
    app()