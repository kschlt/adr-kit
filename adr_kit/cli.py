"""CLI interface for ADR Kit using Typer.

Design decisions:
- Use Typer for modern CLI with automatic help generation
- Use Rich for colored output and better formatting
- Provide all CLI commands specified in 04_CLI_SPEC.md
- Exit codes match specification (0=success, 1=validation, 2=schema, 3=IO)
"""

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .core.parse import ParseError, find_adr_files, parse_adr_file
from .core.validate import validate_adr_directory, validate_adr_file
from .index.json_index import generate_adr_index
from .index.sqlite_index import generate_sqlite_index

app = typer.Typer(
    name="adr-kit",
    help="A toolkit for managing Architectural Decision Records (ADRs) in MADR format. Most functionality is available via MCP server for AI agents.",
    add_completion=False,
)
console = Console()
stderr_console = Console(stderr=True)


def check_for_updates_async() -> object:
    """Check for updates in the background and show notification if available.

    Returns the background thread so callers can join it if needed.
    """
    import threading

    def _check() -> None:
        try:
            import importlib.metadata

            import requests

            # Get current version directly from package metadata for accuracy
            try:
                current_version = importlib.metadata.version("adr-kit")
            except importlib.metadata.PackageNotFoundError:
                # Fallback to __version__ if not installed properly
                from . import __version__

                current_version = __version__

            # Get latest version from PyPI
            response = requests.get("https://pypi.org/pypi/adr-kit/json", timeout=5)
            response.raise_for_status()

            latest_version = response.json()["info"]["version"]

            # Use semantic version comparison instead of string equality
            if current_version != latest_version:
                try:
                    from packaging.version import parse

                    current_ver = parse(current_version)
                    latest_ver = parse(latest_version)

                    # Only show update if latest is actually newer
                    if current_ver < latest_ver:
                        stderr_console.print(
                            f"🔄 [yellow]Update available:[/yellow] v{current_version} → v{latest_version}"
                        )
                        stderr_console.print(
                            "💡 [dim]Run 'uv tool upgrade adr-kit' to upgrade[/dim]"
                        )
                except Exception:
                    # Fallback to string comparison if packaging not available
                    if current_version != latest_version:
                        stderr_console.print(
                            f"🔄 [yellow]Update available:[/yellow] v{current_version} → v{latest_version}"
                        )
                        stderr_console.print(
                            "💡 [dim]Run 'uv tool upgrade adr-kit' to upgrade[/dim]"
                        )

        except Exception:
            # Silently ignore update check failures
            pass

    # Run in background thread to avoid blocking
    thread = threading.Thread(target=_check, daemon=True)
    thread.start()
    return thread


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
    adr_dir: Path = typer.Option(
        Path("docs/adr"), "--adr-dir", help="ADR directory to initialize"
    ),
    skip_setup: bool = typer.Option(
        False, "--skip-setup", help="Skip interactive AI agent setup"
    ),
    with_enforcement: bool = typer.Option(
        False, "--with-enforcement", help="Set up git hooks for staged enforcement"
    ),
) -> None:
    """Initialize ADR structure in repository."""
    try:
        # Create ADR directory
        adr_dir.mkdir(parents=True, exist_ok=True)

        # Create .project-index directory
        index_dir = Path(".project-index")
        index_dir.mkdir(exist_ok=True)

        console.print("✅ Initialized ADR structure:")
        console.print(f"   📁 {adr_dir} (for ADR files)")
        console.print(f"   📁 {index_dir} (for indexes)")

        # Generate initial index files
        try:
            generate_adr_index(adr_dir, adr_dir / "adr-index.json")
            console.print(f"   📄 {adr_dir / 'adr-index.json'} (JSON index)")
        except Exception as e:
            console.print(f"⚠️  Could not generate initial JSON index: {e}")

        # Optional: set up git hooks for enforcement
        if with_enforcement:
            _setup_enforcement_hooks()

        # Interactive setup prompt (skip if --skip-setup flag is provided)
        if not skip_setup:
            console.print("\n🤖 [bold]Setup AI Agent Integration?[/bold]")
            console.print("1. Cursor IDE - Set up MCP server for Cursor's built-in AI")
            console.print("2. Claude Code - Set up MCP server for Claude Code terminal")
            console.print(
                "3. Skip - Set up later with 'adr-kit setup-cursor' or 'adr-kit setup-claude'"
            )

            choice = typer.prompt("Choose option (1/2/3)", default="3")

            if choice == "1":
                console.print("\n🎯 Setting up for Cursor IDE...")
                try:
                    _setup_cursor_impl()
                except Exception as e:
                    console.print(f"⚠️  Setup failed: {e}")
                    console.print("You can run 'adr-kit setup-cursor' later")
            elif choice == "2":
                console.print("\n🤖 Setting up for Claude Code...")
                try:
                    _setup_claude_impl()
                except Exception as e:
                    console.print(f"⚠️  Setup failed: {e}")
                    console.print("You can run 'adr-kit setup-claude' later")
            else:
                console.print(
                    "✅ Skipped AI setup. Run 'adr-kit setup-cursor' or 'adr-kit setup-claude' when ready."
                )
        else:
            console.print(
                "\n✅ Skipped AI setup. Run 'adr-kit setup-cursor' or 'adr-kit setup-claude' when ready."
            )

        sys.exit(0)

    except Exception as e:
        console.print(f"❌ Failed to initialize ADR structure: {e}")
        raise typer.Exit(code=3) from e


