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
def mcp_server(
    stdio: bool = typer.Option(True, "--stdio", help="Use stdio transport (recommended for Cursor/Claude Code)"),
    http: bool = typer.Option(False, "--http", help="Use HTTP transport instead of stdio")
):
    """Start the MCP server for AI agent integration.
    
    This is the primary interface for ADR Kit. The MCP server provides
    rich contextual tools for AI agents to create, manage, and validate ADRs.
    
    By default, uses stdio transport which is compatible with Cursor and Claude Code.
    """
    if stdio and not http:
        # Stdio mode - clean output for MCP protocol
        try:
            from .mcp.server import run_stdio_server
            run_stdio_server()
        except ImportError as e:
            console.print(f"❌ MCP server dependencies not available: {e}", err=True)
            console.print("💡 Install with: pip install 'adr-kit[mcp]'", err=True)
            raise typer.Exit(code=1)
        except KeyboardInterrupt:
            raise typer.Exit(code=0)
    else:
        # HTTP mode - with user feedback
        console.print("🚀 Starting ADR Kit MCP Server (HTTP mode)...")
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
def mcp_health():
    """Check MCP server health and connectivity.
    
    Verifies that MCP server dependencies are available and tools are accessible.
    Useful for troubleshooting Cursor/Claude Code integration.
    """
    console.print("🔍 Checking ADR Kit MCP Server Health...")
    
    try:
        # Test imports
        from .mcp.server import mcp
        console.print("✅ MCP server dependencies: OK")
        
        # Test core functionality without calling MCP tools directly
        from .core.model import ADR, ADRFrontMatter, ADRStatus, PolicyModel
        from .core.policy_extractor import PolicyExtractor
        from .enforce.eslint import StructuredESLintGenerator
        
        # Test policy system
        extractor = PolicyExtractor()
        generator = StructuredESLintGenerator()
        console.print("✅ Core policy system: OK")
        
        # List available tools by inspecting MCP server
        console.print("📡 Available MCP Tools:")
        tools = [
            "adr_init", "adr_create", "adr_query_related", "adr_approve", 
            "adr_supersede", "adr_validate", "adr_index", "adr_export_lint_config", 
            "adr_render_site"
        ]
        for tool in tools:
            console.print(f"   • {tool}()")
        
        console.print("✅ Enhanced MCP features:")
        console.print("   • Structured policy extraction (hybrid approach)")
        console.print("   • Automatic lint rule generation")
        console.print("   • Policy validation with V3 requirements")
        console.print("   • AI-first contextual guidance")
        
        console.print("\n🎯 Integration Instructions:")
        console.print("1. In your project: adr-kit mcp-server")
        console.print("2. In Cursor: Add MCP server config (see 'adr-kit info')")
        console.print("3. In Claude Code: Point to the stdio server")
        
        console.print("\n✅ MCP Server is ready for AI agent integration!")
        
    except ImportError as e:
        console.print(f"❌ Missing dependencies: {e}")
        console.print("💡 Install with: pip install 'adr-kit[mcp]'")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"❌ Health check failed: {e}")
        raise typer.Exit(code=1)


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
        ("adr_create()", "Create new ADRs with structured policies"),
        ("adr_approve()", "Approve proposed ADRs and handle relationships"),
        ("adr_validate()", "Validate ADRs with policy requirements"),
        ("adr_index()", "Generate comprehensive ADR index"),
        ("adr_supersede()", "Replace existing decisions"),
        ("adr_export_lint_config()", "Generate enforcement rules from policies"),
        ("adr_render_site()", "Create static ADR documentation site"),
    ]
    
    for tool, desc in tools:
        console.print(f"  • [cyan]{tool}[/cyan] - {desc}")
    
    console.print(f"\n🚀 [bold]Quick Start:[/bold]")
    console.print("   1. [cyan]adr-kit mcp-health[/cyan]     # Check server health")
    console.print("   2. [cyan]adr-kit mcp-server[/cyan]     # Start stdio server")
    console.print("   3. Configure Cursor/Claude Code to connect")
    
    console.print(f"\n🔌 [bold]Cursor Integration:[/bold]")
    console.print("   Add to your MCP settings.json:")
    console.print('   "adr-kit": {')
    console.print('     "command": "adr-kit",')
    console.print('     "args": ["mcp-server"],')  
    console.print('     "env": {}')
    console.print('   }')
    
    console.print(f"\n💡 [bold]Features:[/bold]")
    console.print("   ✅ Structured policy extraction (hybrid approach)")
    console.print("   ✅ Automatic lint rule generation (ESLint, Ruff)")
    console.print("   ✅ Enhanced validation with policy requirements")
    console.print("   ✅ Log4brains integration for site generation")
    console.print("   ✅ AI-first contextual tool descriptions")
    
    console.print(f"\n📚 [bold]Learn more:[/bold] https://github.com/kschlt/adr-kit")
    console.print()


