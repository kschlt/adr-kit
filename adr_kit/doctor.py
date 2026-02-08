"""ADR Kit health check and diagnostics module.

Provides comprehensive health checking for ADR setup including:
- Schema file availability
- ADR directory structure
- Index health
- Contract status
- Configuration issues
"""

from dataclasses import dataclass
from pathlib import Path

from .contract.builder import ConstraintsContractBuilder
from .core.model import ADRStatus
from .core.parse import find_adr_files, parse_adr_file
from .core.validate import ADRValidator


@dataclass
class HealthCheckIssue:
    """A single health check issue or observation."""

    level: str  # 'ok', 'warning', 'error'
    category: str  # Component being checked
    message: str
    recommendation: str | None = None


@dataclass
class HealthCheckResult:
    """Result of health check operation."""

    success: bool
    issues: list[HealthCheckIssue]
    summary: dict[str, int | str]

    def get_recommendations(self) -> list[str]:
        """Get all recommendations from issues."""
        return [
            issue.recommendation
            for issue in self.issues
            if issue.recommendation is not None
        ]


class HealthChecker:
    """Health checker for ADR Kit setup and configuration."""

    def __init__(self, adr_dir: Path = Path("docs/adr")):
        self.adr_dir = Path(adr_dir)

    def check_all(self) -> HealthCheckResult:
        """Run all health checks."""
        issues: list[HealthCheckIssue] = []

        # 1. Check schema file
        issues.append(self._check_schema())

        # 2. Check ADR directory
        issues.append(self._check_adr_directory())

        # 3. Check ADRs
        adr_check_results = self._check_adrs()
        issues.extend(adr_check_results)

        # 4. Check index
        issues.append(self._check_index())

        # 5. Check contract
        issues.append(self._check_contract())

        # Determine overall success
        has_errors = any(issue.level == "error" for issue in issues)
        success = not has_errors

        # Build summary
        summary = self._build_summary(issues)

        return HealthCheckResult(success=success, issues=issues, summary=summary)

    def _check_schema(self) -> HealthCheckIssue:
        """Check if schema file is available."""
        try:
            validator = ADRValidator()
            if validator.schema_path and validator.schema_path.exists():
                return HealthCheckIssue(
                    level="ok",
                    category="Schema file",
                    message="Present",
                )
            else:
                return HealthCheckIssue(
                    level="warning",
                    category="Schema file",
                    message="Missing (degraded mode)",
                    recommendation="Reinstall ADR Kit to restore schema file",
                )
        except Exception:
            return HealthCheckIssue(
                level="warning",
                category="Schema file",
                message="Missing (degraded mode)",
                recommendation="Reinstall ADR Kit to restore schema file",
            )

    def _check_adr_directory(self) -> HealthCheckIssue:
        """Check if ADR directory exists."""
        if self.adr_dir.exists() and self.adr_dir.is_dir():
            return HealthCheckIssue(
                level="ok",
                category="ADR directory",
                message=str(self.adr_dir),
            )
        else:
            return HealthCheckIssue(
                level="error",
                category="ADR directory",
                message=f"{self.adr_dir} not found",
                recommendation="Run 'adr-kit init' to initialize ADR structure",
            )

    def _check_adrs(self) -> list[HealthCheckIssue]:
        """Check ADRs in directory."""
        issues: list[HealthCheckIssue] = []

        if not self.adr_dir.exists():
            # Already reported by _check_adr_directory
            return issues

        adr_files = find_adr_files(self.adr_dir)

        if not adr_files:
            issues.append(
                HealthCheckIssue(
                    level="warning",
                    category="Total ADRs",
                    message="0 (no ADRs found)",
                    recommendation="Create your first ADR with MCP tool: adr_create()",
                )
            )
            return issues

        # Count ADRs by status
        status_counts: dict[ADRStatus, int] = {}
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr:
                    status_counts[adr.front_matter.status] = (
                        status_counts.get(adr.front_matter.status, 0) + 1
                    )
            except Exception:
                continue

        # Report total
        total_adrs = len(adr_files)
        issues.append(
            HealthCheckIssue(
                level="ok",
                category="Total ADRs",
                message=str(total_adrs),
            )
        )

        # Report status distribution
        if status_counts:
            status_str = ", ".join(
                f"{status.value if hasattr(status, 'value') else status}({count})"
                for status, count in status_counts.items()
            )
            issues.append(
                HealthCheckIssue(
                    level="ok",
                    category="Status distribution",
                    message=status_str,
                )
            )
        else:
            issues.append(
                HealthCheckIssue(
                    level="warning",
                    category="Status distribution",
                    message="Unable to parse ADR files",
                    recommendation="Check ADR file format with 'adr-kit validate'",
                )
            )

        return issues

    def _check_index(self) -> HealthCheckIssue:
        """Check if index file exists and is up to date."""
        index_path = self.adr_dir / "adr-index.json"

        if not index_path.exists():
            return HealthCheckIssue(
                level="warning",
                category="Index",
                message="Missing",
                recommendation="Run 'adr-kit index' to generate JSON index",
            )

        # Check if index is fresh (basic check)
        import json

        try:
            with open(index_path) as f:
                index_data = json.load(f)

            if "metadata" in index_data and "generated_at" in index_data["metadata"]:
                return HealthCheckIssue(
                    level="ok",
                    category="Index",
                    message="Up to date",
                )
            else:
                return HealthCheckIssue(
                    level="warning",
                    category="Index",
                    message="Outdated format",
                    recommendation="Run 'adr-kit index' to regenerate",
                )
        except Exception:
            return HealthCheckIssue(
                level="warning",
                category="Index",
                message="Corrupted",
                recommendation="Run 'adr-kit index' to regenerate",
            )

    def _check_contract(self) -> HealthCheckIssue:
        """Check contract status."""
        try:
            builder = ConstraintsContractBuilder(adr_dir=self.adr_dir)
            summary = builder.get_contract_summary()

            if summary["success"] and summary["total_constraints"] > 0:
                return HealthCheckIssue(
                    level="ok",
                    category="Contract",
                    message=f"{summary['total_constraints']} constraints from {len(summary['source_adrs'])} ADRs",
                )
            elif summary["success"] and summary["total_constraints"] == 0:
                return HealthCheckIssue(
                    level="warning",
                    category="Contract",
                    message="No constraints (no accepted ADRs with policies)",
                    recommendation="Add policy blocks to accepted ADRs (see guide/POLICY-FORMAT.md)",
                )
            else:
                return HealthCheckIssue(
                    level="warning",
                    category="Contract",
                    message="Not built",
                    recommendation="Run 'adr-kit contract-build' to build constraint contract",
                )
        except Exception as e:
            return HealthCheckIssue(
                level="warning",
                category="Contract",
                message=f"Error: {str(e)[:50]}",
                recommendation="Run 'adr-kit contract-build' to rebuild contract",
            )

    def _build_summary(self, issues: list[HealthCheckIssue]) -> dict[str, int | str]:
        """Build summary statistics from issues."""
        ok_count = sum(1 for issue in issues if issue.level == "ok")
        warning_count = sum(1 for issue in issues if issue.level == "warning")
        error_count = sum(1 for issue in issues if issue.level == "error")

        # Extract key metrics
        total_adrs = "0"
        for issue in issues:
            if issue.category == "Total ADRs":
                total_adrs = issue.message.split()[0]  # Extract number before " ("

        return {
            "ok": ok_count,
            "warnings": warning_count,
            "errors": error_count,
            "total_checks": len(issues),
            "total_adrs": total_adrs,
        }
