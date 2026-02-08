"""Tests for single decision validator."""

from datetime import date

import pytest

from adr_kit.core.model import (
    ADR,
    ADRFrontMatter,
    ADRStatus,
    ImportPolicy,
    PolicyModel,
    PythonPolicy,
)
from adr_kit.core.single_decision_validator import (
    EXCESSIVE_AND_USAGE,
    MULTIPLE_CHOICES_IN_DECISION,
    MULTIPLE_DECISIONS_IN_TITLE,
    POLICY_SPANS_MULTIPLE_DOMAINS,
    SingleDecisionValidator,
    validate_single_decision,
)


class TestSingleDecisionValidator:
    """Test suite for single decision validation."""

    def test_single_decision_no_warnings(self) -> None:
        """Test that a proper single-decision ADR passes validation."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI for Backend",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(disallow=["flask"], prefer=["fastapi"]),
                ),
            ),
            content="""## Context
We need a modern Python web framework.

## Decision
Use FastAPI as our backend framework.

## Consequences
Better async support and automatic OpenAPI documentation.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        assert len(warnings) == 0

    def test_multiple_decisions_in_title_high_severity(self) -> None:
        """Test detection of multiple decisions in title."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI and Deploy to Fly.io",  # ❌ Two decisions
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Need backend and deployment.

## Decision
Use FastAPI and deploy to Fly.io.

## Consequences
Good.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        assert len(warnings) > 0
        assert any(w.type == MULTIPLE_DECISIONS_IN_TITLE for w in warnings)
        assert any(w.severity == "high" for w in warnings)

    def test_multiple_technologies_different_domains(self) -> None:
        """Test detection of technologies from different domains in title."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="FastAPI and PostgreSQL",  # Backend + Database
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Need stack.

## Decision
Use FastAPI and PostgreSQL.

## Consequences
Good stack.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should detect different domains
        title_warnings = [w for w in warnings if w.type == MULTIPLE_DECISIONS_IN_TITLE]
        assert len(title_warnings) > 0

    def test_multiple_choice_statements_in_decision(self) -> None:
        """Test detection of multiple technology choices in decision section."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Technology Stack Selection",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Need full stack.

## Decision
Use React for frontend. Use FastAPI for backend. Deploy to AWS. Use PostgreSQL for database.

## Consequences
Complete stack.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should detect multiple distinct choices
        choice_warnings = [
            w for w in warnings if w.type == MULTIPLE_CHOICES_IN_DECISION
        ]
        assert len(choice_warnings) > 0
        assert any(w.severity in ["medium", "high"] for w in choice_warnings)

    def test_policy_spans_multiple_domains(self) -> None:
        """Test detection when policy covers too many unrelated domains."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Technology Standards",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(
                        disallow=[
                            "flask",  # Backend
                            "vue",  # Frontend
                            "mysql",  # Database
                        ],
                        prefer=["fastapi", "react", "postgresql"],
                    ),
                ),
            ),
            content="""## Context
Setting standards.

## Decision
Use FastAPI, React, and PostgreSQL.

## Consequences
Consistent stack.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should detect multiple domains in policy
        policy_warnings = [
            w for w in warnings if w.type == POLICY_SPANS_MULTIPLE_DOMAINS
        ]
        assert len(policy_warnings) > 0

    def test_excessive_and_usage(self) -> None:
        """Test detection of excessive 'and' usage."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use React and TypeScript and TailwindCSS and Vite",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Need frontend tooling.

## Decision
Use React and TypeScript and TailwindCSS and Vite and ESLint.

## Consequences
Modern frontend and good DX and fast builds and type safety.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should detect excessive "and" usage
        and_warnings = [w for w in warnings if w.type == EXCESSIVE_AND_USAGE]
        assert len(and_warnings) > 0

    def test_related_technologies_allowed(self) -> None:
        """Test that related technologies in same decision are allowed."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use React with TypeScript",  # ✅ Related, same domain
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(prefer=["react", "typescript"]),
                ),
            ),
            content="""## Context
