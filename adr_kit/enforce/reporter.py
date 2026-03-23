"""AI-readable enforcement report generation.

Converts ValidationResult into structured JSON that agents and CI pipelines
can consume for automated violation handling and self-correction.

Output schema:
  - schema_version: report format version (currently "1.0")
  - level: enforcement level that was run
  - passed: whether the check passed (no error-severity violations)
  - summary: counts of files, checks, errors, warnings
  - violations: list of structured violations with fix suggestions
  - errors: any errors encountered during validation
"""

from datetime import datetime, timezone

from pydantic import BaseModel

from .validator import ValidationResult


class ViolationEntry(BaseModel):
    """Single violation in an enforcement report."""

    file: str
    line: int | None = None
    adr_id: str
    adr_title: str | None = None
    message: str
    severity: str
    level: str
    fix_suggestion: str | None = None


class ReportSummary(BaseModel):
    """Aggregate counts for an enforcement run."""

    files_checked: int
    checks_run: int
    error_count: int
    warning_count: int


class EnforcementReport(BaseModel):
    """AI-readable enforcement report — JSON output for agents and CI."""

    schema_version: str = "1.0"
    level: str
    timestamp: str
    passed: bool
    summary: ReportSummary
    violations: list[ViolationEntry]
    errors: list[str]


def build_report(result: ValidationResult) -> EnforcementReport:
    """Convert a ValidationResult to a serializable EnforcementReport.

    Args:
        result: ValidationResult from StagedValidator.validate().

    Returns:
        EnforcementReport ready for JSON serialization.
    """
    violations = [
        ViolationEntry(
            file=v.file,
            line=v.line,
            adr_id=v.adr_id,
            adr_title=v.adr_title,
            message=v.message,
            severity=v.severity,
            level=v.level.value,
            fix_suggestion=v.fix_suggestion,
        )
        for v in result.violations
    ]

    return EnforcementReport(
        level=result.level.value,
        timestamp=datetime.now(timezone.utc).isoformat(),
        passed=result.passed,
        summary=ReportSummary(
            files_checked=result.files_checked,
            checks_run=result.checks_run,
            error_count=result.error_count,
            warning_count=result.warning_count,
        ),
        violations=violations,
        errors=result.errors,
    )
