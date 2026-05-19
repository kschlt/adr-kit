"""Integration tests for setup-claude config output and schema packaging fix."""

import json
from pathlib import Path

from typer.testing import CliRunner

from adr_kit.cli import app

runner = CliRunner()


def test_setup_claude_creates_mcp_json(tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["setup-claude"])
        assert Path(".mcp.json").exists(), ".mcp.json must be created by setup-claude"
        assert not Path(
            ".claude-mcp-config.json"
        ).exists(), ".claude-mcp-config.json must not be created (wrong filename)"


def test_setup_claude_uses_mcp_servers_key(tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["setup-claude"])
        config = json.loads(Path(".mcp.json").read_text())
        assert "mcpServers" in config, "top-level key must be 'mcpServers'"
        assert "servers" not in config, "'servers' key must not be present"


def test_setup_claude_no_stale_tools_array(tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(app, ["setup-claude"])
        config = json.loads(Path(".mcp.json").read_text())
        server = config["mcpServers"]["adr-kit"]
        assert "tools" not in server, "stale tools array must be removed from config"
        assert "description" not in server, "description field must be removed"


def test_schema_file_bundled_in_package():
    from adr_kit.core.validate import ADRValidator

    validator = ADRValidator.__new__(ADRValidator)
    schema_path = validator._get_default_schema_path()
    assert schema_path.exists(), (
        f"Schema must exist at {schema_path} — "
        "schemas/adr.schema.json must be bundled inside adr_kit/schemas/"
    )
