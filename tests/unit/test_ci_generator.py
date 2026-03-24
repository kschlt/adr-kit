"""Unit tests for CI workflow generator."""

import tempfile
from pathlib import Path

import pytest

from adr_kit.enforcement.generation.ci import _MANAGED_HEADER, CIWorkflowGenerator


class TestCIWorkflowGenerator:
    """Test CI workflow YAML generation."""

    def test_generates_valid_yaml_content(self):
        gen = CIWorkflowGenerator()
        content = gen.generate()
        assert content.startswith(_MANAGED_HEADER)
        assert "name: ADR Enforcement" in content
        assert "adr-kit enforce ci --format json" in content
        assert "pull_request:" in content

    def test_contains_required_steps(self):
        gen = CIWorkflowGenerator()
        content = gen.generate()
        assert "actions/checkout@v4" in content
        assert "actions/setup-python@v5" in content
        assert "pip install adr-kit" in content
        assert "adr-report.json" in content

    def test_contains_pr_comment_step(self):
        gen = CIWorkflowGenerator()
        content = gen.generate()
        assert "Post PR comment" in content
        assert "ADR Enforcement Report" in content
        assert "actions/github-script@v7" in content

    def test_writes_to_file(self):
        gen = CIWorkflowGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / ".github" / "workflows" / "adr-validation.yml"
            content = gen.generate(output_path=output)
            assert output.exists()
            assert output.read_text() == content

    def test_overwrites_managed_file(self):
        gen = CIWorkflowGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "workflow.yml"
            # Write initial managed file
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(f"{_MANAGED_HEADER}\nold content")
            # Should overwrite without error
            gen.generate(output_path=output)
            assert "ADR Enforcement" in output.read_text()

    def test_refuses_to_overwrite_unmanaged_file(self):
        gen = CIWorkflowGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "workflow.yml"
            output.write_text("# My custom workflow\nname: Custom")
            with pytest.raises(FileExistsError):
                gen.generate(output_path=output)

    def test_creates_parent_directories(self):
        gen = CIWorkflowGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "deep" / "nested" / "dir" / "workflow.yml"
            gen.generate(output_path=output)
            assert output.exists()

    def test_fail_on_violations_step(self):
        gen = CIWorkflowGenerator()
        content = gen.generate()
        assert "Fail on violations" in content
        assert "exit 1" in content
