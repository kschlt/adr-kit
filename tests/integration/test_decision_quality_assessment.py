"""Integration tests for decision quality assessment in creation workflow."""

import tempfile
from pathlib import Path

import pytest

from adr_kit.workflows.creation import CreationInput, CreationWorkflow


class TestDecisionQualityAssessment:
    """Test quality assessment feedback in ADR creation."""

    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)

    def test_high_quality_adr_gets_good_score(self, temp_adr_dir):
        """Test that high-quality ADR receives good score."""
        # High-quality ADR with all elements
        input_data = CreationInput(
            title="Use PostgreSQL 15 for Primary Database",
            context=(
                "We need ACID transactions for financial data integrity. "
                "Current SQLite setup doesn't support concurrent writes from multiple services. "
                "Requires complex queries with joins and JSON document storage for flexible user metadata."
            ),
            decision=(
                "Use PostgreSQL 15 as the primary database for all application data. "
                "Don't use MySQL (weaker JSON support) or MongoDB (eventual consistency conflicts with requirements). "
                "Deploy on AWS RDS with Multi-AZ for high availability."
            ),
            consequences=(
                "### Positive\n"
                "- ACID compliance guarantees data consistency\n"
                "- Rich feature set: JSON, full-text search\n"
                "- Excellent query planner\n\n"
                "### Negative\n"
                "- Higher resource usage than simpler databases\n"
                "- Requires operational expertise\n"
                "- Vertical scaling limits"
            ),
            alternatives=(
                "### MySQL\n"
                "**Rejected**: Weaker JSON support.\n\n"
                "### MongoDB\n"
                "**Rejected**: Eventual consistency conflicts with financial requirements."
            ),
            deciders=["backend-team"],
            tags=["database"],
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        assert result.success is True
        assert "quality_feedback" in result.data

        feedback = result.data["quality_feedback"]
        assert (
            feedback["quality_score"] >= 75
        )  # Should be good quality (B grade or higher)
        assert feedback["grade"] in ["A", "B"]
        assert len(feedback["strengths"]) > 0

    def test_vague_adr_gets_specificity_issue(self, temp_adr_dir):
        """Test that vague ADR is flagged for specificity."""
        input_data = CreationInput(
            title="Use a Modern Framework",
            context="We need a framework for the frontend",
            decision="Use a modern framework with good performance",
            consequences="The framework will work well for our needs",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        # Should be blocked due to low quality
        assert result.success is False
        assert result.status.value == "requires_action"
        assert "quality_feedback" in result.data

        feedback = result.data["quality_feedback"]
        assert not feedback["passes_threshold"]

        # Should flag specificity issue
        specificity_issues = [
            issue for issue in feedback["issues"] if issue["category"] == "specificity"
        ]
        assert len(specificity_issues) > 0

        issue = specificity_issues[0]
        assert "generic terms" in issue["issue"].lower()
        assert "suggestion" in issue
        assert "example_fix" in issue

    def test_one_sided_consequences_flagged(self, temp_adr_dir):
        """Test that one-sided consequences (only pros) are flagged."""
        input_data = CreationInput(
            title="Use React for Frontend",
            context="We need a frontend framework for building interactive UIs",
            decision="Use React 18 with TypeScript for all frontend development",
            consequences=(
                "React provides excellent performance and developer experience. "
                "Large ecosystem and strong community support."
            ),  # Only positives, no negatives
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        # Should be blocked due to low quality (one-sided consequences)
        assert result.success is False
        assert result.status.value == "requires_action"
        assert "quality_feedback" in result.data

        feedback = result.data["quality_feedback"]
        assert not feedback["passes_threshold"]

        # Should flag balance issue
        balance_issues = [
            issue for issue in feedback["issues"] if issue["category"] == "balance"
        ]
        assert len(balance_issues) > 0

        issue = balance_issues[0]
        assert "one-sided" in issue["issue"].lower()
        assert issue["severity"] == "high"

    def test_weak_context_flagged(self, temp_adr_dir):
        """Test that insufficient context is flagged."""
        input_data = CreationInput(
            title="Use PostgreSQL",
            context="We need a database",  # Too brief
            decision="Use PostgreSQL as the database",
            consequences="PostgreSQL is reliable and feature-rich",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        # Should be blocked due to low quality (weak context)
        assert result.success is False
        assert result.status.value == "requires_action"
        assert "quality_feedback" in result.data

        feedback = result.data["quality_feedback"]
        assert not feedback["passes_threshold"]

        # Should flag context issue
        context_issues = [
            issue for issue in feedback["issues"] if issue["category"] == "context"
        ]
        assert len(context_issues) > 0

        issue = context_issues[0]
        assert "too brief" in issue["issue"].lower()

    def test_missing_constraints_flagged(self, temp_adr_dir):
        """Test that lack of explicit constraints is flagged."""
        input_data = CreationInput(
            title="Use FastAPI for Backend",
            context="We need a Python web framework for our API service with async support",
            decision="Use FastAPI for the backend API",  # No explicit "don't use" constraints
            consequences=(
                "### Positive\n- Good async support\n\n"
                "### Negative\n- Smaller ecosystem"
            ),
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        # Should be blocked due to low quality (missing constraints)
        assert result.success is False
        assert result.status.value == "requires_action"
        assert "quality_feedback" in result.data

        feedback = result.data["quality_feedback"]
        assert not feedback["passes_threshold"]

        # Should flag policy readiness issue
        policy_issues = [
            issue
            for issue in feedback["issues"]
            if issue["category"] == "policy_readiness"
        ]
        assert len(policy_issues) > 0

        issue = policy_issues[0]
        assert "explicit constraints" in issue["issue"].lower()
        assert "Don't use" in issue["suggestion"]

    def test_missing_alternatives_flagged(self, temp_adr_dir):
        """Test that missing alternatives are flagged."""
        input_data = CreationInput(
            title="Use React for Frontend",
            context="We need a modern frontend framework",
            decision="Use React 18 with TypeScript. Don't use Vue or Angular.",
            consequences=(
                "### Positive\n- Large ecosystem\n\n" "### Negative\n- Learning curve"
            ),
            alternatives=None,  # No alternatives provided
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        # Should be blocked due to low quality (missing alternatives)
        assert result.success is False
        assert result.status.value == "requires_action"
        assert "quality_feedback" in result.data

        feedback = result.data["quality_feedback"]
        assert not feedback["passes_threshold"]

        # Should flag alternatives issue
        alternatives_issues = [
            issue for issue in feedback["issues"] if issue["category"] == "alternatives"
        ]
        assert len(alternatives_issues) > 0

        issue = alternatives_issues[0]
        assert "alternatives" in issue["issue"].lower()
        assert "why_it_matters" in issue
        assert "'disallow' policies" in issue["why_it_matters"]

    def test_quality_recommendations_prioritized(self, temp_adr_dir):
        """Test that recommendations are prioritized by severity."""
        # Create ADR with multiple issues of different severities
        input_data = CreationInput(
            title="Use a framework",  # Vague (medium)
            context="Need framework",  # Too brief (high)
            decision="Use framework X",  # Vague (medium)
            consequences="Good performance",  # One-sided (high)
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        feedback = result.data["quality_feedback"]
        recommendations = feedback["recommendations"]

        # High priority issues should be mentioned first
        assert len(recommendations) > 0
        first_rec = recommendations[0]
        assert "High Priority" in first_rec or "critical" in first_rec.lower()

    def test_quality_next_steps_vary_by_score(self, temp_adr_dir):
        """Test that next steps vary based on quality score."""
        # High quality ADR
        good_input = CreationInput(
            title="Use PostgreSQL 15 for Primary Database",
            context=(
                "We need ACID transactions for financial integrity and support for "
                "complex queries with concurrent writes from multiple services."
            ),
            decision=(
                "Use PostgreSQL 15 as primary database. "
                "Don't use MySQL or MongoDB for production data."
            ),
            consequences=(
                "### Positive\n- ACID compliance\n- Rich features\n\n"
                "### Negative\n- Higher resource usage\n- Ops complexity"
            ),
            alternatives="### MySQL\n**Rejected**: Weaker JSON support",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=good_input)
        feedback = result.data["quality_feedback"]

        # Good quality (B grade) should suggest proceeding or improving
        next_steps = feedback["next_steps"]
        # Score around 75 means "acceptable but could improve" or "high quality"
        assert len(next_steps) > 0
        # Should mention either approval or improvement
        combined_text = " ".join(next_steps).lower()
        assert (
            "approv" in combined_text
            or "review" in combined_text
            or "quality" in combined_text
        )

    def test_low_quality_suggests_revision(self, temp_adr_dir):
        """Test that low quality ADR suggests revision."""
        # Poor quality ADR (but passes minimum validation)
        poor_input = CreationInput(
            title="Use tool X",
            context="We need it for the project",  # Meets 10 char minimum
            decision="Use tool X",  # Meets 5 char minimum
            consequences="It is good",  # Meets 5 char minimum
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=poor_input)
        feedback = result.data["quality_feedback"]

        # Low quality should suggest revision or improvement
        assert feedback["quality_score"] < 70  # Below "good" threshold
        next_steps = feedback["next_steps"]
        combined_text = " ".join(next_steps).lower()
        assert any(
            keyword in combined_text
            for keyword in ["revis", "improv", "address", "strengthen", "quality"]
        )

    def test_quality_feedback_includes_all_fields(self, temp_adr_dir):
        """Test that quality feedback has complete structure."""
        input_data = CreationInput(
            title="Use FastAPI",
            context="Need async API framework",
            decision="Use FastAPI",
            consequences="Good async support",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)

        feedback = result.data["quality_feedback"]

        # Check all required fields present
        assert "quality_score" in feedback
        assert "grade" in feedback
        assert "summary" in feedback
        assert "issues" in feedback
        assert "strengths" in feedback
        assert "recommendations" in feedback
        assert "next_steps" in feedback

        # Score should be integer
        assert isinstance(feedback["quality_score"], int)
        assert 0 <= feedback["quality_score"] <= 100

        # Grade should be A-F
        assert feedback["grade"] in ["A", "B", "C", "D", "F"]

    def test_explicit_constraints_recognized_as_strength(self, temp_adr_dir):
        """Test that explicit constraints are recognized as strength."""
        input_data = CreationInput(
            title="Use FastAPI for Backend",
            context="Need async API framework with automatic documentation for mobile team",
            decision=(
                "Use FastAPI for all new backend services. "
                "Don't use Flask (no native async) or Django (too heavyweight). "
                "All handlers must be async functions."
            ),
            consequences=(
                "### Positive\n- Native async/await\n- Auto OpenAPI docs\n\n"
                "### Negative\n- Smaller ecosystem\n- Team learning curve"
            ),
            alternatives=(
                "### Flask\n**Rejected**: No native async.\n\n"
                "### Django\n**Rejected**: Too heavyweight for API-only."
            ),
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)
        feedback = result.data["quality_feedback"]

        # Should recognize explicit constraints as strength
        assert any(
            "explicit constraints" in strength.lower()
            or "policy extraction" in strength.lower()
            for strength in feedback["strengths"]
        )

    def test_balanced_consequences_recognized_as_strength(self, temp_adr_dir):
        """Test that balanced consequences are recognized."""
        input_data = CreationInput(
            title="Use PostgreSQL",
            context="Need database with ACID compliance and JSON support",
            decision="Use PostgreSQL 15. Don't use MySQL or MongoDB.",
            consequences=(
                "Benefits: ACID compliance for transactions, rich feature set. "
                "Drawbacks: Higher resource usage, operational complexity. "
                "Risk: Performance issues without proper indexing."
            ),
            alternatives="### MySQL\n**Rejected**: Weaker JSON support",
        )

        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(input_data=input_data)
        feedback = result.data["quality_feedback"]

        # Should recognize balance (look for consequence-related strengths)
        # The exact wording depends on the implementation, check that it's high quality
        assert feedback["quality_score"] >= 75  # Good quality
        assert len(feedback["strengths"]) > 0  # Has recognized strengths
        # Check that consequences section was evaluated positively (not flagged for balance issue)
        balance_issues = [
            issue for issue in feedback["issues"] if issue["category"] == "balance"
        ]
        assert len(balance_issues) == 0  # No balance issues = balanced recognized
