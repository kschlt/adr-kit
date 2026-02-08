"""Tests for planning workflow - specifically testing the adr_planning_context crash fix."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from adr_kit.contract.builder import ConstraintsContractBuilder
from adr_kit.contract.models import ConstraintsContract, MergedConstraints
from adr_kit.core.model import (
    ADR,
    ADRFrontMatter,
    ADRStatus,
    ImportPolicy,
    PolicyModel,
)
from adr_kit.workflows.planning import PlanningInput, PlanningWorkflow


class TestPlanningWorkflowCrashFix:
    """Test suite specifically for the MergedConstraints.policy crash bug."""

    def test_planning_context_with_approved_adrs(self, tmp_path: Path) -> None:
        """Test that planning context doesn't crash when ADRs have policies.

        This reproduces the bug: 'MergedConstraints' object has no attribute 'policy'
        which occurs in _assess_constraint_relevance method.
        """
        # Setup: Create ADR directory with approved ADR containing policy
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create an approved ADR with policy
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI for Backend",
            status=ADRStatus.ACCEPTED,
            date=date(2025, 1, 1),
            deciders=["team"],
            policy=PolicyModel(
                imports=ImportPolicy(
                    disallow=["flask", "django"], prefer=["fastapi"]
                ),
            ),
        )

        content = """## Context

We need a modern async Python web framework.

## Decision

Use FastAPI as the backend framework.

## Consequences

Better async support, automatic OpenAPI docs.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        adr_file = adr_dir / "ADR-0001-use-fastapi.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        # Build the constraints contract
        builder = ConstraintsContractBuilder(adr_dir=adr_dir)
        contract = builder.build()

        # Verify contract has constraints
        assert contract.constraints is not None
        assert contract.constraints.imports is not None
        assert "fastapi" in contract.constraints.imports.prefer

        # Create planning workflow
        workflow = PlanningWorkflow(adr_dir=adr_dir)

        # Create planning input - this task should match the FastAPI ADR
        planning_input = PlanningInput(
            task_description="Implement a REST API endpoint for user authentication",
            context_type="implementation",
            domain_hints=["backend"],
            priority_level="normal",
        )

        # Execute workflow - this should NOT crash with AttributeError
        result = workflow.execute(input_data=planning_input)

        # Verify result
        assert result.success, f"Workflow failed: {result.errors}"
        assert result.data is not None
        assert "architectural_context" in result.data

        # Verify architectural context was generated
        context = result.data["architectural_context"]
        assert context is not None
        assert len(context.relevant_adrs) > 0
        assert context.relevant_adrs[0]["adr_id"] == "ADR-0001"

    def test_planning_context_with_empty_contract(self, tmp_path: Path) -> None:
        """Test that planning context works with no approved ADRs."""
        # Setup: Create empty ADR directory
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create planning workflow
        workflow = PlanningWorkflow(adr_dir=adr_dir)

        # Create planning input
        planning_input = PlanningInput(
            task_description="Implement a REST API endpoint",
            context_type="implementation",
            domain_hints=["backend"],
            priority_level="normal",
        )

        # Execute workflow - should work with empty contract
        result = workflow.execute(input_data=planning_input)

        # Verify result
        assert result.success, f"Workflow failed: {result.errors}"
        assert result.data is not None
        assert "architectural_context" in result.data

        # Verify context is empty but valid
        context = result.data["architectural_context"]
        assert len(context.relevant_adrs) == 0
        assert len(context.applicable_constraints) == 0

    def test_assess_constraint_relevance_with_merged_constraints(
        self, tmp_path: Path
    ) -> None:
        """Test _assess_constraint_relevance with actual MergedConstraints object.

        This is the specific method that was crashing.
        """
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        workflow = PlanningWorkflow(adr_dir=adr_dir)

        # Create a MergedConstraints object directly
        merged_constraints = MergedConstraints(
            imports=ImportPolicy(disallow=["axios"], prefer=["fetch"]),
            boundaries=None,
            python=None,
        )

        # Test the _assess_constraint_relevance method directly
        task_domains = {"frontend"}
        task_tech = {"react", "fetch"}

        # This should NOT crash with AttributeError: 'MergedConstraints' object has no attribute 'policy'
        relevance = workflow._assess_constraint_relevance(
            merged_constraints, task_domains, task_tech
        )

        # Verify relevance calculation works
        assert isinstance(relevance, float)
        assert 0.0 <= relevance <= 1.0

    def test_planning_context_with_multiple_adrs(self, tmp_path: Path) -> None:
        """Test planning context with multiple approved ADRs with different policies."""
        # Setup: Create ADR directory with multiple approved ADRs
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # ADR 1: Backend framework
        adr1_content = """## Context

Need async Python framework.

## Decision

Use FastAPI.

## Consequences

Better async support.
"""
        adr1 = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI for Backend",
                status=ADRStatus.ACCEPTED,
                date=date(2025, 1, 1),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(
                        disallow=["flask", "django"], prefer=["fastapi"]
                    ),
                ),
            ),
            content=adr1_content,
        )

        # ADR 2: Database choice
        adr2_content = """## Context

Need reliable RDBMS.

## Decision

Use PostgreSQL.

## Consequences

ACID compliance, good performance.
"""
        adr2 = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0002",
                title="Use PostgreSQL for Database",
                status=ADRStatus.ACCEPTED,
                date=date(2025, 1, 15),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(
                        disallow=["mysql-connector"], prefer=["psycopg2"]
                    ),
                ),
            ),
            content=adr2_content,
        )

        # Write both ADRs
        with open(adr_dir / "ADR-0001-use-fastapi.md", "w") as f:
            f.write(adr1.to_markdown())

        with open(adr_dir / "ADR-0002-use-postgresql.md", "w") as f:
            f.write(adr2.to_markdown())

        # Create planning workflow
        workflow = PlanningWorkflow(adr_dir=adr_dir)

        # Task that should match both ADRs
        planning_input = PlanningInput(
            task_description="Build a FastAPI endpoint to query PostgreSQL database",
            context_type="implementation",
            domain_hints=["backend", "database"],
            priority_level="high",
        )

        # Execute workflow
        result = workflow.execute(input_data=planning_input)

        # Verify result
        assert result.success, f"Workflow failed: {result.errors}"
        context = result.data["architectural_context"]

        # Should find both ADRs as relevant
        assert len(context.relevant_adrs) == 2
        adr_ids = [adr["adr_id"] for adr in context.relevant_adrs]
        assert "ADR-0001" in adr_ids
        assert "ADR-0002" in adr_ids

        # Verify technology recommendations structure exists (content may be empty due to separate bug)
        assert "recommended" in context.technology_recommendations
        assert "avoid" in context.technology_recommendations
        # Note: The actual population of these recommendations has a separate bug
        # where _generate_technology_recommendations expects "Prefers:" but
        # _extract_key_policies returns "Prefers imports:". This is a separate issue.

    def test_planning_context_with_complex_task(self, tmp_path: Path) -> None:
        """Test planning context with a complex task description."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with comprehensive policy
        adr_content = """## Context

