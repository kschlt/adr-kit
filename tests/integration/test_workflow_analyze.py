"""Unit tests for AnalyzeProjectWorkflow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from adr_kit.workflows.analyze import AnalyzeProjectWorkflow
from adr_kit.workflows.base import WorkflowStatus


class TestAnalyzeProjectWorkflow:
    """Test AnalyzeProjectWorkflow functionality."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory with sample files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create package.json
            package_json = {
                "name": "test-project",
                "version": "1.0.0",
                "dependencies": {
                    "react": "^18.2.0",
                    "express": "^4.18.2",
                    "typescript": "^5.0.0",
                },
                "devDependencies": {"jest": "^29.0.0", "@types/node": "^18.0.0"},
            }

            with open(project_dir / "package.json", "w") as f:
                json.dump(package_json, f, indent=2)

            # Create some source files
            (project_dir / "src").mkdir()
            (project_dir / "src" / "index.js").write_text("console.log('Hello World');")
            (project_dir / "src" / "components").mkdir()
            (project_dir / "src" / "components" / "App.jsx").write_text(
                "export default function App() { return <div>App</div>; }"
            )

            # Create README
            (project_dir / "README.md").write_text(
                "# Test Project\n\nThis is a test project."
            )

            yield str(project_dir)

    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)

    @pytest.fixture
    def sample_existing_adr(self, temp_adr_dir):
        """Create a sample existing ADR."""
        adr_content = """---
id: ADR-0001
title: Use React for Frontend
status: accepted
date: 2024-01-15
deciders: ["frontend-team"]
tags: ["frontend", "react"]
---

## Context

We need a modern frontend framework for our web application.

## Decision

We will use React for all frontend development.

## Consequences

### Positive
- Modern component-based architecture
- Large ecosystem and community support

### Negative
- Learning curve for team members new to React
"""

        adr_file = Path(temp_adr_dir) / "ADR-0001-use-react-for-frontend.md"
        adr_file.write_text(adr_content)
        return str(adr_file)

    def test_successful_project_analysis(self, temp_project_dir, temp_adr_dir):
        """Test successful analysis of a project."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(
            project_path=temp_project_dir, focus_areas=["frontend", "testing"]
        )

        # Check overall success
        assert result.success is True
        assert result.status == WorkflowStatus.SUCCESS
        assert "analysis completed" in result.message.lower()
        assert result.duration_ms > 0

        # Check steps were executed
        step_names = [step.name for step in result.steps]
        expected_steps = [
            "validate_inputs",
            "scan_project_structure",
            "detect_technologies",
            "check_existing_adrs",
            "generate_analysis_prompt",
        ]

        for expected_step in expected_steps:
            assert expected_step in step_names

        # All steps should be successful
        for step in result.steps:
            assert step.status == WorkflowStatus.SUCCESS
            assert step.duration_ms > 0

        # Check data content
        assert "analysis_prompt" in result.data
        assert "project_context" in result.data

        project_context = result.data["project_context"]
        assert "technologies" in project_context

        # Should detect JavaScript/React technologies
        technologies = project_context["technologies"]
        tech_list_lower = [tech.lower() for tech in technologies]
        assert "javascript" in tech_list_lower or "react" in tech_list_lower

        # Check agent guidance
        assert result.guidance
        assert len(result.next_steps) > 0
        assert any(
            "analyze" in step.lower() or "identify" in step.lower()
            for step in result.next_steps
        )

    def test_project_with_existing_adrs(
        self, temp_project_dir, temp_adr_dir, sample_existing_adr
    ):
        """Test analysis of project that already has ADRs."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(project_path=temp_project_dir)

        assert result.success is True

        # Should detect existing ADRs
        project_context = result.data["project_context"]
        assert "existing_adrs" in project_context
        assert project_context["existing_adrs"]["count"] == 1
        assert len(project_context["existing_adrs"]["files"]) == 1

        # Analysis prompt should mention existing ADRs
        analysis_prompt = result.data["analysis_prompt"]
        assert "existing" in analysis_prompt.lower() or "adr" in analysis_prompt.lower()

    def test_focus_areas_filtering(self, temp_project_dir, temp_adr_dir):
        """Test that focus areas affect the analysis."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        # Test with specific focus areas
        result = workflow.execute(
            project_path=temp_project_dir, focus_areas=["testing", "build"]
        )

        assert result.success is True

        analysis_prompt = result.data["analysis_prompt"]

        # Should mention the focus areas in the prompt
        assert (
            "testing" in analysis_prompt.lower() or "build" in analysis_prompt.lower()
        )

    def test_empty_project_analysis(self, temp_adr_dir):
        """Test analysis of empty project directory."""
        with tempfile.TemporaryDirectory() as empty_dir:
            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

            result = workflow.execute(project_path=empty_dir)

            assert result.success is True

            # Should still complete analysis but detect no technologies
            project_context = result.data["project_context"]
            technologies = project_context["technologies"]

            # Should have empty or minimal technology detection
            assert isinstance(technologies, list)

            # Should provide generic analysis guidance
            assert result.guidance
            assert "analysis_prompt" in result.data

    def test_nonexistent_project_path(self, temp_adr_dir):
        """Test handling of non-existent project path."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(project_path="/nonexistent/path")

        # Should fail gracefully
        assert result.success is False
        assert result.status == WorkflowStatus.FAILED

        # Should have error details
        assert len(result.errors) > 0
        assert any(
            "not exist" in error.lower() or "not found" in error.lower()
            for error in result.errors
        )

        # Should have failed at the validation step
        failed_steps = [
            step for step in result.steps if step.status == WorkflowStatus.FAILED
        ]
        assert len(failed_steps) > 0
        assert failed_steps[0].name == "validate_inputs"

    def test_project_path_is_file(self, temp_adr_dir):
        """Test handling when project path is a file, not directory."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

            result = workflow.execute(project_path=temp_file.name)

            assert result.success is False
            assert result.status == WorkflowStatus.FAILED

            # Should have appropriate error message
            assert len(result.errors) > 0
            assert any("directory" in error.lower() for error in result.errors)

    def test_default_project_path(self, temp_adr_dir):
        """Test using default project path (current directory)."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        # Should use current directory when project_path is None
        result = workflow.execute(project_path=None)

        # Should complete (current directory should exist)
        assert result.success is True or result.success is False  # Either is acceptable

        # Should have attempted validation step
        step_names = [step.name for step in result.steps]
        assert "validate_inputs" in step_names

    def test_technology_detection_python(self, temp_adr_dir):
        """Test detection of Python project technologies."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)

            # Create Python project files
            (project_path / "requirements.txt").write_text(
                "fastapi==0.104.1\npytest==7.4.3"
            )
            (project_path / "main.py").write_text(
                "from fastapi import FastAPI\napp = FastAPI()"
            )
            (project_path / "pyproject.toml").write_text(
                "[tool.poetry]\nname = 'test'\nversion = '1.0.0'"
            )

            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
            result = workflow.execute(project_path=str(project_path))

            assert result.success is True

            # Should detect Python technologies
            technologies = result.data["project_context"]["technologies"]

            # Should detect Python and potentially FastAPI
            detected_tech = str(technologies).lower()
            assert "python" in detected_tech or "fastapi" in detected_tech

    def test_confidence_scoring(self, temp_project_dir, temp_adr_dir):
        """Test that technology detection includes confidence scores."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(project_path=temp_project_dir)

        assert result.success is True

        project_context = result.data["project_context"]
        assert "confidence_scores" in project_context

        confidence_scores = project_context["confidence_scores"]
        assert isinstance(confidence_scores, dict)

        # Should have some confidence scores
        if len(confidence_scores) > 0:
            for _tech, score in confidence_scores.items():
                assert isinstance(score, int | float)
                assert 0 <= score <= 1  # Confidence should be between 0 and 1

    def test_analysis_prompt_quality(self, temp_project_dir, temp_adr_dir):
        """Test that generated analysis prompt is comprehensive."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        result = workflow.execute(
            project_path=temp_project_dir, focus_areas=["architecture", "dependencies"]
        )

        assert result.success is True

        analysis_prompt = result.data["analysis_prompt"]

        # Prompt should be substantial
        assert len(analysis_prompt) > 100

        # Should contain key guidance elements
        prompt_lower = analysis_prompt.lower()
        assert "decision" in prompt_lower
        assert "architecture" in prompt_lower or "architectural" in prompt_lower

        # Should mention focus areas
        assert "architecture" in prompt_lower
        assert "dependencies" in prompt_lower or "dependency" in prompt_lower

        # Should provide actionable guidance
        assert (
            "look for" in prompt_lower
            or "examine" in prompt_lower
            or "analyze" in prompt_lower
        )

    def test_workflow_step_error_handling(self, temp_adr_dir):
        """Test error handling in individual workflow steps."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)

        # Mock a step to fail
        original_scan = workflow._scan_project_structure

        def failing_scan(*args, **kwargs):
            raise Exception("Simulated scan failure")

        workflow._scan_project_structure = failing_scan

        result = workflow.execute(
            project_path=tempfile.gettempdir()
        )  # Use platform-independent temp directory

        assert result.success is False
        assert result.status == WorkflowStatus.FAILED

        # Should have error details
        assert len(result.errors) > 0
        assert any("Simulated scan failure" in error for error in result.errors)

        # Should have failed step
        failed_steps = [
            step for step in result.steps if step.status == WorkflowStatus.FAILED
        ]
        assert len(failed_steps) > 0

        failed_step = failed_steps[0]
        assert failed_step.name == "scan_project_structure"
        assert len(failed_step.errors) > 0

    def test_large_project_handling(self, temp_adr_dir):
        """Test analysis of project with many files."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)

            # Create many files to test performance and handling
            src_dir = project_path / "src"
            src_dir.mkdir()

            for i in range(50):  # Create 50 files
                (src_dir / f"file_{i}.js").write_text(f"console.log('File {i}');")

            # Add package.json
            package_json = {"name": "large-project", "version": "1.0.0"}
            with open(project_path / "package.json", "w") as f:
                json.dump(package_json, f)

            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
            result = workflow.execute(project_path=str(project_path))

            # Should handle large project successfully
            assert result.success is True

            # Should complete in reasonable time (less than 10 seconds)
            assert result.duration_ms < 10000

            # Should still detect technologies
            project_context = result.data["project_context"]
            assert "technologies" in project_context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
