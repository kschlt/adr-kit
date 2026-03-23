"""Unit tests for validation script generator.

Tests generate scripts into a temp dir, then execute them via subprocess
to verify they produce valid EnforcementReport JSON.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from adr_kit.enforce.script_generator import ScriptGenerator

# Reuse the _make_adr helper from test_staged_enforcement
from tests.unit.test_staged_enforcement import _make_adr

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_script(script_path: Path, project_root: Path, quick: bool = False) -> dict:
    """Execute a generated script and parse its JSON output."""
    cmd = [sys.executable, str(script_path), "--root", str(project_root)]
    if quick:
        cmd.append("--quick")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.stdout.strip(), f"Script produced no output.\nstderr: {result.stderr}"
    return json.loads(result.stdout)


def _assert_valid_report(report: dict) -> None:
    """Assert the report matches EnforcementReport schema basics."""
    assert report["schema_version"] == "1.0"
    assert "passed" in report
    assert "summary" in report
    assert "violations" in report
    assert "errors" in report
    summary = report["summary"]
    assert "files_checked" in summary
    assert "checks_run" in summary
    assert "error_count" in summary
    assert "warning_count" in summary


# ---------------------------------------------------------------------------
# ScriptGenerator unit tests
# ---------------------------------------------------------------------------


class TestScriptGeneratorBasics:
    """Test ScriptGenerator methods without executing scripts."""

    def test_no_policies_returns_none(self):
        gen = ScriptGenerator()
        adr = _make_adr()  # no policies
        with tempfile.TemporaryDirectory() as tmp:
            result = gen.generate_for_adr(adr, Path(tmp))
            assert result is None

    def test_config_only_returns_none(self):
        """Config checks are skipped (not yet implemented)."""
        gen = ScriptGenerator()
        adr = _make_adr(config_enforcement={"typescript": {"strict": True}})
        with tempfile.TemporaryDirectory() as tmp:
            result = gen.generate_for_adr(adr, Path(tmp))
            assert result is None

    def test_generates_executable_file(self):
        gen = ScriptGenerator()
        adr = _make_adr(imports_disallow=["lodash"])
        with tempfile.TemporaryDirectory() as tmp:
            path = gen.generate_for_adr(adr, Path(tmp))
            assert path is not None
            assert path.exists()
            assert path.name == "validate_adr_0001.py"
            # Check executable bit
            import os

            assert os.access(path, os.X_OK)

    def test_generates_output_dir(self):
        gen = ScriptGenerator()
        adr = _make_adr(imports_disallow=["lodash"])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scripts" / "adr"
            path = gen.generate_for_adr(adr, out)
            assert path is not None
            assert out.exists()


# ---------------------------------------------------------------------------
# Import check scripts (executed via subprocess)
# ---------------------------------------------------------------------------


class TestImportCheckScripts:
    """Test generated import-check scripts by running them."""

    def test_clean_project_passes(self):
        gen = ScriptGenerator()
        adr = _make_adr(imports_disallow=["lodash"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            # Create a clean JS file
            (project_dir / "app.js").write_text("const x = 1;\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is True
            assert report["summary"]["error_count"] == 0

    def test_detects_js_import(self):
        gen = ScriptGenerator()
        adr = _make_adr(adr_id="ADR-0010", imports_disallow=["lodash"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "app.js").write_text("import lodash from 'lodash';\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is False
            assert report["summary"]["error_count"] >= 1
            assert report["violations"][0]["adr_id"] == "ADR-0010"

    def test_detects_python_import(self):
        gen = ScriptGenerator()
        adr = _make_adr(python_disallow=["requests"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "main.py").write_text("import requests\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is False
            assert report["summary"]["error_count"] >= 1

    def test_python_from_import_detected(self):
        gen = ScriptGenerator()
        adr = _make_adr(python_disallow=["requests"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "main.py").write_text("from requests import get\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is False


# ---------------------------------------------------------------------------
# Pattern check scripts
# ---------------------------------------------------------------------------


class TestPatternCheckScripts:
    """Test generated pattern-check scripts."""

    def test_pattern_clean_passes(self):
        gen = ScriptGenerator()
        adr = _make_adr(
            patterns={
                "no_console": {
                    "description": "No console.log",
                    "rule": r"console\.log\(",
                    "language": "js",
                }
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "app.js").write_text("const x = 1;\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is True

    def test_pattern_violation_detected(self):
        gen = ScriptGenerator()
        adr = _make_adr(
            patterns={
                "no_console": {
                    "description": "No console.log",
                    "rule": r"console\.log\(",
                    "language": "js",
                }
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "app.js").write_text('console.log("hello");\n')

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is False
            assert report["summary"]["error_count"] >= 1

    def test_pattern_warning_severity(self):
        gen = ScriptGenerator()
        adr = _make_adr(
            patterns={
                "no_todo": {
                    "description": "Avoid TODO comments",
                    "rule": r"# TODO",
                    "severity": "warning",
                }
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "main.py").write_text("# TODO: fix this\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            # Warnings don't cause failure
            assert report["passed"] is True
            assert report["summary"]["warning_count"] >= 1


# ---------------------------------------------------------------------------
# Architecture check scripts
# ---------------------------------------------------------------------------


class TestArchitectureCheckScripts:
    """Test generated architecture-check scripts."""

    def test_arch_clean_passes(self):
        gen = ScriptGenerator()
        adr = _make_adr(
            architecture_boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "ui/**/*.py",
                    "action": "block",
                    "message": "UI must not import database directly",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            ui_dir = project_dir / "ui"
            ui_dir.mkdir(parents=True)
            (ui_dir / "views.py").write_text("from api import get_data\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is True

    def test_arch_violation_detected(self):
        gen = ScriptGenerator()
        adr = _make_adr(
            architecture_boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "ui/**/*.py",
                    "action": "block",
                    "message": "UI must not import database directly",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            ui_dir = project_dir / "ui"
            ui_dir.mkdir(parents=True)
            (ui_dir / "views.py").write_text("from database import models\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is False
            assert report["summary"]["error_count"] >= 1


# ---------------------------------------------------------------------------
# Required structure check scripts
# ---------------------------------------------------------------------------


class TestStructureCheckScripts:
    """Test generated required-structure-check scripts."""

    def test_structure_exists_passes(self):
        gen = ScriptGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            # Create required path
            (project_dir / "src").mkdir()
            (project_dir / "src" / "main.py").write_text("")

            adr = _make_adr(
                required_structure=[
                    {
                        "path": str(project_dir / "src"),
                        "description": "Source dir required",
                    }
                ]
            )
            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is True

    def test_structure_missing_fails(self):
        gen = ScriptGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()

            adr = _make_adr(
                required_structure=[
                    {
                        "path": str(project_dir / "nonexistent"),
                        "description": "Must exist",
                    }
                ]
            )
            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is False
            assert report["summary"]["error_count"] >= 1


# ---------------------------------------------------------------------------
# generate_all and runner
# ---------------------------------------------------------------------------


class TestGenerateAll:
    """Test generate_all and the runner script."""

    def test_generate_all_creates_runner(self):
        """generate_all creates individual scripts plus validate_all.py."""
        gen = ScriptGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adr_dir = tmp_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            scripts_dir = tmp_path / "scripts"

            # Write a minimal accepted ADR with a policy
            adr_content = """\
