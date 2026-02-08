"""Tests for ADR Kit doctor (health check) functionality."""

from datetime import date
from pathlib import Path

import pytest

from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus
from adr_kit.doctor import HealthChecker


class TestHealthChecker:
    """Test suite for health checker."""

    def test_check_all_empty_directory(self, tmp_path: Path) -> None:
        """Test health check on empty/missing ADR directory."""
        adr_dir = tmp_path / "docs/adr"
        # Don't create directory

        checker = HealthChecker(adr_dir=adr_dir)
        result = checker.check_all()

        # Should have error about missing directory
        assert not result.success
        assert any(issue.level == "error" for issue in result.issues)

        # Should have ADR directory issue
        dir_issues = [
            issue for issue in result.issues if issue.category == "ADR directory"
        ]
        assert len(dir_issues) == 1
        assert dir_issues[0].level == "error"

    def test_check_all_empty_but_initialized(self, tmp_path: Path) -> None:
        """Test health check on initialized but empty ADR directory."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        checker = HealthChecker(adr_dir=adr_dir)
        result = checker.check_all()

        # Should succeed but have warnings
        assert result.success  # No errors, just warnings

        # Should warn about no ADRs
        adr_issues = [issue for issue in result.issues if issue.category == "Total ADRs"]
        assert len(adr_issues) == 1
        assert adr_issues[0].level == "warning"
        assert "0" in adr_issues[0].message

    def test_check_all_with_adrs(self, tmp_path: Path) -> None:
        """Test health check with some ADRs present."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create a few ADRs
        for i in range(3):
            front_matter = ADRFrontMatter(
                id=f"ADR-{i+1:04d}",
                title=f"Test Decision {i+1}",
                status=ADRStatus.ACCEPTED if i < 2 else ADRStatus.PROPOSED,
                date=date(2025, 1, i + 1),
                deciders=["team"],
            )

            content = f"""## Context

Test context {i+1}.

## Decision

Use technology {i+1}.

## Consequences

Good things happen.
"""

            adr = ADR(front_matter=front_matter, content=content)
            adr_file = adr_dir / f"ADR-{i+1:04d}-test-{i+1}.md"
            with open(adr_file, "w") as f:
                f.write(adr.to_markdown())

        checker = HealthChecker(adr_dir=adr_dir)
        result = checker.check_all()

        # Should succeed
        assert result.success

        # Should report correct number of ADRs
        adr_issues = [issue for issue in result.issues if issue.category == "Total ADRs"]
        assert len(adr_issues) == 1
        assert adr_issues[0].level == "ok"
        assert "3" in adr_issues[0].message

        # Should report status distribution
        status_issues = [
            issue for issue in result.issues if issue.category == "Status distribution"
        ]
        assert len(status_issues) == 1
        assert "accepted(2)" in status_issues[0].message
        assert "proposed(1)" in status_issues[0].message

    def test_check_schema_availability(self, tmp_path: Path) -> None:
        """Test schema file check."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        checker = HealthChecker(adr_dir=adr_dir)
        schema_issue = checker._check_schema()

        # Schema check should either be ok or warning (not error)
        assert schema_issue.level in ["ok", "warning"]
        assert schema_issue.category == "Schema file"

    def test_check_index_missing(self, tmp_path: Path) -> None:
        """Test index check when index is missing."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        checker = HealthChecker(adr_dir=adr_dir)
        index_issue = checker._check_index()

        assert index_issue.level == "warning"
        assert index_issue.category == "Index"
        assert "Missing" in index_issue.message
        assert index_issue.recommendation is not None

    def test_check_index_present(self, tmp_path: Path) -> None:
        """Test index check when index exists."""
        import json

        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create a valid index file
        index_path = adr_dir / "adr-index.json"
        index_data = {
            "metadata": {"generated_at": "2025-01-01T00:00:00", "total_adrs": 0},
            "adrs": [],
        }
        with open(index_path, "w") as f:
            json.dump(index_data, f)

        checker = HealthChecker(adr_dir=adr_dir)
        index_issue = checker._check_index()

        assert index_issue.level == "ok"
        assert index_issue.category == "Index"

    def test_check_contract_no_accepted_adrs(self, tmp_path: Path) -> None:
        """Test contract check when no accepted ADRs exist."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create a proposed ADR (not accepted)
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Test",
            status=ADRStatus.PROPOSED,
            date=date(2025, 1, 1),
            deciders=["team"],
        )

        adr = ADR(front_matter=front_matter, content="## Context\n\nTest.")
        adr_file = adr_dir / "ADR-0001-test.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        checker = HealthChecker(adr_dir=adr_dir)
        contract_issue = checker._check_contract()

        # Should warn about no constraints
        assert contract_issue.level == "warning"
        assert contract_issue.category == "Contract"

    def test_recommendations_extraction(self, tmp_path: Path) -> None:
        """Test that recommendations are extracted correctly."""
        adr_dir = tmp_path / "docs/adr"
        # Don't create directory to trigger recommendations

        checker = HealthChecker(adr_dir=adr_dir)
        result = checker.check_all()

        recommendations = result.get_recommendations()

        # Should have at least one recommendation
        assert len(recommendations) > 0
        assert all(isinstance(rec, str) for rec in recommendations)

    def test_summary_statistics(self, tmp_path: Path) -> None:
        """Test that summary statistics are generated correctly."""
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        checker = HealthChecker(adr_dir=adr_dir)
        result = checker.check_all()

        summary = result.summary

        # Should have expected keys
        assert "ok" in summary
        assert "warnings" in summary
        assert "errors" in summary
        assert "total_checks" in summary

        # Counts should be non-negative
        assert summary["ok"] >= 0
        assert summary["warnings"] >= 0
        assert summary["errors"] >= 0
        assert summary["total_checks"] > 0

        # Total checks should equal sum of ok + warnings + errors
        assert summary["total_checks"] == (
            summary["ok"] + summary["warnings"] + summary["errors"]
        )
