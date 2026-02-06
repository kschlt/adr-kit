"""Unit tests for policy validation in ADR creation workflow."""

import tempfile
from pathlib import Path

import pytest

from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus
from adr_kit.core.policy_extractor import PolicyExtractor
from adr_kit.workflows.creation import CreationInput, CreationWorkflow


class TestPolicyValidation:
    """Test policy validation during ADR creation."""

    def test_creation_without_policy_returns_warning(self):
        """ADR creation without policy should return validation warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            input_data = CreationInput(
                title="Use FastAPI as Web Framework",
                context="Need a modern Python web framework with async support.",
                decision="Use FastAPI for backend API development.",
                consequences="Better performance and automatic documentation.",
                alternatives="Rejected Flask due to lack of native async support.",
            )

            result = workflow.execute(input_data=input_data)

            assert result.success
            assert result.data is not None
            creation_result = result.data["creation_result"]

            # Should have warnings about missing policy
            assert len(creation_result.validation_warnings) > 0
            warning_text = " ".join(creation_result.validation_warnings)
            assert "policy" in warning_text.lower()
            assert "constraint extraction" in warning_text.lower()

    def test_creation_with_structured_policy_no_warning(self):
        """ADR with structured policy should not trigger validation warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            input_data = CreationInput(
                title="Use FastAPI as Web Framework",
                context="Need async support",
                decision="Use FastAPI",
                consequences="Better performance",
                policy={
                    "imports": {"disallow": ["flask"], "prefer": ["fastapi"]},
                },
            )

            result = workflow.execute(input_data=input_data)

            assert result.success
            creation_result = result.data["creation_result"]

            # Should NOT have policy-related warnings
            policy_warnings = [
                w
                for w in creation_result.validation_warnings
                if "policy" in w.lower() or "constraint extraction" in w.lower()
            ]
            assert len(policy_warnings) == 0

    def test_creation_with_pattern_language_no_warning(self):
        """ADR with pattern-matching language should not trigger warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            input_data = CreationInput(
                title="Use FastAPI as Web Framework",
                context="Need async support",
                decision="Use FastAPI. **Don't use Flask** as it lacks native async support.",
                consequences="**Avoid** synchronous frameworks like Flask.",
            )

            result = workflow.execute(input_data=input_data)

            assert result.success
            creation_result = result.data["creation_result"]

            # Should NOT have policy warnings (patterns detected)
            policy_warnings = [
                w
                for w in creation_result.validation_warnings
                if "policy" in w.lower() or "constraint extraction" in w.lower()
            ]
            assert len(policy_warnings) == 0

    def test_policy_extractor_with_structured_policy(self):
        """PolicyExtractor should extract from structured policy."""
        from datetime import date

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "imports": {"disallow": ["flask"], "prefer": ["fastapi"]},
            },
        )

        adr = ADR(front_matter=front_matter, content="Test content")

        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr) is True

        policy = extractor.extract_policy(adr)
        assert policy.get_disallowed_imports() == ["flask"]
        assert policy.get_preferred_imports() == ["fastapi"]

    def test_policy_extractor_with_pattern_language(self):
        """PolicyExtractor should extract from pattern-matching language."""
        from datetime import date

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
        )

        content = """
## Decision

Use FastAPI. **Don't use Flask** or Django.
**Prefer FastAPI over Flask** for this use case.

## Consequences

**Avoid** synchronous frameworks.
"""

        adr = ADR(front_matter=front_matter, content=content)

        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr) is True

        policy = extractor.extract_policy(adr)
        # Should extract Flask from "Don't use Flask"
        disallowed = policy.get_disallowed_imports()
        assert any("flask" in item.lower() for item in disallowed)

    def test_policy_extractor_without_policy(self):
        """PolicyExtractor should return False for ADR without policy."""
        from datetime import date

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
        )

        content = """
## Decision

Use FastAPI as the framework.

## Consequences

Provides good performance.
"""

        adr = ADR(front_matter=front_matter, content=content)

        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr) is False

    def test_policy_suggestion_from_alternatives(self):
        """Should suggest policy based on alternatives text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            input_data = CreationInput(
                title="Use FastAPI",
                context="Need framework",
                decision="Use FastAPI as the framework",
                consequences="Better performance",
                alternatives="Rejected Flask and Django",
            )

            result = workflow.execute(input_data=input_data)

            assert result.success
            creation_result = result.data["creation_result"]

            # Should have suggestions
            warnings = creation_result.validation_warnings
            assert len(warnings) > 0

            # Check if suggestion includes Flask
            suggestion_text = " ".join(warnings)
            assert "Suggested policy" in suggestion_text
            assert "Flask" in suggestion_text or "flask" in suggestion_text.lower()

    def test_validation_backward_compatible(self):
        """Validation should not break existing workflows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            # Minimal valid input (what existing code might provide)
            input_data = CreationInput(
                title="Test Decision",
                context="Some context here",
                decision="Make this decision",
                consequences="Some consequences",
            )

            result = workflow.execute(input_data=input_data)

            # Should succeed (warnings are non-blocking)
            assert result.success
            assert result.data is not None
            assert result.data["creation_result"].adr_id is not None
            assert Path(result.data["creation_result"].file_path).exists()


class TestPolicySuggestion:
    """Test policy suggestion helper method."""

    def test_suggest_from_rejected_alternatives(self):
        """Should extract rejected technologies from alternatives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            decision = "Use FastAPI"
            alternatives = "Rejected: Flask\nRejected: Django"

            suggested = workflow._suggest_policy_from_alternatives(decision, alternatives)

            assert suggested is not None
            assert "imports" in suggested
            assert "disallow" in suggested["imports"]
            assert any("flask" in item.lower() for item in suggested["imports"]["disallow"])

    def test_suggest_from_use_statement(self):
        """Should extract chosen technology from 'Use X' statement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            decision = "Use FastAPI as our framework"
            alternatives = ""

            suggested = workflow._suggest_policy_from_alternatives(decision, alternatives)

            assert suggested is not None
            assert "imports" in suggested
            assert "prefer" in suggested["imports"]
            assert "FastAPI" in suggested["imports"]["prefer"]

    def test_suggest_no_policy_when_no_patterns(self):
        """Should return None when no recognizable patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = CreationWorkflow(adr_dir=tmpdir)

            decision = "We decided this approach is better"
            alternatives = "We considered other options"

            suggested = workflow._suggest_policy_from_alternatives(decision, alternatives)

            # No clear technology names or rejected patterns
            assert suggested is None or len(suggested) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