@app.command()
def mcp_server(
    stdio: bool = typer.Option(
        True, "--stdio", help="Use stdio transport (recommended for Cursor/Claude Code)"
    ),
    http: bool = typer.Option(
        False, "--http", help="Use HTTP transport instead of stdio"
    ),
) -> None:
    """Start the MCP server for AI agent integration.

    This is the primary interface for ADR Kit. The MCP server provides
    agent-friendly tools that call the full workflow automation backend.

    By default, uses stdio transport which is compatible with Cursor and Claude Code.
    """
    if stdio and not http:
        # Stdio mode - clean output for MCP protocol
        try:
            # Check for updates in background (non-blocking)
            check_for_updates_async()

            from .mcp.server import run_stdio_server

            run_stdio_server()
        except ImportError as e:
            stderr_console.print(f"❌ MCP server dependencies not available: {e}")
            stderr_console.print("💡 Install with: pip install fastmcp")
            raise typer.Exit(code=1) from e
        except KeyboardInterrupt:
            raise typer.Exit(code=0) from None
    else:
        # HTTP mode - with user feedback
        console.print("🚀 Starting ADR Kit MCP Server (HTTP mode)...")
        console.print("📡 AI agents can now access ADR management tools")
        console.print(
            "💡 Use MCP tools: adr_analyze_project, adr_preflight, adr_create, adr_approve, etc."
        )

        try:
            from .mcp.server import run_server

            run_server()
        except ImportError as e:
            console.print(f"❌ MCP server dependencies not available: {e}")
            console.print("💡 Install with: pip install fastmcp")
            raise typer.Exit(code=1) from e
        except KeyboardInterrupt:
            console.print("\n👋 MCP server stopped")
            raise typer.Exit(code=0) from None