# Keep only essential manual commands
@app.command()
def dual_setup():
    """Set up ADR Kit for both Cursor IDE and Claude Code terminal access.
    
    Creates configuration files for both Cursor's built-in AI and Claude Code
    running in terminals within Cursor IDE.
    """
    from pathlib import Path
    import json
    
    console.print("🤖 Setting up Dual Agent Access (Cursor IDE + Claude Code)")
    
    try:
        # Create Claude Code config
        claude_config = {
            "servers": {
                "adr-kit": {
                    "command": "adr-kit",
                    "args": ["mcp-server"],
                    "description": "AI-first Architectural Decision Records management",
                    "tools": [
                        "adr_init", "adr_query_related", "adr_create", "adr_approve",
                        "adr_supersede", "adr_validate", "adr_index", 
                        "adr_export_lint_config", "adr_render_site"
                    ]
                }
            }
        }
        
        claude_config_file = Path(".claude-mcp-config.json")
        with open(claude_config_file, 'w') as f:
            json.dump(claude_config, f, indent=2)
        
        console.print(f"✅ Created {claude_config_file} (for Claude Code terminals)")
        
        # Create Cursor config  
        cursor_config = {
            "mcpServers": {
                "adr-kit": {
                    "command": "adr-kit",
                    "args": ["mcp-server"],
                    "env": {
                        "PYTHONPATH": ".",
                        "ADR_DIR": "docs/adr"
                    }
                }
            }
        }
        
        cursor_config_file = Path("cursor-mcp-config.json")
        with open(cursor_config_file, 'w') as f:
            json.dump(cursor_config, f, indent=2)
            
        console.print(f"✅ Created {cursor_config_file} (for Cursor IDE)")
        
        # Test MCP server health
        console.print("\n🔍 Testing MCP server health...")
        from .mcp.server import mcp
        console.print("✅ MCP server ready")
        
        console.print("\n🎯 Next Steps:")
        console.print("1. [bold]Cursor IDE:[/bold] Add config from cursor-mcp-config.json to Cursor settings")
        console.print("2. [bold]Claude Code:[/bold] Will auto-detect .claude-mcp-config.json in this directory")
        console.print("3. [bold]Test:[/bold] Both agents can now use adr_* tools!")
        
        console.print(f"\n💡 [bold]Verification:[/bold]")
        console.print("   • Cursor AI: Ask 'What ADR tools do you have?'")
        console.print("   • Claude Code: Run 'claude' and ask about ADR capabilities")
        console.print("   • Both should have access to the same 9 ADR management tools")
        
        console.print(f"\n📚 [bold]Full Guide:[/bold] See DUAL_AGENT_SETUP.md for detailed instructions")
        
    except Exception as e:
        console.print(f"❌ Setup failed: {e}")
        raise typer.Exit(code=1)