---
id: ADR-0001
title: Use FastAPI
status: accepted
date: 2026-01-01
policy:
  python:
    disallow_imports:
      - flask
---

# Use FastAPI

## Context
We need a web framework.

## Decision
Use FastAPI.

## Consequences
- Must not import flask.
"""
            (adr_dir / "ADR-0001.md").write_text(adr_content)

            gen_with_dir = ScriptGenerator(adr_dir=adr_dir)
            paths = gen_with_dir.generate_all(scripts_dir)

            assert len(paths) >= 2  # at least one script + runner
            runner = scripts_dir / "validate_all.py"
            assert runner.exists()
            assert any(p.name == "validate_all.py" for p in paths)
            assert any(p.name.startswith("validate_adr_") for p in paths)

    def test_runner_executes_and_aggregates(self):
        """validate_all.py runs all scripts and merges results."""
        gen = ScriptGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            adr_dir = tmp_path / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()

            # Write a clean project file
            (project_dir / "main.py").write_text("print('hello')\n")

            # Write accepted ADR
            adr_content = """\
---
id: ADR-0001
title: No Flask
status: accepted
date: 2026-01-01
policy:
  python:
    disallow_imports:
      - flask
---

# No Flask

## Context
We standardized on FastAPI.

## Decision
Ban flask.

## Consequences
- Flask imports are errors.
"""
            (adr_dir / "ADR-0001.md").write_text(adr_content)

            gen_with_dir = ScriptGenerator(adr_dir=adr_dir)
            gen_with_dir.generate_all(scripts_dir)

            runner = scripts_dir / "validate_all.py"
            report = _run_script(runner, project_dir)
            _assert_valid_report(report)
            assert report["passed"] is True


# ---------------------------------------------------------------------------
# Multiple check types in one ADR
# ---------------------------------------------------------------------------


class TestMultipleCheckTypes:
    """Test ADRs with multiple policy types generate combined scripts."""

    def test_combined_import_and_pattern(self):
        gen = ScriptGenerator()
        adr = _make_adr(
            imports_disallow=["lodash"],
            patterns={
                "no_eval": {
                    "description": "No eval()",
                    "rule": r"\beval\(",
                }
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            (project_dir / "app.js").write_text("eval('dangerous');\n")

            path = gen.generate_for_adr(adr, scripts_dir)
            report = _run_script(path, project_dir)
            _assert_valid_report(report)
            # eval violation found
            assert report["passed"] is False
            assert report["summary"]["checks_run"] >= 2
