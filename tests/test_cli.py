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

            result = self.runner.invoke(app, ["init", "--adr-dir", str(adr_dir)])

            assert result.exit_code == 0
            assert adr_dir.exists()
            assert (tmpdir_path / ".project-index").exists()
            assert "Initialized ADR structure" in result.stdout

    def test_new_command(self):
        """Test adr-kit new command."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            result = self.runner.invoke(
                app,
                [
                    "new",
                    "Use React Query for data fetching",
                    "--tags",
                    "frontend,data",
                    "--deciders",
                    "frontend-team",
                    "--adr-dir",
                    str(adr_dir),
                ],
            )

            assert result.exit_code == 0
            assert "Created ADR" in result.stdout
            assert "ADR-0001" in result.stdout

            # Check that file was created
            adr_files = list(adr_dir.glob("ADR-*.md"))
            assert len(adr_files) == 1

            # Check file content
            content = adr_files[0].read_text()
            assert "id: ADR-0001" in content
            assert "title: Use React Query for data fetching" in content
            assert "status: proposed" in content
            assert "tags:" in content
            assert "- frontend" in content
            assert "- data" in content
            assert "deciders:" in content
            assert "- frontend-team" in content

    def test_validate_command(self):
        """Test adr-kit validate command."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create a valid ADR
            valid_adr = """---
id: ADR-0001
title: Use FastAPI
status: accepted
date: 2025-09-03
---

# Decision

Use FastAPI for backend."""

            (adr_dir / "ADR-0001-fastapi.md").write_text(valid_adr)

            result = self.runner.invoke(app, ["validate", "--adr-dir", str(adr_dir)])

            assert result.exit_code == 0
            assert "Validation Summary" in result.stdout
            assert "Total ADRs: 1" in result.stdout
            assert "Valid ADRs: 1" in result.stdout

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

            assert result.exit_code == 1  # Validation errors
            assert "Errors: " in result.stdout
            assert int(result.stdout.split("Errors: ")[1].split("\n")[0]) > 0

    def test_index_command(self):
        """Test adr-kit index command."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create a valid ADR
            valid_adr = """---
id: ADR-0001
title: Use PostgreSQL
status: accepted
date: 2025-09-03
tags: [database]
---

# Decision

Use PostgreSQL as primary database."""

            (adr_dir / "ADR-0001-postgres.md").write_text(valid_adr)

            index_file = adr_dir / "adr-index.json"

            result = self.runner.invoke(
                app, ["index", "--out", str(index_file), "--adr-dir", str(adr_dir)]
            )

            assert result.exit_code == 0
            assert "JSON index generated" in result.stdout
            assert index_file.exists()

            # Check index content
            index_data = json.loads(index_file.read_text())
            assert "metadata" in index_data
            assert "adrs" in index_data
            assert len(index_data["adrs"]) == 1
            assert index_data["adrs"][0]["id"] == "ADR-0001"

    def test_supersede_command(self):
        """Test adr-kit supersede command."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create original ADR
            original_adr = """---
id: ADR-0001
title: Use MySQL
status: accepted
date: 2025-09-03
---

# Decision

Use MySQL as database."""

            original_file = adr_dir / "ADR-0001-mysql.md"
            original_file.write_text(original_adr)

            result = self.runner.invoke(
                app,
                [
                    "supersede",
                    "ADR-0001",
                    "--title",
                    "Use PostgreSQL instead",
                    "--adr-dir",
                    str(adr_dir),
                ],
            )

            assert result.exit_code == 0
            assert "Created superseding ADR" in result.stdout
            assert "Updated superseded ADR" in result.stdout

            # Check that new ADR was created
            adr_files = list(adr_dir.glob("ADR-*.md"))
            assert len(adr_files) == 2

            # Check that original ADR was updated to superseded
            original_content = original_file.read_text()
            assert "status: superseded" in original_content
            assert "superseded_by:" in original_content
            assert "ADR-0002" in original_content

    @patch("subprocess.run")
    def test_render_site_command(self, mock_run):
        """Test adr-kit render-site command."""
        # Mock successful log4brains execution
        mock_run.side_effect = [
            # First call: version check
            type(
                "CompletedProcess",
                (),
                {"returncode": 0, "stdout": "v1.0.0", "stderr": ""},
            )(),
            # Second call: build
            type(
                "CompletedProcess",
                (),
                {"returncode": 0, "stdout": "Built successfully", "stderr": ""},
            )(),
        ]

        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            out_dir = tmpdir_path / ".log4brains" / "out"

            result = self.runner.invoke(
                app,
                ["render-site", "--adr-dir", str(adr_dir), "--out-dir", str(out_dir)],
            )

            assert result.exit_code == 0
            assert "ADR site generated" in result.stdout
            assert mock_run.call_count == 2

    def test_export_lint_eslint(self):
        """Test exporting ESLint configuration."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            adr_dir = tmpdir_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # Create ADR with lint rules
            adr_with_rules = """---
id: ADR-0001
title: Use React Query instead of fetch
status: accepted
date: 2025-09-03
tags: [frontend]
---

# Decision

Don't use fetch API directly. Use React Query for data fetching."""

            (adr_dir / "ADR-0001-react-query.md").write_text(adr_with_rules)

            output_file = tmpdir_path / "eslint.json"

            result = self.runner.invoke(
                app,
                [
                    "export-lint",
                    "eslint",
                    "--out",
                    str(output_file),
                    "--adr-dir",
                    str(adr_dir),
                ],
            )

            assert result.exit_code == 0
            assert "Generated eslint configuration" in result.stdout
            assert output_file.exists()

            # Check that configuration was generated
            config = json.loads(output_file.read_text())
            assert "rules" in config

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
---

# Decision

Valid decision."""

            adr2 = """---
id: ADR-0002
title: Another ADR
status: accepted
date: 2025-09-03
---

# Decision

Another decision."""

            (adr_dir / "ADR-0001-valid.md").write_text(adr1)
            (adr_dir / "ADR-0002-another.md").write_text(adr2)

            result = self.runner.invoke(
                app, ["validate", "--id", "ADR-0001", "--adr-dir", str(adr_dir)]
            )

            assert result.exit_code == 0
            assert "Total ADRs: 1" in result.stdout  # Only validated the specific ADR