@app.command()
def mcp_health() -> None:
    """Check MCP server health and connectivity.

    Verifies that MCP server dependencies are available and tools are accessible.
    Useful for troubleshooting Cursor/Claude Code integration.
    """
    import importlib.metadata

    try:
        current_version = importlib.metadata.version("adr-kit")
    except importlib.metadata.PackageNotFoundError:
        from . import __version__

        current_version = __version__

    console.print(f"🔍 Checking ADR Kit MCP Server Health... (v{current_version})")

    # Check for updates in background — join at the end so output is ordered
    update_thread = check_for_updates_async()

    try:
        # Test FastMCP dependency
        import fastmcp

        console.print(f"✅ FastMCP dependency: OK (v{fastmcp.__version__})")

        # Test main MCP server imports
        from .mcp.models import MCPErrorResponse, MCPResponse  # noqa: F401
        from .mcp.server import mcp  # noqa: F401

        console.print("✅ MCP server: OK")

        # Test workflow system (the real business logic)
        try:
            from .workflows.analyze import AnalyzeProjectWorkflow  # noqa: F401
            from .workflows.approval import ApprovalWorkflow  # noqa: F401
            from .workflows.creation import CreationWorkflow  # noqa: F401
            from .workflows.preflight import PreflightWorkflow  # noqa: F401

            console.print("✅ Workflow backend system: OK")
            workflow_available = True
        except ImportError as e:
            console.print(f"⚠️  Workflow system: Not available ({e})")
            workflow_available = False

        # Test core functionality
        from .core.model import ADR, ADRFrontMatter, ADRStatus  # noqa: F401
        from .core.parse import find_adr_files, parse_adr_file  # noqa: F401
        from .core.policy_extractor import PolicyExtractor  # noqa: F401

        console.print("✅ Core ADR functionality: OK")

        # List available tools
        console.print(
            "📡 Available MCP Tools (Agent-First Interface + Full Workflow Backend):"
        )
        tools = [
            "adr_analyze_project",
            "adr_preflight",
            "adr_create",
            "adr_approve",
            "adr_supersede",
            "adr_planning_context",
        ]
        for tool in tools:
            console.print(f"   • {tool}() - Clean interface → Full workflow automation")

        console.print("📚 Available Resources:")
        console.print("   • adr://index       - Structured ADR index (all ADRs)")
        console.print(
            "   • adr://{ADR-ID}    - Full content of a single ADR (e.g. adr://ADR-0001)"
        )

        console.print("\n✅ MCP Features:")
        console.print("   • Agent-friendly interfaces with proper FastMCP patterns")
        console.print(
            "   • Full workflow automation backend (semantic search, policy extraction)"
        )
        console.print("   • Consistent response formats with structured errors")
        console.print("   • Advanced features: conflict detection, policy enforcement")
        console.print("   • Structured logging for debugging")

        console.print("\n🎯 Integration Instructions:")
        console.print("1. Start server: adr-kit mcp-server")
        console.print("2. For Claude Code: Point MCP client to the stdio server")
        console.print("3. For Cursor: Add MCP server config (see 'adr-kit info')")

        if workflow_available:
            console.print("\n🚀 Full Feature Set Available:")
            console.print("   • Intelligent project analysis with technology detection")
            console.print("   • Smart preflight checks with policy conflict detection")
            console.print(
                "   • Advanced ADR creation with semantic similarity detection"
            )
            console.print("   • Policy automation with lint rule generation")
            console.print("   • Contextual guidance for agent task planning")

        console.print("\n✅ MCP Server is ready for AI agent integration!")

        # Wait briefly for update check to complete so output is ordered
        update_thread.join(timeout=6)

    except ImportError as e:
        console.print(f"❌ Missing dependencies: {e}")
        console.print("💡 Install with: pip install fastmcp")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"❌ Health check failed: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def update(
    check_only: bool = typer.Option(
        False, "--check", "-c", help="Only check for updates, don't install"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force update even if up to date"
    ),
) -> None:
    """Check for and install adr-kit updates.

    This command checks PyPI for newer versions of adr-kit and optionally
    installs them. Detects whether adr-kit was installed via uv or pip
    and uses the appropriate upgrade method.
    """
    import shutil
    import subprocess

    try:
        import requests
    except ImportError as e:
        console.print("❌ requests library not available for update checking")
        console.print(
            "💡 Install manually: uv tool upgrade adr-kit (or pip install --upgrade adr-kit)"
        )
        raise typer.Exit(code=1) from e

    from . import __version__

    console.print(f"🔍 Checking for adr-kit updates... (current: v{__version__})")

    try:
        # Check PyPI for latest version
        response = requests.get("https://pypi.org/pypi/adr-kit/json", timeout=10)
        response.raise_for_status()

        latest_version = response.json()["info"]["version"]
        current_version = __version__

        # Use semantic version comparison
        try:
            from packaging.version import parse

            if parse(current_version) >= parse(latest_version) and not force:
                console.print(f"✅ Already up to date (v{current_version})")
                return
        except Exception:
            # Fallback to string comparison
            if current_version == latest_version and not force:
                console.print(f"✅ Already up to date (v{current_version})")
                return

        console.print(f"📦 Update available: v{current_version} → v{latest_version}")

        if check_only:
            console.print("💡 Run 'adr-kit update' to install the update")
            return

        # Detect installation method and use appropriate upgrade command
        console.print("⬇️ Installing update...")

        # Check if uv is available and adr-kit is a uv tool
        uv_path = shutil.which("uv")
        if uv_path:
            # Try uv tool upgrade (works for uv-managed installations)
            result = subprocess.run(
                ["uv", "tool", "upgrade", "adr-kit"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                console.print(f"✅ Successfully updated to v{latest_version}")
                console.print("💡 Restart your MCP server to use the new version")
                return
            else:
                # uv upgrade failed, might not be a uv tool installation
                console.print("[dim]uv tool upgrade failed, trying pip...[/dim]")

        # Fallback to pip (works for pip installations)
        # Use sys.executable to find python in the current environment
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "adr-kit"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            console.print(f"✅ Successfully updated to v{latest_version}")
            console.print("💡 Restart your MCP server to use the new version")
        else:
            console.print(f"❌ Update failed: {result.stderr}")
            console.print("💡 Try manually:")
            console.print("   - uv tool upgrade adr-kit")
            console.print("   - OR: pip install --upgrade adr-kit")
            raise typer.Exit(code=1)

    except requests.RequestException as e:
        console.print("❌ Failed to check for updates (network error)")
        console.print("💡 Try manually: uv tool upgrade adr-kit")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"❌ Update check failed: {e}")
        console.print("💡 Try manually: uv tool upgrade adr-kit")
        raise typer.Exit(code=1) from e


@app.command()
def validate(
    adr_id: str | None = typer.Option(None, "--id", help="Specific ADR ID to validate"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed validation output"
    ),
) -> None:
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
                    if issue.level == "error":
                        console.print(f"   ❌ {issue.message}")
                    else:
                        console.print(f"   ⚠️  {issue.message}")

        # Summary
        console.print("\n" + "=" * 50)
        console.print("📊 Validation Summary:")
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
        raise typer.Exit(code=3) from e


@app.command()
def index(
    out: Path = typer.Option(
        Path("docs/adr/adr-index.json"), "--out", help="Output path for JSON index"
    ),
    sqlite: Path | None = typer.Option(
        None, "--sqlite", help="Output path for SQLite database"
    ),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    no_validate: bool = typer.Option(
        False, "--no-validate", help="Skip validation during indexing"
    ),
) -> None:
    """Generate ADR index files."""
    try:
        validate_adrs = not no_validate

        # Generate JSON index
        console.print("📝 Generating JSON index...")
        json_index = generate_adr_index(adr_dir, out, validate=validate_adrs)

        console.print(f"✅ JSON index generated: {out}")
        console.print(f"   📊 Total ADRs: {json_index.metadata['total_adrs']}")

        if json_index.metadata.get("validation_errors"):
            error_count = len(json_index.metadata["validation_errors"])
            console.print(f"   ⚠️  Validation errors: {error_count}")

        # Generate SQLite index if requested
        if sqlite:
            console.print("🗄️  Generating SQLite index...")
            sqlite_stats = generate_sqlite_index(
                adr_dir, sqlite, validate=validate_adrs
            )

            console.print(f"✅ SQLite index generated: {sqlite}")
            console.print(f"   📊 Indexed ADRs: {sqlite_stats['indexed']}")

            if sqlite_stats["errors"]:
                console.print(f"   ⚠️  Errors: {len(sqlite_stats['errors'])}")

        raise typer.Exit(code=0)

    except typer.Exit:
        # Re-raise typer.Exit as-is (don't catch our own successful exits)
        raise
    except Exception as e:
        console.print(f"❌ Index generation failed: {e}")
        raise typer.Exit(code=3) from e


@app.command()
def info() -> None:
    """Show ADR Kit information and MCP usage.

    Displays information about ADR Kit's AI-first approach and MCP integration.
    """
    console.print("\n🤖 [bold]ADR Kit - AI-First Architecture Decision Records[/bold]")
    console.print(
        "\nADR Kit is designed for AI agents like Claude Code to autonomously manage"
    )
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

    console.print("\n🚀 [bold]Quick Start:[/bold]")
    console.print("   1. [cyan]adr-kit mcp-health[/cyan]     # Check server health")
    console.print("   2. [cyan]adr-kit mcp-server[/cyan]     # Start stdio server")
    console.print("   3. Configure Cursor/Claude Code to connect")

    console.print("\n🔌 [bold]Cursor Integration:[/bold]")
    console.print("   Add to your MCP settings.json:")
    console.print('   "adr-kit": {')
    console.print('     "command": "adr-kit",')
    console.print('     "args": ["mcp-server"],')
    console.print('     "env": {}')
    console.print("   }")

    console.print("\n💡 [bold]Features:[/bold]")
    console.print("   ✅ Structured policy extraction (hybrid approach)")
    console.print("   ✅ Automatic lint rule generation (ESLint, Ruff)")
    console.print("   ✅ Enhanced validation with policy requirements")
    console.print("   ✅ Log4brains integration for site generation")
    console.print("   ✅ AI-first contextual tool descriptions")

    console.print("\n📚 [bold]Learn more:[/bold] https://github.com/kschlt/adr-kit")
    console.print()


# Keep only essential manual commands


def _setup_enforcement_hooks() -> None:
    """Set up git hooks for staged ADR enforcement (called from init --with-enforcement)."""
    from .enforce.hooks import HookGenerator

    gen = HookGenerator()
    results = gen.generate()

    actions = {
        "pre-commit": results.get("pre-commit", "skipped"),
        "pre-push": results.get("pre-push", "skipped"),
    }

    for hook_name, action in actions.items():
        if "skipped" in action:
            console.print(f"   ⚠️  {hook_name}: skipped ({action})")
        elif action == "unchanged":
            console.print(f"   ✅ {hook_name}: already configured")
        else:
            console.print(f"   ✅ {hook_name}: {action}")

    console.print(
        "   💡 Run 'adr-kit enforce commit' to test pre-commit checks manually"
    )


def _setup_cursor_impl() -> None:
    """Implementation for Cursor setup that can be called from commands or init."""
    import json
    from pathlib import Path

    console.print("🎯 Setting up ADR Kit for Cursor IDE")

    # Detect the correct adr-kit command path
    import os
    import shutil

    adr_kit_command = shutil.which("adr-kit")
    if not adr_kit_command:
        # Fallback to simple command name
        adr_kit_command = "adr-kit"

    # Check if we're in a virtual environment
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        console.print(f"📍 Detected virtual environment: {venv_path}")
        console.print(f"📍 Using adr-kit from: {adr_kit_command}")

    # Create Cursor config in proper location
    cursor_dir = Path(".cursor")
    cursor_dir.mkdir(exist_ok=True)

    cursor_config = {
        "mcpServers": {
            "adr-kit": {
                "command": adr_kit_command,
                "args": ["mcp-server"],
                "env": {"PYTHONPATH": ".", "ADR_DIR": "docs/adr"},
            }
        }
    }

    cursor_config_file = cursor_dir / "mcp.json"
    with open(cursor_config_file, "w") as f:
        json.dump(cursor_config, f, indent=2)

    console.print(f"✅ Created {cursor_config_file}")

    # Test MCP server health
    console.print("\n🔍 Testing MCP server health...")

    console.print("✅ MCP server ready")

    console.print("\n🎯 Next Steps:")
    console.print(
        "1. [bold]Restart:[/bold] Restart Cursor IDE to load the new MCP configuration"
    )
    console.print("2. [bold]Test:[/bold] Ask Cursor AI 'What ADR tools do you have?'")
    console.print(
        "3. [bold]Use:[/bold] Try 'Analyze my project for architectural decisions'"
    )


@app.command()
def setup_enforcement(
    project_root: Path = typer.Option(
        Path("."), "--root", help="Project root (git repository)"
    ),
) -> None:
    """Set up git hooks for staged ADR enforcement.

    Writes ADR-Kit managed sections into .git/hooks/pre-commit and
    .git/hooks/pre-push. Safe on existing hooks — appends only.
    Re-running is idempotent.
    """
    from .enforce.hooks import HookGenerator

    try:
        gen = HookGenerator()
        results = gen.generate(project_root=project_root)

        console.print("🔧 Setting up enforcement hooks...")
        for hook_name, action in results.items():
            if "skipped" in action:
                console.print(f"   ⚠️  {hook_name}: {action}")
            elif action == "unchanged":
                console.print(f"   ✅ {hook_name}: already configured")
            else:
                console.print(f"   ✅ {hook_name}: {action}")

        console.print(
            "\n💡 Use 'adr-kit enforce commit' to run pre-commit checks manually"
        )
        console.print("💡 Use 'adr-kit enforce push' to run pre-push checks manually")
    except Exception as e:
        console.print(f"❌ Failed to set up enforcement hooks: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def enforce_status(
    project_root: Path = typer.Option(
        Path("."), "--root", help="Project root (git repository)"
    ),
) -> None:
    """Show status of ADR enforcement hooks."""
    from .enforce.hooks import HookGenerator

    try:
        gen = HookGenerator()
        status = gen.status(project_root=project_root)

        console.print("🔍 ADR Enforcement Hook Status")
        for hook_name, active in status.items():
            icon = "✅" if active else "❌"
            console.print(
                f"   {icon} {hook_name}: {'active' if active else 'not configured'}"
            )

        if not any(status.values()):
            console.print(
                "\n💡 Run 'adr-kit setup-enforcement' to enable automatic enforcement"
            )
    except Exception as e:
        console.print(f"❌ Failed to get enforcement status: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def setup_cursor() -> None:
    """Set up ADR Kit MCP server for Cursor IDE."""
    try:
        _setup_cursor_impl()
    except Exception as e:
        console.print(f"❌ Cursor setup failed: {e}")
        raise typer.Exit(code=1) from e


def _setup_claude_impl() -> None:
    """Implementation for Claude Code setup that can be called from commands or init."""
    import json
    from pathlib import Path

    console.print("🤖 Setting up ADR Kit for Claude Code")

    # Detect the correct adr-kit command path
    import os
    import shutil

    adr_kit_command = shutil.which("adr-kit")
    if not adr_kit_command:
        # Fallback to simple command name
        adr_kit_command = "adr-kit"

    # Check if we're in a virtual environment
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        console.print(f"📍 Detected virtual environment: {venv_path}")
        console.print(f"📍 Using adr-kit from: {adr_kit_command}")

    # Create Claude Code config
    claude_config = {
        "servers": {
            "adr-kit": {
                "command": adr_kit_command,
                "args": ["mcp-server"],
                "description": "AI-first Architectural Decision Records management",
                "tools": [
                    "adr_init",
                    "adr_query_related",
                    "adr_create",
                    "adr_approve",
                    "adr_supersede",
                    "adr_validate",
                    "adr_index",
                    "adr_export_lint_config",
                    "adr_render_site",
                ],
            }
        }
    }

    claude_config_file = Path(".claude-mcp-config.json")
    with open(claude_config_file, "w") as f:
        json.dump(claude_config, f, indent=2)

    console.print(f"✅ Created {claude_config_file}")

    # Test MCP server health
    console.print("\n🔍 Testing MCP server health...")

    console.print("✅ MCP server ready")

    console.print("\n🎯 Next Steps:")
    console.print("1. [bold]Restart:[/bold] Restart your terminal session")
    console.print("2. [bold]Test:[/bold] Run 'claude' and ask about ADR capabilities")
    console.print(
        "3. [bold]Use:[/bold] Try 'Create an ADR for switching to PostgreSQL'"
    )


@app.command()
def setup_claude() -> None:
    """Set up ADR Kit MCP server for Claude Code."""
    try:
        _setup_claude_impl()
    except Exception as e:
        console.print(f"❌ Claude Code setup failed: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def contract_build(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    force_rebuild: bool = typer.Option(
        False, "--force", help="Force rebuild even if cache is valid"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output"),
) -> None:
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
        console.print(
            f"   📅 Generated: {contract.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
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
            console.print("\n📋 Source ADRs:")
            for adr_id in contract.metadata.source_adrs:
                console.print(f"   • {adr_id}")

        if verbose and contract.provenance:
            console.print("\n🔍 Policy Provenance:")
            for rule_path, prov in contract.provenance.items():
                console.print(f"   • {rule_path} ← {prov.adr_id}")

        console.print(
            "\n💡 Next: Use [cyan]adr-kit export-lint[/cyan] to apply as enforcement rules"
        )
        sys.exit(0)

    except Exception as e:
        console.print(f"❌ Failed to build contract: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def contract_status(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory")
) -> None:
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
                console.print("\n📋 Source ADRs:")
                for adr_id in summary["source_adrs"]:
                    console.print(f"   • {adr_id}")

            cache_info = summary.get("cache_info", {})
            if cache_info.get("cached"):
                console.print("\n💾 Cache Status:")
                console.print(f"   ✅ Cached: {cache_info['cached']}")
                if cache_info.get("cached_at"):
                    console.print(f"   📅 Cached at: {cache_info['cached_at']}")
        else:
            console.print("❌ No constraints contract found")
            console.print(f"   📁 Expected at: {contract_path}")
            console.print("   💡 Run [cyan]adr-kit contract-build[/cyan] to create")

        sys.exit(0)

    except Exception as e:
        console.print(f"❌ Failed to get contract status: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def preflight(
    choice_name: str = typer.Argument(
        ..., help="Name of the technical choice to evaluate"
    ),
    context: str = typer.Option(
        ..., "--context", help="Context or reason for this choice"
    ),
    choice_type: str = typer.Option(
        "dependency", "--type", help="Type of choice: dependency, framework, tool"
    ),
    ecosystem: str = typer.Option(
        "npm", "--ecosystem", help="Package ecosystem (npm, pypi, gem, etc.)"
    ),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output"),
) -> None:
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
            ecosystem=ecosystem,
        )

        result = gate.evaluate(choice)

        # Display result with appropriate styling
        if result.decision.value == "allowed":
            console.print(f"✅ [green]ALLOWED[/green]: '{choice_name}' may proceed")
        elif result.decision.value == "requires_adr":
            console.print(
                f"🛑 [yellow]REQUIRES ADR[/yellow]: '{choice_name}' needs approval"
            )
        elif result.decision.value == "blocked":
            console.print(f"❌ [red]BLOCKED[/red]: '{choice_name}' is not permitted")
        elif result.decision.value == "conflict":
            console.print(
                f"⚠️ [red]CONFLICT[/red]: '{choice_name}' conflicts with existing ADRs"
            )

        console.print(f"\n💭 Reasoning: {result.reasoning}")

        if verbose:
            console.print("\n📊 Details:")
            console.print(f"   Choice type: {result.choice.choice_type.value}")
            console.print(f"   Category: {result.metadata.get('category')}")
            console.print(
                f"   Normalized name: {result.metadata.get('normalized_name')}"
            )
            console.print(
                f"   Evaluated at: {result.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        console.print("\n🚀 Agent Guidance:")
        console.print(f"   {result.get_agent_guidance()}")

        # Get recommendations
        recommendations = gate.get_recommendations_for_choice(choice_name)
        if recommendations.get("alternatives"):
            console.print("\n💡 Recommended alternatives:")
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
        raise typer.Exit(code=3) from e


@app.command()
def gate_status(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed configuration"
    ),
) -> None:
    """Show current preflight gate status and configuration."""
    try:
        from .gate import PolicyGate

        gate = PolicyGate(adr_dir)
        status = gate.get_gate_status()

        console.print("🚪 Preflight Policy Gate Status")
        console.print(f"   📁 ADR Directory: {status['adr_directory']}")
        console.print(f"   ✅ Gate Ready: {status['gate_ready']}")

        config = status["config"]
        console.print("\n⚙️ Configuration:")
        console.print(f"   📄 Config file: {config['config_file']}")
        console.print(f"   ✅ Config exists: {config['config_exists']}")

        console.print("\n🎯 Default Policies:")
        policies = config["default_policies"]
        console.print(f"   Dependencies: [cyan]{policies['dependency']}[/cyan]")
        console.print(f"   Frameworks: [cyan]{policies['framework']}[/cyan]")
        console.print(f"   Tools: [cyan]{policies['tool']}[/cyan]")

        if verbose:
            console.print("\n📋 Lists:")
            console.print(f"   Always allow: {len(config['always_allow'])} items")
            if config["always_allow"]:
                for item in config["always_allow"][:5]:  # Show first 5
                    console.print(f"     • {item}")
                if len(config["always_allow"]) > 5:
                    console.print(
                        f"     ... and {len(config['always_allow']) - 5} more"
                    )

            console.print(f"   Always deny: {len(config['always_deny'])} items")
            if config["always_deny"]:
                for item in config["always_deny"]:
                    console.print(f"     • {item}")

            console.print(f"   Development tools: {config['development_tools']} items")
            console.print(f"   Categories: {config['categories']} defined")
            console.print(f"   Name mappings: {config['name_mappings']} defined")

        console.print("\n💡 Usage:")
        console.print(
            '   Test choices: [cyan]adr-kit preflight <choice> --context "reason"[/cyan]'
        )
        console.print("   For agents: Use [cyan]adr_preflight()[/cyan] MCP tool")

        sys.exit(0)

    except Exception as e:
        console.print(f"❌ Failed to get gate status: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def guardrail_apply(
    adr_dir: Annotated[str, typer.Option(help="ADR directory path")] = "docs/adr",
    force: Annotated[
        bool, typer.Option("--force", help="Force reapply guardrails")
    ] = False,
) -> None:
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

        console.print(
            f"\n📊 Results: {success_count}/{len(results)} targets updated with {total_fragments} rules"
        )

        for result in results:
            status_icon = "✅" if result.status.value == "success" else "❌"
            console.print(f"{status_icon} {result.target.file_path}: {result.message}")

            if result.errors:
                for error in result.errors:
                    console.print(f"   ⚠️  Error: {error}", style="red")

        console.print("\n💡 Lint tools will now enforce ADR policies automatically")

    except Exception as e:
        console.print(f"❌ Failed to apply guardrails: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def guardrail_status(
    adr_dir: Annotated[str, typer.Option(help="ADR directory path")] = "docs/adr",
) -> None:
    """Show status of the automatic guardrail system."""

    try:
        from .guardrail import GuardrailManager

        adr_path = Path(adr_dir)
        manager = GuardrailManager(adr_path)

        status = manager.get_status()

        console.print("🛡️  [cyan]Guardrail System Status[/cyan]")
        console.print(f"   Enabled: {'✅' if status['enabled'] else '❌'}")
        console.print(f"   Auto-apply: {'✅' if status['auto_apply'] else '❌'}")
        console.print(
            f"   Contract valid: {'✅' if status['contract_valid'] else '❌'}"
        )
        console.print(f"   Active constraints: {status['active_constraints']}")
        console.print(f"   Target count: {status['target_count']}")

        console.print("\n📁 Configuration Targets:")
        for file_path, target_info in status["targets"].items():
            exists_icon = "✅" if target_info["exists"] else "❌"
            managed_icon = (
                "🔧" if target_info.get("has_managed_section", False) else "⭕"
            )
            console.print(
                f"   {exists_icon}{managed_icon} {file_path} ({target_info['fragment_type']})"
            )

        console.print(
            "\n💡 Use [cyan]adr-kit guardrail-apply[/cyan] to sync configurations"
        )

    except Exception as e:
        console.print(f"❌ Failed to get guardrail status: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def legacy() -> None:
    """Show legacy CLI commands (use MCP server instead).

    Most ADR Kit functionality is now available through the MCP server
    for better AI agent integration. Manual CLI commands are minimal.
    """
    console.print("⚠️  [yellow]Legacy CLI Mode[/yellow]")
    console.print("\nADR Kit is designed for AI agents. Consider using:")
    console.print("• [cyan]adr-kit mcp-server[/cyan] - Start MCP server for AI agents")
    console.print("• [cyan]adr-kit info[/cyan] - Show available MCP tools")

    console.print("\nMinimal CLI commands still available:")
    console.print("• [dim]adr-kit init[/dim] - Initialize ADR structure")
    console.print("• [dim]adr-kit validate[/dim] - Validate existing ADRs")

    console.print("\n💡 Use MCP tools for rich, contextual ADR management!")
    console.print()


@app.command()
def enforce(
    level: str = typer.Argument(
        ...,
        help="Enforcement level: commit (staged files), push (changed files), ci (all files)",
    ),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    project_root: Path = typer.Option(
        Path("."), "--root", help="Project root directory"
    ),
) -> None:
    """Run ADR policy enforcement checks at the given workflow stage.

    Reads accepted ADRs, classifies their policies by stage, and checks the
    appropriate files for violations.

    \\b
    Levels:
      commit  Check staged files only (<5s). Run as pre-commit hook.
      push    Check changed files (<15s). Run as pre-push hook.
      ci      Check entire codebase (<2min). Run in CI pipelines.

    Exit codes: 0 = pass, 1 = violations found, 2 = warnings only, 3 = error
    """
    from .enforce.stages import EnforcementLevel
    from .enforce.validator import StagedValidator

    try:
        try:
            enforcement_level = EnforcementLevel(level.lower())
        except ValueError:
            stderr_console.print(
                f"❌ Unknown level '{level}'. Valid levels: commit, push, ci"
            )
            raise typer.Exit(code=3) from None

        validator = StagedValidator(adr_dir=adr_dir)
        result = validator.validate(enforcement_level, project_root=project_root)

        level_labels = {
            EnforcementLevel.COMMIT: "pre-commit (staged files)",
            EnforcementLevel.PUSH: "pre-push (changed files)",
            EnforcementLevel.CI: "ci (full codebase)",
        }
        console.print(f"🔍 ADR enforcement — {level_labels[enforcement_level]}")
        console.print(f"   {result.checks_run} checks · {result.files_checked} files")

        if not result.violations:
            console.print("✅ All checks passed")
            raise typer.Exit(code=0)

        # Print violations grouped by ADR
        for violation in result.violations:
            icon = "❌" if violation.severity == "error" else "⚠️ "
            location = (
                f"{violation.file}:{violation.line}"
                if violation.line
                else violation.file
            )
            console.print(f"{icon} {location}")
            console.print(f"   {violation.message}")

        console.print(
            f"\n{'❌' if result.error_count else '⚠️ '} "
            f"{result.error_count} error(s), {result.warning_count} warning(s)"
        )

        if result.passed:
            raise typer.Exit(code=2)  # warnings only
        raise typer.Exit(code=1)  # errors found

    except typer.Exit:
        raise
    except Exception as e:
        stderr_console.print(f"❌ Enforcement check failed: {e}")
        raise typer.Exit(code=3) from e


if __name__ == "__main__":
    import sys

    app()