Need type-safe frontend.

## Decision
Use React with TypeScript for type safety.

## Consequences
Better developer experience with type checking.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should have few or no high-severity warnings
        high_warnings = [w for w in warnings if w.severity == "high"]
        assert len(high_warnings) == 0

    def test_has_critical_warnings(self) -> None:
        """Test the has_critical_warnings helper method."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI and Deploy to AWS and Use PostgreSQL",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Full stack.

## Decision
Use FastAPI and deploy to AWS and use PostgreSQL.

## Consequences
Done.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should have critical warnings
        assert validator.has_critical_warnings(warnings)

    def test_format_warnings_for_display(self) -> None:
        """Test warning formatting for user display."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI and PostgreSQL",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Stack.

## Decision
Use both.

## Consequences
Good.
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        formatted = validator.format_warnings_for_display(warnings)

        # Should include emoji, message, suggestion
        assert "⚠️" in formatted or "✅" in formatted
        if warnings:
            assert "Suggestion:" in formatted
            assert "Evidence:" in formatted or len(warnings) == 0

    def test_convenience_function(self) -> None:
        """Test the validate_single_decision convenience function."""
        # Good ADR
        good_adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Need backend.

## Decision
Use FastAPI.

## Consequences
Good.
""",
        )

        is_valid, warnings = validate_single_decision(good_adr)
        assert is_valid
        assert len(warnings) == 0

        # Bad ADR
        bad_adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0002",
                title="Use FastAPI and PostgreSQL and Deploy to AWS",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Everything.

## Decision
Do everything.

## Consequences
Done.
""",
        )

        is_valid, warnings = validate_single_decision(bad_adr)
        assert not is_valid  # Has high severity warnings
        assert len(warnings) > 0

    def test_implementation_details_not_flagged(self) -> None:
        """Test that implementation details aren't confused with multiple decisions."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI with Pydantic Validation",
                status=ADRStatus.PROPOSED,
                date=date(2025, 1, 1),
                deciders=["team"],
            ),
            content="""## Context
Need API framework with validation.

## Decision
Use FastAPI as our backend framework. We will use Pydantic for request validation
and response serialization, which is natively integrated with FastAPI.

## Consequences
- Automatic request validation
- Type-safe responses
- OpenAPI documentation generation
""",
        )

        validator = SingleDecisionValidator()
        warnings = validator.validate(adr)

        # Should not have high severity warnings for implementation details
        high_warnings = [w for w in warnings if w.severity == "high"]
        assert len(high_warnings) == 0


class TestDomainDetection:
    """Test domain detection logic."""

    def test_detect_backend_domain(self) -> None:
        """Test detection of backend technologies."""
        validator = SingleDecisionValidator()

        assert validator._detect_domain("fastapi") == "backend"
        assert validator._detect_domain("express server") == "backend"
        assert validator._detect_domain("api endpoint") == "backend"

    def test_detect_frontend_domain(self) -> None:
        """Test detection of frontend technologies."""
        validator = SingleDecisionValidator()

        assert validator._detect_domain("react") == "frontend"
        assert validator._detect_domain("vue component") == "frontend"
        assert validator._detect_domain("ui") == "frontend"

    def test_detect_database_domain(self) -> None:
        """Test detection of database technologies."""
        validator = SingleDecisionValidator()

        assert validator._detect_domain("postgresql") == "database"
        assert validator._detect_domain("database") == "database"
        assert validator._detect_domain("storage") == "database"

    def test_detect_infrastructure_domain(self) -> None:
        """Test detection of infrastructure technologies."""
        validator = SingleDecisionValidator()

        assert validator._detect_domain("docker") == "infrastructure"
        assert validator._detect_domain("kubernetes deployment") == "infrastructure"
        assert validator._detect_domain("host") == "infrastructure"

    def test_unknown_domain_returns_none(self) -> None:
        """Test that unknown terms return None."""
        validator = SingleDecisionValidator()

        assert validator._detect_domain("unknowntech") is None
        assert validator._detect_domain("random") is None
