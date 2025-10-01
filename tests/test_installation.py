"""Tests for installation and package availability.

These tests verify that ADR Kit can be installed correctly using uv
and that the CLI is properly accessible.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _get_cli_command():
    """Get the CLI command to use (adr-kit or python -m adr_kit.cli)."""
    # First try to find adr-kit in PATH
    if shutil.which("adr-kit"):
        return ["adr-kit"]
    # Fallback to running via Python module (for editable installs in testing)
    return [sys.executable, "-m", "adr_kit.cli"]


class TestInstallation:
    """Test package installation and CLI availability."""

    def test_cli_command_available(self):
        """Test that adr-kit command is available."""
        cmd = _get_cli_command()
        result = subprocess.run(
            cmd + ["--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"CLI command failed: {result.stderr}"
        assert "adr-kit" in result.stdout.lower()

    def test_cli_help_output(self):
        """Test that --help produces expected output."""
        cmd = _get_cli_command()
        result = subprocess.run(
            cmd + ["--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "Architectural Decision Records" in result.stdout
        assert "init" in result.stdout
        assert "validate" in result.stdout

    def test_cli_version_info(self):
        """Test that we can get version information."""
        # Import version from package
        from adr_kit import __version__

        assert __version__ is not None
        assert len(__version__) > 0

    def test_mcp_server_command_exists(self):
        """Test that mcp-server command is available."""
        cmd = _get_cli_command()
        result = subprocess.run(
            cmd + ["mcp-server", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "mcp" in result.stdout.lower()

    def test_package_metadata(self):
        """Test that package metadata is correct."""
        import importlib.metadata

        try:
            metadata = importlib.metadata.metadata("adr-kit")
            assert metadata["Name"] == "adr-kit"
            assert metadata["Version"]  # Just check it exists
            assert "Architectural Decision Records" in metadata["Summary"]
        except importlib.metadata.PackageNotFoundError:
            # In editable install during development, metadata might not be available
            # Just verify the package can be imported
            import adr_kit

            assert adr_kit.__version__ is not None

    def test_entry_point_registered(self):
        """Test that CLI entry point is properly registered."""
        import importlib.metadata
        from typing import Any

        entry_points = importlib.metadata.entry_points()

        # Find our console script
        console_scripts: Any = []
        if hasattr(entry_points, "select"):
            # Python 3.10+
            console_scripts = entry_points.select(group="console_scripts")
        else:
            # Python 3.9
            console_scripts = entry_points.get("console_scripts", [])

        adr_kit_entry = None
        for ep in console_scripts:
            if ep.name == "adr-kit":
                adr_kit_entry = ep
                break

        assert adr_kit_entry is not None, "adr-kit entry point not found"
        assert "adr_kit.cli:app" in adr_kit_entry.value

    def test_import_main_module(self):
        """Test that main module can be imported."""
        import adr_kit

        assert hasattr(adr_kit, "__version__")

    def test_import_cli_module(self):
        """Test that CLI module can be imported."""
        from adr_kit.cli import app

        assert app is not None

    def test_import_mcp_server(self):
        """Test that MCP server module can be imported."""
        from adr_kit.mcp.server import mcp

        assert mcp is not None

    def test_all_cli_commands_exist(self):
        """Test that all documented CLI commands are available."""
        cmd = _get_cli_command()
        result = subprocess.run(
            cmd + ["--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Check for main commands
        expected_commands = ["init", "validate", "index", "mcp-server"]
        for command in expected_commands:
            assert (
                command in result.stdout
            ), f"Command '{command}' not found in CLI help output"


class TestDevelopmentInstallation:
    """Test development/editable installation."""

    def test_editable_install_detected(self):
        """Test if we can detect an editable install."""
        import importlib.metadata

        # Get distribution location
        try:
            dist = importlib.metadata.distribution("adr-kit")
            # Editable installs typically have .egg-link or direct-url.json
            # This is informational, not a hard requirement
            assert dist is not None
        except importlib.metadata.PackageNotFoundError:
            pytest.fail("adr-kit package not installed")

    def test_source_code_available(self):
        """Test that source code is accessible (for development)."""
        import adr_kit

        module_file = Path(adr_kit.__file__)
        assert module_file.exists()

        # Check that it's in a reasonable location
        assert "adr_kit" in str(module_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
