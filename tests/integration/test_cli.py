"""Tests for CLI functionality."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from typer.testing import CliRunner

from adr_kit.cli import app
from adr_kit.core.model import ADRStatus


class TestCLI:
    """Test CLI commands."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_init_command(self):
        """Test adr-kit init command."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"

            result = self.runner.invoke(app, ["init", "--adr-dir", str(adr_dir)], input="3\n")

            assert result.exit_code == 0
            assert adr_dir.exists()
            # CLI creates .project-index in current directory
            assert Path(".project-index").exists()
            assert "Initialized ADR structure" in result.output

    def test_legacy_command(self):
        """Test adr-kit legacy command."""
        result = self.runner.invoke(app, ["legacy"])
        assert result.exit_code == 0
        assert "Legacy CLI Mode" in result.output
        assert "MCP server" in result.output

    def test_validate_command(self):
        """Test adr-kit validate command runs properly."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create an ADR - doesn't need to be perfectly valid for this CLI test
            test_adr = """---
id: "ADR-0001"
title: "Use FastAPI"
status: "proposed"
date: "2025-09-03"
deciders: ["team-lead"]
tags: ["backend", "framework"]
---

# Context

We need a web framework for our backend API.

# Decision

Use FastAPI for backend development."""

            (adr_dir / "ADR-0001-fastapi.md").write_text(test_adr)

            result = self.runner.invoke(app, ["validate", "--adr-dir", str(adr_dir)])

            # Test that CLI runs and produces validation output (not validating the ADR content itself)
            assert "Validation Summary" in result.output
            assert "Total ADRs: 1" in result.output

    def test_validate_command_with_errors(self):
        """Test validation command with invalid ADR."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create an invalid ADR
            invalid_adr = """---
id: INVALID-ID
title: Test
status: superseded
date: 2025-09-03
---

# Decision

Test decision."""

            (adr_dir / "ADR-0001-invalid.md").write_text(invalid_adr)

            result = self.runner.invoke(app, ["validate", "--adr-dir", str(adr_dir)])

            # CLI exits with code 3 for validation failures, not 1
            assert result.exit_code == 3  # Validation errors
            assert "Validation failed" in result.output

    def test_index_command(self):
        """Test adr-kit index command."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create a valid ADR
            valid_adr = """---
id: "ADR-0001"
title: "Use PostgreSQL"
status: "proposed"  
date: "2025-09-03"
deciders: ["team-lead"]
tags: ["database"]
---

# Context

We need a database for our application.

# Decision

Use PostgreSQL as primary database."""

            (adr_dir / "ADR-0001-postgres.md").write_text(valid_adr)

            index_file = adr_dir / "adr-index.json"

            result = self.runner.invoke(
                app, ["index", "--out", str(index_file), "--adr-dir", str(adr_dir)]
            )

            if result.exit_code != 0:
                print(f"Exit code: {result.exit_code}")
                print(f"Output: {result.output}")
                if result.exception:
                    print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            assert "JSON index generated" in result.stdout
            assert index_file.exists()

            # Check index content
            index_data = json.loads(index_file.read_text())
            assert "metadata" in index_data
            assert "adrs" in index_data
            assert len(index_data["adrs"]) == 1
            assert index_data["adrs"][0]["id"] == "ADR-0001"

    # Supersede command removed - use MCP server instead

    # Render-site command removed - use MCP server instead

    # Export-lint command removed - use MCP server instead

    def test_validate_specific_adr(self):
        """Test validating a specific ADR by ID."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create multiple ADRs
            adr1 = """---
id: ADR-0001
title: Valid ADR
status: accepted
date: 2025-09-03
policy:
  imports:
    prefer: ["valid-library"]
---

# Decision

Valid decision with extractable policy implications."""

            adr2 = """---
id: ADR-0002
title: Another ADR
status: accepted
date: 2025-09-03
policy:
  imports:
    prefer: ["another-library"]
---

# Decision

Another decision with clear policy directives."""

            (adr_dir / "ADR-0001-valid.md").write_text(adr1)
            (adr_dir / "ADR-0002-another.md").write_text(adr2)

            result = self.runner.invoke(
                app, ["validate", "--id", "ADR-0001", "--adr-dir", str(adr_dir)]
            )

            assert result.exit_code == 0
            assert "Total ADRs: 1" in result.stdout  # Only validated the specific ADR