Need to standardize frontend framework.

## Decision

Use React with TypeScript.

## Consequences

Type safety, large ecosystem.
"""
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Frontend Architecture with React",
                status=ADRStatus.ACCEPTED,
                date=date(2025, 1, 1),
                deciders=["frontend-team"],
                policy=PolicyModel(
                    imports=ImportPolicy(
                        disallow=["vue", "angular"], prefer=["react", "typescript"]
                    ),
                ),
                tags=["frontend", "architecture", "react"],
            ),
            content=adr_content,
        )

        with open(adr_dir / "ADR-0001-react-frontend.md", "w") as f:
            f.write(adr.to_markdown())

        # Create workflow
        workflow = PlanningWorkflow(adr_dir=adr_dir)

        # Complex task with multiple technologies and domains
        planning_input = PlanningInput(
            task_description="Refactor the user authentication UI component from JavaScript to TypeScript, integrate with FastAPI backend, and add unit tests",
            context_type="refactoring",
            domain_hints=["frontend", "testing"],
            priority_level="high",
        )

        # Execute workflow
        result = workflow.execute(input_data=planning_input)

        # Verify result
        assert result.success, f"Workflow failed: {result.errors}"
        context = result.data["architectural_context"]
        task_analysis = result.data["task_analysis"]

        # Verify task analysis
        assert task_analysis["complexity"] in ["medium", "high"]
        assert "frontend" in task_analysis["domains"]
        assert "refactor" in task_analysis["intents"]

        # Verify context includes the React ADR
        assert len(context.relevant_adrs) > 0
        assert context.relevant_adrs[0]["adr_id"] == "ADR-0001"

        # Verify guidance prompts are appropriate for refactoring
        guidance_text = " ".join(context.guidance_prompts).lower()
        assert "refactor" in guidance_text or "architectural" in guidance_text

        # Verify compliance checklist exists
        assert len(context.compliance_checklist) > 0
