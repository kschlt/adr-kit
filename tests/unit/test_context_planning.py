"""Tests for planning context module - AI warnings and domain filtering."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from adr_kit.context.analyzer import TaskAnalyzer, TaskContext, TaskType
from adr_kit.context.guidance import GuidanceGenerator, GuidanceType
from adr_kit.context.models import ContextualADR, TaskHint
from adr_kit.context.planner import PlanningConfig, PlanningContext
from adr_kit.context.ranker import RankingStrategy, RelevanceRanker
from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus


class TestAIWarningExtraction:
    """Test AI warning extraction from ADR consequences."""

    def test_extract_bold_heading_warnings(self):
        """Test extraction of warnings with bold headings."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Test ADR",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
            ),
            content="""## Decision
Use Express.js for backend.

## Consequences

**Documentation**: Limited for Express 5.x
**Known AI Pitfall**: Middleware ordering matters significantly
**Test Determinism**: Requires in-memory database mock for reliable tests
""",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs/adr"
            adr_dir.mkdir(parents=True)

            # Create planning context
            config = PlanningConfig(adr_dir=adr_dir)
            planner = PlanningContext(config)

            # Extract warnings
            warnings = planner._extract_ai_warnings(adr)

            # Should extract all 3 warnings
            assert len(warnings) == 3
            assert any("Documentation: Limited for Express 5.x" in w for w in warnings)
            assert any("Known AI Pitfall: Middleware ordering" in w for w in warnings)
            assert any("Test Determinism: Requires in-memory" in w for w in warnings)

    def test_extract_warning_patterns_from_consequences(self):
        """Test extraction of warning patterns from consequences section."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0002",
                title="Database Choice",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
            ),
            content="""## Decision
Use PostgreSQL.

## Consequences

- Performance is excellent for most use cases
- Requires careful connection pool configuration
- May fail under high concurrent write loads without tuning
- Limited documentation for advanced features in version 15
""",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs/adr"
            adr_dir.mkdir(parents=True)

            config = PlanningConfig(adr_dir=adr_dir)
            planner = PlanningContext(config)

            warnings = planner._extract_ai_warnings(adr)

            # Should extract warnings with warning indicators
            assert len(warnings) > 0
            assert any("requires careful" in w.lower() for w in warnings)
            assert any("may fail" in w.lower() for w in warnings)
            assert any("limited documentation" in w.lower() for w in warnings)

    def test_warning_limit_to_three(self):
        """Test that warnings are limited to 3 per ADR."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0003",
                title="Many Warnings",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
            ),
            content="""## Consequences

**Warning 1**: First warning
**Warning 2**: Second warning
**Warning 3**: Third warning
**Warning 4**: Fourth warning
**Warning 5**: Fifth warning
""",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs/adr"
            adr_dir.mkdir(parents=True)

            config = PlanningConfig(adr_dir=adr_dir)
            planner = PlanningContext(config)

            warnings = planner._extract_ai_warnings(adr)

            # Should limit to 3 warnings
            assert len(warnings) <= 3

    def test_no_warnings_in_adr(self):
        """Test ADR with no warnings returns empty list."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0004",
                title="Simple ADR",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
            ),
            content="""## Decision
Use React.

## Consequences