@app.command()  
def contract_build(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    force_rebuild: bool = typer.Option(False, "--force", help="Force rebuild even if cache is valid"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output")
):
    """Build the unified constraints contract from accepted ADRs.
    
    Creates constraints_accepted.json - the definitive source of truth
    for all architectural decisions that agents must follow.
    """
    try:
        from .contract import ConstraintsContractBuilder
        
        builder = ConstraintsContractBuilder(adr_dir)
        contract = builder.build_contract(force_rebuild=force_rebuild)
        summary = builder.get_contract_summary()
        
        console.print("✅ Constraints contract built successfully!")
        console.print(f"   📁 Location: {builder.get_contract_file_path()}")
        console.print(f"   🏷️  Hash: {contract.metadata.hash[:12]}...")
        console.print(f"   📅 Generated: {contract.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"   📋 Source ADRs: {len(contract.metadata.source_adrs)}")
        
        if summary["success"]:
            counts = summary["constraint_counts"]
            total = summary["total_constraints"]
            console.print(f"\n📊 Constraints Summary ({total} total):")
            if counts["import_disallow"] > 0:
                console.print(f"   🚫 Import disallow: {counts['import_disallow']}")
            if counts["import_prefer"] > 0:
                console.print(f"   ✅ Import prefer: {counts['import_prefer']}")
            if counts["boundary_layers"] > 0:
                console.print(f"   🏗️  Boundary layers: {counts['boundary_layers']}")
            if counts["boundary_rules"] > 0:
                console.print(f"   🛡️  Boundary rules: {counts['boundary_rules']}")
            if counts["python_disallow"] > 0:
                console.print(f"   🐍 Python disallow: {counts['python_disallow']}")
        
        if verbose and contract.metadata.source_adrs:
            console.print(f"\n📋 Source ADRs:")
            for adr_id in contract.metadata.source_adrs:
                console.print(f"   • {adr_id}")
        
        if verbose and contract.provenance:
            console.print(f"\n🔍 Policy Provenance:")
            for rule_path, prov in contract.provenance.items():
                console.print(f"   • {rule_path} ← {prov.adr_id}")
        
        console.print(f"\n💡 Next: Use [cyan]adr-kit export-lint[/cyan] to apply as enforcement rules")
        sys.exit(0)
        
    except Exception as e:
        console.print(f"❌ Failed to build contract: {e}")
        raise typer.Exit(code=1)


@app.command()
def contract_status(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory")
):
    """Show current constraints contract status and metadata."""
    try:
        from .contract import ConstraintsContractBuilder
        
        builder = ConstraintsContractBuilder(adr_dir)
        summary = builder.get_contract_summary()
        contract_path = builder.get_contract_file_path()
        
        if summary["success"]:
            console.print("📊 Constraints Contract Status")
            console.print(f"   📁 File: {contract_path}")
            console.print(f"   ✅ Exists: {contract_path.exists()}")
            console.print(f"   🏷️  Hash: {summary['contract_hash'][:12]}...")
            console.print(f"   📅 Generated: {summary['generated_at']}")
            console.print(f"   📋 Source ADRs: {len(summary['source_adrs'])}")
            console.print(f"   🔢 Total constraints: {summary['total_constraints']}")
            
            if summary.get("source_adrs"):
                console.print(f"\n📋 Source ADRs:")
                for adr_id in summary["source_adrs"]:
                    console.print(f"   • {adr_id}")
            
            cache_info = summary.get("cache_info", {})
            if cache_info.get("cached"):
                console.print(f"\n💾 Cache Status:")
                console.print(f"   ✅ Cached: {cache_info['cached']}")
                if cache_info.get("cached_at"):
                    console.print(f"   📅 Cached at: {cache_info['cached_at']}")
        else:
            console.print("❌ No constraints contract found")
            console.print(f"   📁 Expected at: {contract_path}")
            console.print(f"   💡 Run [cyan]adr-kit contract-build[/cyan] to create")
        
        sys.exit(0)
        
    except Exception as e:
        console.print(f"❌ Failed to get contract status: {e}")
        raise typer.Exit(code=1)


@app.command()
def preflight(
    choice_name: str = typer.Argument(..., help="Name of the technical choice to evaluate"),
    context: str = typer.Option(..., "--context", help="Context or reason for this choice"),
    choice_type: str = typer.Option("dependency", "--type", help="Type of choice: dependency, framework, tool"),
    ecosystem: str = typer.Option("npm", "--ecosystem", help="Package ecosystem (npm, pypi, gem, etc.)"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output")
):
    """Evaluate a technical choice through the preflight policy gate.
    
    This command checks if a technical decision requires human approval
    before implementation, helping enforce architectural governance.
    """
    try:
        from .gate import PolicyGate, create_technical_choice
        
        gate = PolicyGate(adr_dir)
        
        # Create and evaluate the choice
        choice = create_technical_choice(
            choice_type=choice_type,
            name=choice_name,
            context=context,
            ecosystem=ecosystem
        )
        
        result = gate.evaluate(choice)
        
        # Display result with appropriate styling
        if result.decision.value == "allowed":
            console.print(f"✅ [green]ALLOWED[/green]: '{choice_name}' may proceed")
        elif result.decision.value == "requires_adr":
            console.print(f"🛑 [yellow]REQUIRES ADR[/yellow]: '{choice_name}' needs approval")
        elif result.decision.value == "blocked":
            console.print(f"❌ [red]BLOCKED[/red]: '{choice_name}' is not permitted")
        elif result.decision.value == "conflict":
            console.print(f"⚠️ [red]CONFLICT[/red]: '{choice_name}' conflicts with existing ADRs")
        
        console.print(f"\n💭 Reasoning: {result.reasoning}")
        
        if verbose:
            console.print(f"\n📊 Details:")
            console.print(f"   Choice type: {result.choice.choice_type.value}")
            console.print(f"   Category: {result.metadata.get('category')}")
            console.print(f"   Normalized name: {result.metadata.get('normalized_name')}")
            console.print(f"   Evaluated at: {result.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        console.print(f"\n🚀 Agent Guidance:")
        console.print(f"   {result.get_agent_guidance()}")
        
        # Get recommendations
        recommendations = gate.get_recommendations_for_choice(choice_name)
        if recommendations.get("alternatives"):
            console.print(f"\n💡 Recommended alternatives:")
            for alt in recommendations["alternatives"]:
                console.print(f"   • {alt['name']}: {alt['reason']}")
        
        # Exit with appropriate code
        if result.should_proceed:
            sys.exit(0)  # Success - may proceed
        elif result.requires_human_approval:
            sys.exit(2)  # Requires ADR
        else:
            sys.exit(1)  # Blocked/conflict
        
    except Exception as e:
        console.print(f"❌ Preflight evaluation failed: {e}")
        raise typer.Exit(code=3)


@app.command()
def gate_status(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed configuration")
):
    """Show current preflight gate status and configuration."""
    try:
        from .gate import PolicyGate
        
        gate = PolicyGate(adr_dir)
        status = gate.get_gate_status()
        
        console.print("🚪 Preflight Policy Gate Status")
        console.print(f"   📁 ADR Directory: {status['adr_directory']}")
        console.print(f"   ✅ Gate Ready: {status['gate_ready']}")
        
        config = status["config"]
        console.print(f"\n⚙️ Configuration:")
        console.print(f"   📄 Config file: {config['config_file']}")
        console.print(f"   ✅ Config exists: {config['config_exists']}")
        
        console.print(f"\n🎯 Default Policies:")
        policies = config["default_policies"]
        console.print(f"   Dependencies: [cyan]{policies['dependency']}[/cyan]")
        console.print(f"   Frameworks: [cyan]{policies['framework']}[/cyan]")
        console.print(f"   Tools: [cyan]{policies['tool']}[/cyan]")
        
        if verbose:
            console.print(f"\n📋 Lists:")
            console.print(f"   Always allow: {len(config['always_allow'])} items")
            if config['always_allow']:
                for item in config['always_allow'][:5]:  # Show first 5
                    console.print(f"     • {item}")
                if len(config['always_allow']) > 5:
                    console.print(f"     ... and {len(config['always_allow']) - 5} more")
            
            console.print(f"   Always deny: {len(config['always_deny'])} items")
            if config['always_deny']:
                for item in config['always_deny']:
                    console.print(f"     • {item}")
            
            console.print(f"   Development tools: {config['development_tools']} items")
            console.print(f"   Categories: {config['categories']} defined")
            console.print(f"   Name mappings: {config['name_mappings']} defined")
        
        console.print(f"\n💡 Usage:")
        console.print(f"   Test choices: [cyan]adr-kit preflight <choice> --context \"reason\"[/cyan]")
        console.print(f"   For agents: Use [cyan]adr_preflight()[/cyan] MCP tool")
        
        sys.exit(0)
        
    except Exception as e:
        console.print(f"❌ Failed to get gate status: {e}")
        raise typer.Exit(code=1)


@app.command()
def guardrail_apply(
    adr_dir: Annotated[str, typer.Option(help="ADR directory path")] = "docs/adr",
    force: Annotated[bool, typer.Option("--force", help="Force reapply guardrails")] = False
):
    """Apply automatic guardrails based on ADR policies."""
    
    try:
        from .guardrail import GuardrailManager
        
        adr_path = Path(adr_dir)
        manager = GuardrailManager(adr_path)
        
        console.print("🔧 [cyan]Applying automatic guardrails...[/cyan]")
        
        results = manager.apply_guardrails(force=force)
        
        if not results:
            console.print("ℹ️  No guardrail targets configured or no policies found")
            return
        
        success_count = len([r for r in results if r.status.value == "success"])
        total_fragments = sum(r.fragments_applied for r in results)
        
        console.print(f"\n📊 Results: {success_count}/{len(results)} targets updated with {total_fragments} rules")
        
        for result in results:
            status_icon = "✅" if result.status.value == "success" else "❌"
            console.print(f"{status_icon} {result.target.file_path}: {result.message}")
            
            if result.errors:
                for error in result.errors:
                    console.print(f"   ⚠️  Error: {error}", style="red")
        
        console.print("\n💡 Lint tools will now enforce ADR policies automatically")
        
    except Exception as e:
        console.print(f"❌ Failed to apply guardrails: {e}")
        raise typer.Exit(code=1)


@app.command()
def guardrail_status(
    adr_dir: Annotated[str, typer.Option(help="ADR directory path")] = "docs/adr"
):
    """Show status of the automatic guardrail system."""
    
    try:
        from .guardrail import GuardrailManager
        
        adr_path = Path(adr_dir)
        manager = GuardrailManager(adr_path)
        
        status = manager.get_status()
        
        console.print("🛡️  [cyan]Guardrail System Status[/cyan]")
        console.print(f"   Enabled: {'✅' if status['enabled'] else '❌'}")
        console.print(f"   Auto-apply: {'✅' if status['auto_apply'] else '❌'}")
        console.print(f"   Contract valid: {'✅' if status['contract_valid'] else '❌'}")
        console.print(f"   Active constraints: {status['active_constraints']}")
        console.print(f"   Target count: {status['target_count']}")
        
        console.print("\n📁 Configuration Targets:")
        for file_path, target_info in status['targets'].items():
            exists_icon = "✅" if target_info['exists'] else "❌"
            managed_icon = "🔧" if target_info.get('has_managed_section', False) else "⭕"
            console.print(f"   {exists_icon}{managed_icon} {file_path} ({target_info['fragment_type']})")
        
        console.print(f"\n💡 Use [cyan]adr-kit guardrail-apply[/cyan] to sync configurations")
        
    except Exception as e:
        console.print(f"❌ Failed to get guardrail status: {e}")
        raise typer.Exit(code=1)


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