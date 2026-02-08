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
    command: str | None = None  # Exact command to fix the issue
    severity: int = 0  # 0=info, 1=low, 2=medium, 3=high (for prioritization)


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

    def get_actionable_items(self) -> list[tuple[str, str | None, int]]:
        """Get recommendations with commands, sorted by severity.

        Returns:
            List of (recommendation, command, severity) tuples
        """
        items = [
            (issue.recommendation, issue.command, issue.severity)
            for issue in self.issues
            if issue.recommendation is not None
        ]
        # Sort by severity (high to low), then alphabetically
        return sorted(items, key=lambda x: (-x[2], x[0]))


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

        # 4. Check for duplicate IDs (only if directory exists)
        if self.adr_dir.exists():
            duplicate_issue = self._check_duplicate_ids()
            if duplicate_issue:
                issues.append(duplicate_issue)

        # 5. Check for parsing errors
        if self.adr_dir.exists():
            parse_issues = self._check_parsing_errors()
            issues.extend(parse_issues)

        # 6. Check index
        issues.append(self._check_index())

        # 7. Check contract
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
                    severity=0,
                )
            else:
                return HealthCheckIssue(
                    level="warning",
                    category="Schema file",
                    message="Missing (degraded mode)",
                    recommendation="Reinstall ADR Kit to restore schema validation",
                    command="pip install --upgrade --force-reinstall adr-kit",
                    severity=2,
                )
        except Exception:
            return HealthCheckIssue(
                level="warning",
                category="Schema file",
                message="Missing (degraded mode)",
                recommendation="Reinstall ADR Kit to restore schema validation",
                command="pip install --upgrade --force-reinstall adr-kit",
                severity=2,
            )

    def _check_adr_directory(self) -> HealthCheckIssue:
        """Check if ADR directory exists."""
        if self.adr_dir.exists() and self.adr_dir.is_dir():
            return HealthCheckIssue(
                level="ok",
                category="ADR directory",
                message=str(self.adr_dir),
                severity=0,
            )
        else:
            return HealthCheckIssue(
                level="error",
                category="ADR directory",
                message=f"{self.adr_dir} not found",
                recommendation=f"Initialize ADR Kit in your project (creates {self.adr_dir})",
                command=f"adr-kit init --adr-dir {self.adr_dir}",
                severity=3,
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
                    recommendation="Create your first ADR to document an architectural decision",
                    command="# Via MCP (Claude Code, Cursor):\nadr_create(title='Use FastAPI for backend', context='...', decision='...', consequences='...')\n\n# Or via CLI:\nadr-kit create 'Use FastAPI for backend'",
                    severity=1,
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
                severity=0,
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
                    severity=0,
                )
            )

            # Add recommendations for workflow improvements
            accepted_count = status_counts.get(ADRStatus.ACCEPTED, 0)
            proposed_count = status_counts.get(ADRStatus.PROPOSED, 0)

            if proposed_count > 0 and accepted_count == 0:
                issues.append(
                    HealthCheckIssue(
                        level="warning",
                        category="Workflow",
                        message=f"{proposed_count} proposed ADR(s) pending approval",
                        recommendation="Review and approve proposed ADRs to activate their policies",
                        command="# Via MCP:\nadr_approve(adr_id='ADR-0001')\n\n# Or via CLI:\nadr-kit approve ADR-0001",
                        severity=1,
                    )
                )
        else:
            issues.append(
                HealthCheckIssue(
                    level="warning",
                    category="Status distribution",
                    message="Unable to parse ADR files",
                    recommendation="Validate ADR file format to identify parsing errors",
                    command=f"adr-kit validate --adr-dir {self.adr_dir}",
                    severity=2,
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
                recommendation="Generate JSON index for faster ADR lookups and integrations",
                command=f"adr-kit index --adr-dir {self.adr_dir}",
                severity=1,
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
                    severity=0,
                )
            else:
                return HealthCheckIssue(
                    level="warning",
                    category="Index",
                    message="Outdated format",
                    recommendation="Regenerate index to use latest format",
                    command=f"adr-kit index --adr-dir {self.adr_dir}",
                    severity=1,
                )
        except Exception:
            return HealthCheckIssue(
                level="warning",
                category="Index",
                message="Corrupted",
                recommendation="Rebuild corrupted index file",
                command=f"adr-kit index --adr-dir {self.adr_dir}",
                severity=2,
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
                    severity=0,
                )
            elif summary["success"] and summary["total_constraints"] == 0:
                return HealthCheckIssue(
                    level="warning",
                    category="Contract",
                    message="No constraints (no accepted ADRs with policies)",
                    recommendation="Add policy blocks to accepted ADRs to enable constraint enforcement",
                    command="# See guide/POLICY-FORMAT.md for policy block format\n# Add to ADR frontmatter:\npolicy:\n  imports:\n    disallow: [flask, django]\n    prefer: [fastapi]\n  python:\n    disallow_imports: [flask]",
                    severity=1,
                )
            else:
                return HealthCheckIssue(
                    level="warning",
                    category="Contract",
                    message="Not built",
                    recommendation="Build constraints contract to enable preflight checks",
                    command=f"adr-kit contract-build --adr-dir {self.adr_dir}",
                    severity=1,
                )
        except Exception as e:
            return HealthCheckIssue(
                level="warning",
                category="Contract",
                message=f"Error: {str(e)[:50]}",
                recommendation="Rebuild constraints contract to resolve errors",
                command=f"adr-kit contract-build --adr-dir {self.adr_dir}",
                severity=2,
            )

    def _check_duplicate_ids(self) -> HealthCheckIssue | None:
        """Check for duplicate ADR IDs."""
        adr_files = find_adr_files(self.adr_dir)
        if not adr_files:
            return None

        seen_ids: dict[str, list[Path]] = {}
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.id:
                    adr_id = adr.front_matter.id
                    if adr_id not in seen_ids:
                        seen_ids[adr_id] = []
                    seen_ids[adr_id].append(file_path)
            except Exception:
                continue

        # Find duplicates
        duplicates = {id: files for id, files in seen_ids.items() if len(files) > 1}
        if duplicates:
            dup_str = ", ".join(
                f"{id}({len(files)} files)" for id, files in duplicates.items()
            )
            return HealthCheckIssue(
                level="error",
                category="Duplicate IDs",
                message=f"Found duplicate ADR IDs: {dup_str}",
                recommendation="Each ADR must have a unique ID. Rename duplicate files or update their frontmatter IDs",
                command=f"# List duplicates:\nfind {self.adr_dir} -name 'ADR-*.md' | sort\n\n# Fix by renaming files or updating 'id:' in frontmatter",
                severity=3,
            )
        return None

    def _check_parsing_errors(self) -> list[HealthCheckIssue]:
        """Check for ADR files with parsing errors."""
        issues: list[HealthCheckIssue] = []
        adr_files = find_adr_files(self.adr_dir)

        if not adr_files:
            return issues

        parse_errors: list[tuple[Path, str]] = []
        for file_path in adr_files:
            try:
                parse_adr_file(file_path, strict=True)
            except Exception as e:
                error_msg = str(e)[:100]  # Truncate long errors
                parse_errors.append((file_path, error_msg))

        if parse_errors:
            # Report up to 3 parsing errors
            for file_path, error_msg in parse_errors[:3]:
                filename = file_path.name
                issues.append(
                    HealthCheckIssue(
                        level="error",
                        category="Parse error",
                        message=f"{filename}: {error_msg}",
                        recommendation=f"Fix YAML frontmatter or markdown formatting in {filename}",
                        command=f"# Inspect the file:\ncat {file_path}\n\n# Common fixes:\n# - Check YAML frontmatter has --- delimiters\n# - Verify all required fields (id, title, status, date)\n# - Ensure proper YAML syntax (no tabs, correct indentation)",
                        severity=3,
                    )
                )

            if len(parse_errors) > 3:
                issues.append(
                    HealthCheckIssue(
                        level="warning",
                        category="Parse errors",
                        message=f"... and {len(parse_errors) - 3} more files with errors",
                        recommendation="Run full validation to see all parsing errors",
                        command=f"adr-kit validate --adr-dir {self.adr_dir}",
                        severity=2,
                    )
                )

        return issues

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