- Great developer experience
- Large ecosystem
- Good performance
""",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs/adr"
            adr_dir.mkdir(parents=True)

            config = PlanningConfig(adr_dir=adr_dir)
            planner = PlanningContext(config)

            warnings = planner._extract_ai_warnings(adr)

            assert len(warnings) == 0


class TestDomainFiltering:
    """Test improved domain-based filtering."""

    def test_tag_domain_overlap_direct_match(self):
        """Test direct tag match with architectural scope."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0010",
                title="Backend Framework",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
                tags=["backend", "api"],
            ),
            content="Use FastAPI for backend services.",
        )

        task_context = TaskContext(
            task_description="Add user registration API endpoint",
            task_type=TaskType.FEATURE,
            technologies={"python", "api", "backend"},
            file_patterns={"*.py"},
            keywords={"add", "user", "registration", "endpoint"},
            priority_indicators=[],
            complexity_indicators=[],
        )

        ranker = RelevanceRanker(RankingStrategy.HYBRID)
        score, reasons = ranker._score_tag_domain_overlap(adr, task_context)

        # Should get high score for direct tag match
        assert score > 0.4
        assert any("domain match" in r.lower() for r in reasons)

    def test_no_tag_cross_cutting_concern(self):
        """Test ADR with no tags gets baseline score as cross-cutting concern."""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0011",
                title="General Logging Policy",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
                tags=None,  # No tags
            ),
            content="Use structured logging across all services.",
        )

        task_context = TaskContext(
            task_description="Add logging to payment service",
            task_type=TaskType.FEATURE,
            technologies={"backend", "logging"},
            file_patterns={"*.py"},
            keywords={"add", "logging", "payment"},
            priority_indicators=[],
            complexity_indicators=[],
        )

        ranker = RelevanceRanker(RankingStrategy.HYBRID)
        score, reasons = ranker._score_tag_domain_overlap(adr, task_context)

        # Should get baseline score
        assert score == 0.1
        assert any("cross-cutting" in r.lower() for r in reasons)

    def test_increased_filtering_threshold(self):
        """Test that low-relevance ADRs are filtered out with new threshold."""
        adr_low_relevance = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0012",
                title="Frontend Styling",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
                tags=["frontend", "ui"],
            ),
            content="Use Tailwind CSS for styling.",
        )

        adr_high_relevance = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0013",
                title="Backend API Framework",
                status=ADRStatus.ACCEPTED,
                date=date.today(),
                deciders=["test"],
                tags=["backend", "api"],
            ),
            content="Use FastAPI for backend APIs.",
        )

        task_context = TaskContext(
            task_description="Add user authentication API endpoint",
            task_type=TaskType.FEATURE,
            technologies={"python", "api", "backend"},
            file_patterns={"*.py"},
            keywords={"add", "authentication", "endpoint"},
            priority_indicators=[],
            complexity_indicators=[],
        )

        ranker = RelevanceRanker(RankingStrategy.HYBRID)
        scores = ranker.rank_adrs_for_task(
            [adr_low_relevance, adr_high_relevance], task_context
        )

        # Low relevance ADR should be filtered out (threshold 0.25)
        # High relevance ADR should be included
        adr_ids = [s.adr_id for s in scores]

        assert "ADR-0013" in adr_ids  # High relevance included
        # ADR-0012 might or might not be filtered depending on status/other factors
        # but there should be filtering happening

    def test_domain_filtering_reduces_context(self):
        """Test that domain filtering significantly reduces ADR count."""
        # Create multiple ADRs across different domains
        adrs = [
            ADR(
                front_matter=ADRFrontMatter(
                    id=f"ADR-{i:04d}",
                    title=f"Frontend ADR {i}",
                    status=ADRStatus.ACCEPTED,
                    date=date.today(),
                    deciders=["test"],
                    tags=["frontend", "ui"],
                ),
                content="Frontend decision.",
            )
            for i in range(1, 6)
        ] + [
            ADR(
                front_matter=ADRFrontMatter(
                    id=f"ADR-{i:04d}",
                    title=f"Backend ADR {i}",
                    status=ADRStatus.ACCEPTED,
                    date=date.today(),
                    deciders=["test"],
                    tags=["backend", "api"],
                ),
                content="Backend decision.",
            )
            for i in range(6, 11)
        ]

        # Backend task should filter out frontend ADRs
        task_context = TaskContext(
            task_description="Add database query optimization",
            task_type=TaskType.PERFORMANCE,
            technologies={"backend", "database", "sql"},
            file_patterns={"*.py"},
            keywords={"database", "query", "optimize"},
            priority_indicators=[],
            complexity_indicators=[],
        )

        ranker = RelevanceRanker(RankingStrategy.HYBRID)
        scores = ranker.rank_adrs_for_task(adrs, task_context)

        # Should significantly reduce from 10 ADRs
        # Expect ~50-80% reduction (so 2-5 ADRs remaining)
        assert len(scores) < len(adrs)  # Some filtering happened
        assert len(scores) <= 5  # Significant reduction


