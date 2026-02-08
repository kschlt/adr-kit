"""Tests for single decision validation integration with approval workflow."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus
from adr_kit.workflows.approval import ApprovalInput, ApprovalWorkflow


class TestApprovalSingleDecisionIntegration:
    """Test suite for single decision validation in approval workflow."""

    def test_approve_single_decision_adr_succeeds(self, tmp_path: Path) -> None:
        """Test that ADRs with single decision can be approved."""
        # Setup: Create ADR directory with a good single-decision ADR
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with single decision
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI for Backend",
            status=ADRStatus.PROPOSED,
            date=date(2025, 1, 1),
            deciders=["team"],
        )

        content = """## Context

We need a modern Python web framework for our API backend.

## Decision

Use FastAPI as our backend framework.

## Consequences

Better async support and automatic OpenAPI documentation.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        adr_file = adr_dir / "ADR-0001-use-fastapi.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        # Execute approval workflow
        workflow = ApprovalWorkflow(adr_dir=adr_dir)
        approval_input = ApprovalInput(adr_id="ADR-0001", digest_check=False)

        result = workflow.execute(input_data=approval_input)

        # Verify approval succeeded
        assert result.success
        assert "approval_result" in result.data
        assert result.data["approval_result"].new_status == "accepted"

    def test_approve_multiple_decisions_adr_blocked(self, tmp_path: Path) -> None:
        """Test that ADRs with multiple decisions are blocked from approval."""
        # Setup: Create ADR directory with a multi-decision ADR
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with multiple decisions (high severity warning)
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI and Deploy to AWS",  # ❌ Two decisions
            status=ADRStatus.PROPOSED,
            date=date(2025, 1, 1),
            deciders=["team"],
        )

        content = """## Context

Need backend and deployment.

## Decision

Use FastAPI for the backend and deploy to AWS.

## Consequences

Good performance and scalability.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        adr_file = adr_dir / "ADR-0001-backend-and-deployment.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        # Execute approval workflow
        workflow = ApprovalWorkflow(adr_dir=adr_dir)
        approval_input = ApprovalInput(adr_id="ADR-0001", digest_check=False)

        result = workflow.execute(input_data=approval_input)

        # Verify approval was blocked
        assert not result.success
        assert len(result.errors) > 0

        # Check that error message mentions single decision principle
        error_message = " ".join(result.errors).lower()
        assert "single decision" in error_message or "multiple" in error_message

    def test_approve_multiple_decisions_with_force_succeeds(self, tmp_path: Path) -> None:
        """Test that force_approve bypasses single decision validation."""
        # Setup: Create ADR directory with a multi-decision ADR
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with multiple decisions
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI and PostgreSQL",  # Different domains
            status=ADRStatus.PROPOSED,
            date=date(2025, 1, 1),
            deciders=["team"],
        )

        content = """## Context

Need stack.

## Decision

Use FastAPI and PostgreSQL.

## Consequences

Good stack.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        adr_file = adr_dir / "ADR-0001-tech-stack.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        # Execute approval workflow with force
        workflow = ApprovalWorkflow(adr_dir=adr_dir)
        approval_input = ApprovalInput(
            adr_id="ADR-0001",
            digest_check=False,
            force_approve=True  # Override validation
        )

        result = workflow.execute(input_data=approval_input)

        # Verify approval succeeded despite multiple decisions
        assert result.success
        assert "approval_result" in result.data
        assert result.data["approval_result"].new_status == "accepted"

    def test_approve_related_technologies_allowed(self, tmp_path: Path) -> None:
        """Test that related technologies in same domain are allowed."""
        # Setup: Create ADR directory
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with related technologies (not multiple decisions)
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use React with TypeScript",  # ✅ Related, same domain
            status=ADRStatus.PROPOSED,
            date=date(2025, 1, 1),
            deciders=["team"],
        )

        content = """## Context

Need type-safe frontend.

## Decision

Use React with TypeScript for type safety.

## Consequences

Better developer experience with type checking.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        adr_file = adr_dir / "ADR-0001-react-typescript.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        # Execute approval workflow
        workflow = ApprovalWorkflow(adr_dir=adr_dir)
        approval_input = ApprovalInput(adr_id="ADR-0001", digest_check=False)

        result = workflow.execute(input_data=approval_input)

        # Verify approval succeeded (related techs are OK)
        assert result.success
        assert "approval_result" in result.data
        assert result.data["approval_result"].new_status == "accepted"
