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
            # New message uses "detected" and "enforcement" instead of "constraint extraction"
            assert (
                "detected" in warning_text.lower()
                or "enforcement" in warning_text.lower()
            )

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

    def test_policy_guidance_provided_when_no_policy(self):
        """Should provide policy guidance when no policy provided."""
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

            # Should provide policy guidance
            assert "policy_guidance" in result.data
            guidance = result.data["policy_guidance"]

            # Should indicate no policy provided
            assert guidance["has_policy"] is False

            # Should provide reasoning prompts for agents
            assert "agent_task" in guidance
            assert "policy_capabilities" in guidance

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

    def test_policy_extractor_with_pattern_policy(self):
        """PolicyExtractor should extract pattern policies from front-matter."""
        from datetime import date

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test Pattern Policy",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "patterns": {
                    "patterns": {
                        "async_handlers": {
                            "description": "All FastAPI handlers must be async",
                            "rule": "def\\s+\\w+",
                            "severity": "error",
                        }
                    }
                }
            },
        )

        adr = ADR(front_matter=front_matter, content="Test content")

        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr) is True

        policy = extractor.extract_policy(adr)
        assert policy.patterns is not None
        assert policy.patterns.patterns is not None
        assert "async_handlers" in policy.patterns.patterns
        assert (
            policy.patterns.patterns["async_handlers"].description
            == "All FastAPI handlers must be async"
        )

    def test_policy_extractor_with_architecture_policy(self):
        """PolicyExtractor should extract architecture policies from front-matter."""
        from datetime import date

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test Architecture Policy",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "architecture": {
                    "layer_boundaries": [
                        {
                            "rule": "ui -> database",
                            "action": "block",
                        }
                    ],
                    "required_structure": [
                        {
                            "path": "src/api",
                            "type": "directory",
                            "reason": "All API code must be in src/api",
                        }
                    ],
                }
            },
        )

        adr = ADR(front_matter=front_matter, content="Test content")

        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr) is True

        policy = extractor.extract_policy(adr)
        assert policy.architecture is not None
        assert policy.architecture.layer_boundaries is not None
        assert len(policy.architecture.layer_boundaries) == 1
        assert policy.architecture.layer_boundaries[0].rule == "ui -> database"
        assert policy.architecture.required_structure is not None
        assert len(policy.architecture.required_structure) == 1
        assert policy.architecture.required_structure[0].path == "src/api"

    def test_policy_extractor_with_config_enforcement_policy(self):
        """PolicyExtractor should extract config enforcement policies from front-matter."""
        from datetime import date

        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test Config Enforcement Policy",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "config_enforcement": {
                    "typescript": {
                        "tsconfig": {
                            "compilerOptions": {
                                "strict": True,
                                "noImplicitAny": True,
                            }
                        }
                    },
                    "python": {
                        "ruff": {
                            "select": ["E", "F"],
                        },
                        "mypy": {
                            "strict": True,
                        },
                    },
                }
            },
        )

        adr = ADR(front_matter=front_matter, content="Test content")

        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr) is True

        policy = extractor.extract_policy(adr)
        assert policy.config_enforcement is not None
        assert policy.config_enforcement.typescript is not None
        assert policy.config_enforcement.typescript.tsconfig is not None
        assert (
            policy.config_enforcement.typescript.tsconfig["compilerOptions"]["strict"]
            is True
        )
        assert policy.config_enforcement.python is not None
        assert policy.config_enforcement.python.ruff is not None
        assert policy.config_enforcement.python.mypy is not None

    def test_has_extractable_policy_with_new_types(self):
        """has_extractable_policy should return True for new policy types."""
        from datetime import date

        # Test with pattern policy only
        front_matter_patterns = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "patterns": {
                    "patterns": {
                        "rule1": {
                            "description": "Test",
                            "rule": ".*",
                            "severity": "error",
                        }
                    }
                }
            },
        )
        adr_patterns = ADR(front_matter=front_matter_patterns, content="Test")
        extractor = PolicyExtractor()
        assert extractor.has_extractable_policy(adr_patterns) is True

        # Test with architecture policy only
        front_matter_arch = ADRFrontMatter(
            id="ADR-0002",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "architecture": {
                    "layer_boundaries": [{"rule": "ui -> db", "action": "block"}]
                }
            },
        )
        adr_arch = ADR(front_matter=front_matter_arch, content="Test")
        assert extractor.has_extractable_policy(adr_arch) is True

        # Test with config enforcement policy only
        front_matter_config = ADRFrontMatter(
            id="ADR-0003",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            policy={
                "config_enforcement": {"typescript": {"tsconfig": {"strict": True}}}
            },
        )
        adr_config = ADR(front_matter=front_matter_config, content="Test")
        assert extractor.has_extractable_policy(adr_config) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