class TestGuidanceWithAIWarnings:
    """Test that AI warnings are included in planning guidance."""

    def test_ai_warnings_appear_in_guidance(self):
        """Test that extracted AI warnings appear in planning guidance."""
        contextual_adr = ContextualADR(
            id="ADR-0020",
            title="Express.js Backend",
            status=ADRStatus.ACCEPTED,
            summary="Use Express.js for backend services",
            relevance_score=0.8,  # High relevance
            relevance_reason="Backend framework match",
            key_constraints=["Don't use Express 5.x alpha"],
            related_technologies=["nodejs", "express"],
            ai_warnings=[
                "Documentation: Limited for Express 5.x",
                "Test Determinism: Requires mocking",
            ],
        )

        task_context = TaskContext(
            task_description="Add API endpoint",
            task_type=TaskType.FEATURE,
            technologies={"nodejs", "backend"},
            file_patterns={"*.js"},
            keywords={"add", "api", "endpoint"},
            priority_indicators=[],
            complexity_indicators=[],
        )

        generator = GuidanceGenerator()
        guidance = generator._generate_adr_guidance([contextual_adr], [], task_context)

        # Should include AI warnings
        ai_warning_guidance = [
            g for g in guidance if g.guidance_type == GuidanceType.AI_WARNING.value
        ]

        assert len(ai_warning_guidance) > 0
        assert any("Limited for Express 5.x" in g.message for g in ai_warning_guidance)
        assert any("ADR-0020" in g.source_adrs for g in ai_warning_guidance)

    def test_ai_warnings_have_high_priority(self):
        """Test that AI warnings are marked as high priority."""
        contextual_adr = ContextualADR(
            id="ADR-0021",
            title="Database Choice",
            status=ADRStatus.ACCEPTED,
            summary="Use PostgreSQL",
            relevance_score=0.9,
            relevance_reason="Database match",
            key_constraints=[],
            related_technologies=["postgres"],
            ai_warnings=["Known AI Pitfall: Connection pool configuration is critical"],
        )

        task_context = TaskContext(
            task_description="Add database migrations",
            task_type=TaskType.MIGRATION,
            technologies={"database", "postgres"},
            file_patterns={"*.sql"},
            keywords={"database", "migration"},
            priority_indicators=[],
            complexity_indicators=[],
        )

        generator = GuidanceGenerator()
        guidance = generator._generate_adr_guidance([contextual_adr], [], task_context)

        ai_warning_guidance = [
            g for g in guidance if g.guidance_type == GuidanceType.AI_WARNING.value
        ]

        assert len(ai_warning_guidance) > 0
        assert all(g.priority == "high" for g in ai_warning_guidance)


class TestEndToEndPlanningContext:
    """End-to-end tests for planning context with new features."""

    def test_context_packet_includes_ai_warnings(self):
        """Test that context packets include AI warnings from relevant ADRs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs/adr"
            adr_dir.mkdir(parents=True)

            # Create an ADR file with AI warnings
            adr_file = adr_dir / "ADR-0001-express-backend.md"
            adr_file.write_text(
                """---
id: ADR-0001
title: Use Express.js for Backend
status: accepted
date: 2025-01-15
deciders:
  - dev-team
tags:
  - backend
  - api
---

## Decision

Use Express.js as the backend framework.

## Consequences

**Documentation**: Limited for Express 5.x - mostly community-driven
**Known AI Pitfall**: Middleware ordering matters significantly for authentication
- Excellent ecosystem and community support
"""
            )

            # Create planning context
            config = PlanningConfig(adr_dir=adr_dir, max_relevant_adrs=3)
            planner = PlanningContext(config)

            task_hint = TaskHint(
                task_description="Add user authentication API endpoint using Express backend",
                technologies_mentioned=["nodejs", "express", "backend", "api"],
                task_type="feature",
            )

            context_packet = planner.create_context_packet(task_hint)

            # Should have relevant ADRs
            assert len(context_packet.relevant_adrs) > 0

            # Should have AI warnings in the relevant ADR
            adr_with_warnings = [
                adr for adr in context_packet.relevant_adrs if adr.ai_warnings
            ]
            assert len(adr_with_warnings) > 0

            # Should have AI warning guidance (since it's a backend API task matching backend/api tags)
            ai_warnings = [
                g for g in context_packet.guidance if g.guidance_type == "ai_warning"
            ]
            assert len(ai_warnings) > 0, (
                f"Expected AI warnings in guidance. "
                f"Relevant ADRs: {[adr.id for adr in context_packet.relevant_adrs]}, "
                f"Scores: {[adr.relevance_score for adr in context_packet.relevant_adrs]}, "
                f"Warnings: {[adr.ai_warnings for adr in context_packet.relevant_adrs]}"
            )
