"""Tests for core ADR models."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from adr_kit.core.model import (
    ADR,
    ADRFrontMatter,
    ADRStatus,
    ArchitecturePolicy,
    LayerBoundaryRule,
    PatternPolicy,
    PatternRule,
    PolicyModel,
    RequiredStructure,
)


class TestADRFrontMatter:
    """Test ADR front-matter model."""

    def test_valid_front_matter(self):
        """Test creating valid ADR front-matter."""
        fm = ADRFrontMatter(
            id="ADR-0001",
            title="Use React Query for data fetching",
            status=ADRStatus.ACCEPTED,
            date=date.today(),
            deciders=["team-lead"],
            tags=["frontend", "data"],
        )

        assert fm.id == "ADR-0001"
        assert fm.title == "Use React Query for data fetching"
        assert fm.status == ADRStatus.ACCEPTED
        assert fm.deciders == ["team-lead"]
        assert fm.tags == ["frontend", "data"]

    def test_invalid_id_format(self):
        """Test that invalid ID format raises validation error."""
        with pytest.raises(ValidationError, match="pattern"):
            ADRFrontMatter(
                id="INVALID-001",
                title="Test",
                status=ADRStatus.PROPOSED,
                date=date.today(),
            )

    def test_superseded_allows_empty_superseded_by(self):
        """Test that superseded status currently allows empty superseded_by field."""
        # Note: This test reflects current behavior - validation doesn't enforce the rule
        fm = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.SUPERSEDED,
            date=date.today(),
        )
        assert fm.status == ADRStatus.SUPERSEDED
        assert fm.superseded_by is None

    def test_superseded_with_superseded_by(self):
        """Test that superseded status with superseded_by is valid."""
        fm = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.SUPERSEDED,
            date=date.today(),
            superseded_by=["ADR-0002"],
        )

        assert fm.status == ADRStatus.SUPERSEDED
        assert fm.superseded_by == ["ADR-0002"]

    def test_empty_lists_become_none(self):
        """Test that empty lists are converted to None."""
        fm = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date.today(),
            tags=[],
            deciders=[],
        )

        assert fm.tags is None
        assert fm.deciders is None


class TestADR:
    """Test complete ADR model."""

    def test_valid_adr(self):
        """Test creating a valid ADR."""
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI",
            status=ADRStatus.ACCEPTED,
            date=date.today(),
        )

        content = "# Decision\nUse FastAPI for the backend API."

        adr = ADR(
            front_matter=front_matter,
            content=content,
            file_path=Path("docs/adr/ADR-0001-use-fastapi.md"),
        )

        assert adr.id == "ADR-0001"
        assert adr.title == "Use FastAPI"
        assert adr.status == ADRStatus.ACCEPTED
        assert adr.content == content
        assert adr.file_path == Path("docs/adr/ADR-0001-use-fastapi.md")

    def test_to_markdown(self):
        """Test converting ADR to markdown format."""
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI",
            status=ADRStatus.ACCEPTED,
            date=date(2025, 9, 3),
            tags=["backend", "api"],
        )

        content = "# Decision\n\nUse FastAPI for the backend API."

        adr = ADR(front_matter=front_matter, content=content)
        markdown = adr.to_markdown()

        assert "---" in markdown
        assert "id: ADR-0001" in markdown
        assert "title: Use FastAPI" in markdown
        assert "status: accepted" in markdown
        assert "date: 2025-09-03" in markdown
        assert "tags:" in markdown
        assert "- backend" in markdown
        assert "- api" in markdown
        assert "# Decision\n\nUse FastAPI for the backend API." in markdown

    def test_convenience_properties(self):
        """Test ADR convenience properties."""
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test Title",
            status=ADRStatus.PROPOSED,
            date=date.today(),
        )

        adr = ADR(front_matter=front_matter, content="Test content")

        assert adr.id == "ADR-0001"
        assert adr.title == "Test Title"
        assert adr.status == ADRStatus.PROPOSED


class TestPatternRule:
    """Test PatternRule model."""

    def test_valid_pattern_rule_with_regex(self):
        """Test creating a pattern rule with regex string."""
        rule = PatternRule(
            description="All FastAPI handlers must be async",
            language="python",
            rule=r"def\s+\w+",
            severity="error",
        )

        assert rule.description == "All FastAPI handlers must be async"
        assert rule.language == "python"
        assert rule.rule == r"def\s+\w+"
        assert rule.severity == "error"

    def test_valid_pattern_rule_with_dict(self):
        """Test creating a pattern rule with structured query dict."""
        rule = PatternRule(
            description="No any types allowed",
            language="typescript",
            rule={"type": "ast_query", "pattern": "any"},
            severity="warning",
        )

        assert rule.description == "No any types allowed"
        assert isinstance(rule.rule, dict)
        assert rule.rule["type"] == "ast_query"
        assert rule.severity == "warning"

    def test_invalid_regex_rejected(self):
        """Test that invalid regex pattern raises validation error."""
        with pytest.raises(ValidationError, match="Invalid regex pattern"):
            PatternRule(
                description="Test",
                rule="[invalid(regex",  # Unclosed bracket
                severity="error",
            )

    def test_invalid_severity_rejected(self):
        """Test that invalid severity raises validation error."""
        with pytest.raises(ValidationError, match="Severity must be one of"):
            PatternRule(
                description="Test",
                rule=r"test",
                severity="critical",  # Not in allowed values
            )

    def test_default_severity(self):
        """Test that severity defaults to 'error'."""
        rule = PatternRule(
            description="Test rule",
            rule=r"test",
        )
        assert rule.severity == "error"

    def test_optional_fields(self):
        """Test that language and autofix are optional."""
        rule = PatternRule(
            description="Test rule",
            rule=r"test",
        )
        assert rule.language is None
        assert rule.autofix is None


class TestPatternPolicy:
    """Test PatternPolicy model."""

    def test_pattern_policy_with_multiple_rules(self):
        """Test creating pattern policy with multiple named rules."""
        policy = PatternPolicy(
            patterns={
                "async_handlers": PatternRule(
                    description="All handlers must be async",
                    rule=r"def\s+\w+",
                    severity="error",
                ),
                "no_print": PatternRule(
                    description="No print statements",
                    rule=r"print\(",
                    severity="warning",
                ),
            }
        )

        assert policy.patterns is not None
        assert len(policy.patterns) == 2
        assert "async_handlers" in policy.patterns
        assert "no_print" in policy.patterns
        assert policy.patterns["async_handlers"].severity == "error"
        assert policy.patterns["no_print"].severity == "warning"

    def test_pattern_policy_empty(self):
        """Test creating empty pattern policy."""
        policy = PatternPolicy(patterns=None)
        assert policy.patterns is None


class TestPolicyModelWithPatterns:
    """Test PolicyModel with patterns field."""

    def test_policy_model_includes_patterns(self):
        """Test that PolicyModel can include pattern policies."""
        policy = PolicyModel(
            patterns=PatternPolicy(
                patterns={
                    "test_rule": PatternRule(
                        description="Test",
                        rule=r"test",
                        severity="error",
                    )
                }
            )
        )

        assert policy.patterns is not None
        assert policy.patterns.patterns is not None
        assert "test_rule" in policy.patterns.patterns


class TestLayerBoundaryRule:
    """Test LayerBoundaryRule model."""

    def test_valid_boundary_rule(self):
        """Test creating a valid layer boundary rule."""
        rule = LayerBoundaryRule(
            rule="ui -> database",
            check="src/ui/**/*.py",
            action="block",
            message="UI layer must not directly access database",
        )

        assert rule.rule == "ui -> database"
        assert rule.check == "src/ui/**/*.py"
        assert rule.action == "block"
        assert rule.message == "UI layer must not directly access database"

    def test_default_action(self):
        """Test that action defaults to 'block'."""
        rule = LayerBoundaryRule(rule="frontend -> backend")
        assert rule.action == "block"

    def test_invalid_action_rejected(self):
        """Test that invalid action raises validation error."""
        with pytest.raises(ValidationError, match="Action must be one of"):
            LayerBoundaryRule(
                rule="ui -> database",
                action="forbid",  # Not in allowed values
            )

    def test_optional_fields(self):
        """Test that check and message are optional."""
        rule = LayerBoundaryRule(rule="ui -> database")
        assert rule.check is None
        assert rule.message is None


class TestRequiredStructure:
    """Test RequiredStructure model."""

    def test_valid_required_structure(self):
        """Test creating a valid required structure."""
        struct = RequiredStructure(
            path="src/models/*.py",
            description="Models directory must exist",
        )

        assert struct.path == "src/models/*.py"
        assert struct.description == "Models directory must exist"

    def test_optional_description(self):
        """Test that description is optional."""
        struct = RequiredStructure(path="src/config/")
        assert struct.path == "src/config/"
        assert struct.description is None


class TestArchitecturePolicy:
    """Test ArchitecturePolicy model."""

    def test_architecture_with_boundaries_and_structure(self):
        """Test creating architecture policy with both boundaries and structure."""
        policy = ArchitecturePolicy(
            layer_boundaries=[
                LayerBoundaryRule(rule="ui -> database", action="block"),
                LayerBoundaryRule(rule="api -> ui", action="warn"),
            ],
            required_structure=[
                RequiredStructure(path="src/models/"),
                RequiredStructure(path="src/config/"),
            ],
        )

        assert policy.layer_boundaries is not None
        assert len(policy.layer_boundaries) == 2
        assert policy.layer_boundaries[0].rule == "ui -> database"
        assert policy.layer_boundaries[0].action == "block"
        assert policy.layer_boundaries[1].rule == "api -> ui"
        assert policy.layer_boundaries[1].action == "warn"

        assert policy.required_structure is not None
        assert len(policy.required_structure) == 2
        assert policy.required_structure[0].path == "src/models/"

    def test_architecture_boundaries_only(self):
        """Test creating architecture policy with only boundaries."""
        policy = ArchitecturePolicy(
            layer_boundaries=[LayerBoundaryRule(rule="ui -> database")]
        )

        assert policy.layer_boundaries is not None
        assert len(policy.layer_boundaries) == 1
        assert policy.required_structure is None

    def test_architecture_structure_only(self):
        """Test creating architecture policy with only required structure."""
        policy = ArchitecturePolicy(
            required_structure=[RequiredStructure(path="src/models/")]
        )

        assert policy.layer_boundaries is None
        assert policy.required_structure is not None
        assert len(policy.required_structure) == 1


class TestPolicyModelWithArchitecture:
    """Test PolicyModel with architecture field."""

    def test_policy_model_includes_architecture(self):
        """Test that PolicyModel can include architecture policies."""
        policy = PolicyModel(
            architecture=ArchitecturePolicy(
                layer_boundaries=[LayerBoundaryRule(rule="ui -> database")],
                required_structure=[RequiredStructure(path="src/models/")],
            )
        )

        assert policy.architecture is not None
        assert policy.architecture.layer_boundaries is not None
        assert policy.architecture.required_structure is not None

    def test_policy_model_has_architecture_field(self):
        """Test that PolicyModel has new architecture field."""
        # Verify the new architecture field exists (boundaries kept for backward compat)
        policy = PolicyModel()
        assert hasattr(policy, "architecture")
        assert hasattr(policy, "boundaries")  # Deprecated but kept temporarily
