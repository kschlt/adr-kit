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
    help="A toolkit for managing Architectural Decision Records (ADRs) in MADR format",
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
def new(
    title: str = typer.Argument(..., help="Title of the new ADR"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    deciders: Optional[str] = typer.Option(None, "--deciders", help="Comma-separated deciders"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    status: ADRStatus = typer.Option(ADRStatus.PROPOSED, "--status", help="Initial status")
):
    """Create a new ADR."""
    try:
        # Ensure ADR directory exists
        adr_dir.mkdir(parents=True, exist_ok=True)
        
        # Get next ADR ID
        adr_id = get_next_adr_id(adr_dir)
        
        # Parse tags and deciders
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
        decider_list = [decider.strip() for decider in deciders.split(",")] if deciders else None
        
        # Create front matter
        front_matter = ADRFrontMatter(
            id=adr_id,
            title=title,
            status=status,
            date=date.today(),
            tags=tag_list,
            deciders=decider_list
        )
        
        # Create ADR content template
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

What other alternatives have been considered? What are the trade-offs?

- Alternative 1: 
- Alternative 2: """
        
        # Create ADR object
        adr = ADR(front_matter=front_matter, content=content)
        
        # Generate filename and write file
        filename = f"{adr_id}-{title.lower().replace(' ', '-').replace('_', '-')}.md"
        file_path = adr_dir / filename
        
        file_path.write_text(adr.to_markdown(), encoding='utf-8')
        
        console.print(f"✅ Created ADR: {file_path}")
        console.print(f"   📋 ID: {adr_id}")
        console.print(f"   📝 Title: {title}")
        console.print(f"   🏷️  Status: {status.value}")
        
        if tag_list:
            console.print(f"   🏷️  Tags: {', '.join(tag_list)}")
        if decider_list:
            console.print(f"   👥 Deciders: {', '.join(decider_list)}")
        
        raise typer.Exit(code=0)
        
    except Exception as e:
        console.print(f"❌ Failed to create ADR: {e}")
        raise typer.Exit(code=3)


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
def supersede(
    old_id: str = typer.Argument(..., help="ID of the ADR to supersede"),
    title: str = typer.Option(..., "--title", help="Title of the new ADR"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    deciders: Optional[str] = typer.Option(None, "--deciders", help="Comma-separated deciders")
):
    """Create a new ADR that supersedes an existing one."""
    try:
        # Find the old ADR file
        adr_files = find_adr_files(adr_dir)
        old_adr = None
        old_file_path = None
        
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.id == old_id:
                    old_adr = adr
                    old_file_path = file_path
                    break
            except ParseError:
                continue
        
        if not old_adr:
            console.print(f"❌ ADR with ID {old_id} not found")
            raise typer.Exit(code=3)
        
        # Get next ADR ID for new ADR
        new_id = get_next_adr_id(adr_dir)
        
        # Parse tags and deciders
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else old_adr.front_matter.tags
        decider_list = [decider.strip() for decider in deciders.split(",")] if deciders else old_adr.front_matter.deciders
        
        # Create new ADR that supersedes the old one
        new_front_matter = ADRFrontMatter(
            id=new_id,
            title=title,
            status=ADRStatus.PROPOSED,
            date=date.today(),
            tags=tag_list,
            deciders=decider_list,
            supersedes=[old_id]
        )
        
        new_content = f"""# Context

This ADR supersedes {old_id}: {old_adr.front_matter.title}

# Decision

What is the new decision that replaces the previous one?

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
        
        new_adr = ADR(front_matter=new_front_matter, content=new_content)
        
        # Update old ADR to mark it as superseded
        old_adr.front_matter.status = ADRStatus.SUPERSEDED
        old_adr.front_matter.superseded_by = [new_id]
        
        # Write new ADR file
        new_filename = f"{new_id}-{title.lower().replace(' ', '-').replace('_', '-')}.md"
        new_file_path = adr_dir / new_filename
        new_file_path.write_text(new_adr.to_markdown(), encoding='utf-8')
        
        # Update old ADR file
        old_file_path.write_text(old_adr.to_markdown(), encoding='utf-8')
        
        console.print(f"✅ Created superseding ADR: {new_file_path}")
        console.print(f"   📋 New ID: {new_id}")
        console.print(f"   📝 Title: {title}")
        console.print(f"   ⚡ Supersedes: {old_id}")
        console.print(f"✅ Updated superseded ADR: {old_file_path}")
        console.print(f"   📋 Status changed to: superseded")
        
        raise typer.Exit(code=0)
        
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ Failed to create superseding ADR: {e}")
        raise typer.Exit(code=3)


@app.command()
def export_lint(
    framework: str = typer.Argument(..., help="Lint framework (eslint, ruff, import-linter)"),
    out: Optional[Path] = typer.Option(None, "--out", help="Output file path"),
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory")
):
    """Export lint configurations from ADRs."""
    try:
        # Import the enforcement modules
        if framework == "eslint":
            from .enforce.eslint import generate_eslint_config
            config = generate_eslint_config(adr_dir)
            default_out = ".eslintrc.adrs.json"
        elif framework == "ruff":
            from .enforce.ruff import generate_ruff_config
            config = generate_ruff_config(adr_dir)
            default_out = "ruff.adrs.toml"
        elif framework == "import-linter":
            from .enforce.ruff import generate_import_linter_config
            config = generate_import_linter_config(adr_dir)
            default_out = ".import-linter.adrs.ini"
        else:
            console.print(f"❌ Unsupported framework: {framework}")
            console.print("Supported frameworks: eslint, ruff, import-linter")
            raise typer.Exit(code=2)
        
        # Use provided output path or default
        output_path = out or Path(default_out)
        
        # Write config file
        output_path.write_text(config, encoding='utf-8')
        
        console.print(f"✅ Generated {framework} configuration: {output_path}")
        
        raise typer.Exit(code=0)
        
    except typer.Exit:
        raise
    except ImportError as e:
        console.print(f"❌ Could not import enforcement module: {e}")
        raise typer.Exit(code=2)
    except Exception as e:
        console.print(f"❌ Failed to export lint configuration: {e}")
        raise typer.Exit(code=3)


@app.command()
def render_site(
    adr_dir: Path = typer.Option(Path("docs/adr"), "--adr-dir", help="ADR directory"),
    out_dir: Path = typer.Option(Path(".log4brains/out"), "--out-dir", help="Output directory for site")
):
    """Render static site via Log4brains."""
    try:
        import subprocess
        
        # Check if log4brains is available
        try:
            subprocess.run(["log4brains", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("❌ log4brains not found. Please install it first:")
            console.print("   npm install -g log4brains")
            raise typer.Exit(code=3)
        
        # Run log4brains build
        console.print("🏗️  Building ADR site with Log4brains...")
        
        result = subprocess.run([
            "log4brains", "build",
            "--adrDir", str(adr_dir),
            "--outDir", str(out_dir)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            console.print(f"❌ Log4brains build failed:")
            console.print(result.stderr)
            raise typer.Exit(code=3)
        
        console.print(f"✅ ADR site generated: {out_dir}")
        console.print("   🌐 Open index.html in a web browser to view")
        
        raise typer.Exit(code=0)
        
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ Site rendering failed: {e}")
        raise typer.Exit(code=3)


if __name__ == "__main__":
    import sys
    app()