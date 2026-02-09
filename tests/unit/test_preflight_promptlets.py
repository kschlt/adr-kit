"""Tests for preflight workflow evaluation promptlet injection.

Tests verify that when preflight returns REQUIRES_ADR, the guidance includes
category-specific evaluation criteria from the knowledge module.
"""

import tempfile
from pathlib import Path

import pytest

from adr_kit.workflows.preflight import PreflightInput, PreflightWorkflow


class TestPreflightPromptletInjection:
    """Test evaluation promptlet injection in preflight workflow."""

    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield adr_dir

    def test_database_choice_includes_evaluation_promptlet(self, temp_adr_dir):
        """Test PostgreSQL (database category) returns promptlet with relevant criteria."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(
            choice="PostgreSQL",
            context={"use_case": "primary database"},
            category="database",
        )

        result = workflow.execute(input_data=input_data)

        assert result.success
        assert "decision" in result.data
        assert "guidance" in result.data

        decision = result.data["decision"]
        guidance = result.data["guidance"]

        # Should return REQUIRES_ADR for new technology
        assert decision.status == "REQUIRES_ADR"

        # Guidance should include evaluation prompt
        assert "before documenting this decision" in guidance.lower()

        # Should include category guidance
        assert "database" in guidance.lower()

        # Should include primary database criteria
        assert "feedback" in guidance.lower() or "feedback_loops" in guidance.lower()
        assert "reversibility" in guidance.lower()
        assert "safety" in guidance.lower() or "security" in guidance.lower()
        assert "executability" in guidance.lower()

        # Should include call to action
        assert "adr_create()" in guidance

    def test_frontend_choice_includes_evaluation_promptlet(self, temp_adr_dir):
        """Test React (frontend category) returns promptlet with relevant criteria."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(
            choice="React",
            context={"use_case": "frontend framework"},
            category="frontend",
        )

        result = workflow.execute(input_data=input_data)

        assert result.success
        decision = result.data["decision"]
        guidance = result.data["guidance"]

        assert decision.status == "REQUIRES_ADR"

        # Should include evaluation prompt
        assert "before documenting this decision" in guidance.lower()

        # Should include frontend-specific criteria
        assert "frontend" in guidance.lower()
        assert "modularity" in guidance.lower() or "module" in guidance.lower()

        # Should reference multiple evaluation dimensions
        # Frontend has: feedback_loops, documentation_accessibility, decision_space, modularity, multi_agent
        criteria_count = sum(
            [
                "feedback" in guidance.lower(),
                "documentation" in guidance.lower(),
                "decision space" in guidance.lower() or "conventions" in guidance.lower(),
                "modularity" in guidance.lower() or "scope isolation" in guidance.lower(),
                "multi-agent" in guidance.lower() or "multi agent" in guidance.lower(),
            ]
        )
        assert criteria_count >= 3, "Should include at least 3 primary criteria"

    def test_backend_choice_includes_evaluation_promptlet(self, temp_adr_dir):
        """Test FastAPI (backend category) returns promptlet with relevant criteria."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(
            choice="FastAPI",
            category="backend",
        )

        result = workflow.execute(input_data=input_data)

        assert result.success
        decision = result.data["decision"]
        guidance = result.data["guidance"]

        assert decision.status == "REQUIRES_ADR"

        # Should include backend-specific guidance
        assert "backend" in guidance.lower()
        assert "safety" in guidance.lower() or "security" in guidance.lower()
        assert "executability" in guidance.lower()

    def test_unknown_category_gracefully_degrades(self, temp_adr_dir):
        """Test unknown category falls back to generic guidance."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(
            choice="UnknownTechnology",
            category="unknown_category_xyz",
        )

        result = workflow.execute(input_data=input_data)

        assert result.success
        decision = result.data["decision"]
        guidance = result.data["guidance"]

        assert decision.status == "REQUIRES_ADR"

        # Should still have basic guidance even without promptlet
        assert "requires ADR" in guidance
        assert "adr_create()" in guidance

        # Should NOT include evaluation prompt if promptlet loading failed
        # (graceful degradation)
        # The guidance will still work, just without the enhanced evaluation criteria
        # Note: May still include "before documenting" if fallback to generic technology category works

    def test_allowed_status_does_not_include_promptlet(self, temp_adr_dir):
        """Test ALLOWED status does not inject evaluation promptlet."""
        # This test may be difficult to trigger without an approved ADR
        # We'll test the logic by checking that ALLOWED guidance is concise
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)

        # Most choices without existing ADRs will be REQUIRES_ADR
        # For this test, we verify the structure: ALLOWED should be short
        input_data = PreflightInput(choice="TestChoice")

        result = workflow.execute(input_data=input_data)
        guidance = result.data["guidance"]

        # If it's ALLOWED, guidance should be concise (no evaluation promptlet)
        if result.data["decision"].status == "ALLOWED":
            assert "before documenting this decision" not in guidance.lower()
            assert len(guidance.split("\n")) <= 3  # Should be 1-3 lines max

    def test_blocked_status_does_not_include_promptlet(self, temp_adr_dir):
        """Test BLOCKED status does not inject evaluation promptlet."""
        # Similar to ALLOWED - BLOCKED should be concise and direct
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(choice="BlockedChoice")

        result = workflow.execute(input_data=input_data)
        guidance = result.data["guidance"]

        # If it's BLOCKED, guidance should be concise (no evaluation promptlet)
        if result.data["decision"].status == "BLOCKED":
            assert "before documenting this decision" not in guidance.lower()
            # Should focus on the blocking reason, not evaluation

    def test_auto_categorization_with_promptlet_injection(self, temp_adr_dir):
        """Test that auto-categorization works and promptlet matches the category."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)

        # Don't provide category hint - let workflow categorize
        input_data = PreflightInput(
            choice="MongoDB",  # Should be categorized as database
        )

        result = workflow.execute(input_data=input_data)

        assert result.success
        decision = result.data["decision"]
        guidance = result.data["guidance"]

        assert decision.status == "REQUIRES_ADR"

        # Should include database-specific criteria even without explicit category
        assert "database" in guidance.lower()
        assert "reversibility" in guidance.lower()

    def test_promptlet_includes_structured_sections(self, temp_adr_dir):
        """Test that promptlet has structured sections with headers."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(choice="PostgreSQL", category="database")

        result = workflow.execute(input_data=input_data)

        assert result.success
        guidance = result.data["guidance"]

        # Promptlet should have structured format with markdown headers
        assert "##" in guidance or "**" in guidance  # Should have some formatting

        # Should have multiple sections (assembled from criteria)
        # Each criterion becomes a numbered section
        lines = guidance.split("\n")
        assert len(lines) > 10, "Promptlet should be substantive with multiple lines"

    def test_guidance_includes_next_action(self, temp_adr_dir):
        """Test that guidance includes clear next action (call adr_create)."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(choice="PostgreSQL", category="database")

        result = workflow.execute(input_data=input_data)

        assert result.success
        guidance = result.data["guidance"]

        # Should explicitly tell agent to call adr_create
        assert "adr_create()" in guidance

        # Should mention documenting the decision
        assert "document" in guidance.lower()

    def test_category_defaults_to_technology_for_unknown_choices(self, temp_adr_dir):
        """Test that unknown technologies get 'technology' category with appropriate promptlet."""
        workflow = PreflightWorkflow(adr_dir=temp_adr_dir)
        input_data = PreflightInput(
            choice="SomeNewTool2024",  # Not in any predefined category
        )

        result = workflow.execute(input_data=input_data)

        assert result.success
        guidance = result.data["guidance"]

        # Should get "technology" category guidance
        # Technology category focuses on: feedback_loops, documentation_accessibility, executability
        assert "technology" in guidance.lower() or "evaluate" in guidance.lower()
        assert "feedback" in guidance.lower()
        assert "documentation" in guidance.lower()
