"""Integration tests for setup-claude config output and schema packaging fix.

Uses monkeypatch.chdir rather than CliRunner.isolated_filesystem: typer's CliRunner
no longer subclasses click's, so it has no isolated_filesystem. monkeypatch.chdir is
independent of both libraries' testing APIs.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from adr_kit.cli import app

runner = CliRunner()


def test_setup_claude_creates_mcp_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["setup-claude"])
    assert Path(".mcp.json").exists(), ".mcp.json must be created by setup-claude"
    assert not Path(
        ".claude-mcp-config.json"
    ).exists(), ".claude-mcp-config.json must not be created (wrong filename)"


def test_setup_claude_uses_mcp_servers_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["setup-claude"])
    config = json.loads(Path(".mcp.json").read_text())
    assert "mcpServers" in config, "top-level key must be 'mcpServers'"
    assert "servers" not in config, "'servers' key must not be present"


def test_setup_claude_no_stale_tools_array(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["setup-claude"])
    config = json.loads(Path(".mcp.json").read_text())
    server = config["mcpServers"]["adr-kit"]
    assert "tools" not in server, "stale tools array must be removed from config"
    assert "description" not in server, "description field must be removed"


def test_setup_claude_preserves_other_mcp_servers(tmp_path, monkeypatch):
    """A real .mcp.json usually holds other servers — setup-claude must not eat them."""
    monkeypatch.chdir(tmp_path)
    Path(".mcp.json").write_text(
        json.dumps({"mcpServers": {"other-server": {"command": "other"}}})
    )
    runner.invoke(app, ["setup-claude"])
    config = json.loads(Path(".mcp.json").read_text())
    assert (
        "other-server" in config["mcpServers"]
    ), "setup-claude must merge into .mcp.json, not clobber unrelated servers"
    assert "adr-kit" in config["mcpServers"], "adr-kit entry must still be added"


def test_setup_claude_preserves_unrelated_top_level_keys(tmp_path, monkeypatch):
    """Keys outside mcpServers must survive the merge too."""
    monkeypatch.chdir(tmp_path)
    Path(".mcp.json").write_text(json.dumps({"someOtherKey": {"keep": True}}))
    runner.invoke(app, ["setup-claude"])
    config = json.loads(Path(".mcp.json").read_text())
    assert "someOtherKey" in config, "unrelated top-level keys must be preserved"
    assert "adr-kit" in config["mcpServers"]


def test_schema_file_bundled_in_package():
    from adr_kit.core.validate import ADRValidator

    validator = ADRValidator.__new__(ADRValidator)
    schema_path = validator._get_default_schema_path()
    assert schema_path.exists(), (
        f"Schema must exist at {schema_path} — "
        "schemas/adr.schema.json must be bundled inside adr_kit/schemas/"
    )
