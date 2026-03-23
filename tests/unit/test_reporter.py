"""Unit tests for AI-readable enforcement reporter."""

import json

from adr_kit.enforce.reporter import EnforcementReport, build_report
from adr_kit.enforce.stages import EnforcementLevel
from adr_kit.enforce.validator import ValidationResult, Violation

# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_empty_result_produces_passing_report(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=10,
            checks_run=3,
        )
        report = build_report(result)

        assert report.passed is True
        assert report.level == "ci"
        assert report.summary.files_checked == 10
        assert report.summary.checks_run == 3
        assert report.summary.error_count == 0
        assert report.summary.warning_count == 0
        assert report.violations == []
        assert report.errors == []

    def test_error_violations_set_passed_false(self):
        result = ValidationResult(
            level=EnforcementLevel.COMMIT,
            files_checked=5,
            checks_run=2,
            violations=[
                Violation(
                    file="src/app.py",
                    adr_id="ADR-0001",
                    message="Flask import disallowed",
                    level=EnforcementLevel.COMMIT,
                    severity="error",
                    line=3,
                    adr_title="Use FastAPI",
                    fix_suggestion="Replace flask with fastapi",
                ),
            ],
        )
        report = build_report(result)

        assert report.passed is False
        assert report.summary.error_count == 1
        assert report.summary.warning_count == 0

    def test_warning_only_result(self):
        result = ValidationResult(
            level=EnforcementLevel.PUSH,
            files_checked=8,
            checks_run=4,
            violations=[
                Violation(
                    file="src/views.py",
                    adr_id="ADR-0002",
                    message="Consider refactoring",
                    level=EnforcementLevel.PUSH,
                    severity="warning",
                ),
            ],
        )
        report = build_report(result)

        assert report.passed is True  # warnings don't fail
        assert report.summary.error_count == 0
        assert report.summary.warning_count == 1

    def test_violations_include_all_fields(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=1,
            checks_run=1,
            violations=[
                Violation(
                    file="src/app.py",
                    adr_id="ADR-0001",
                    message="Import disallowed",
                    level=EnforcementLevel.COMMIT,
                    severity="error",
                    line=42,
                    adr_title="Use FastAPI",
                    fix_suggestion="Replace with fastapi",
                ),
            ],
        )
        report = build_report(result)
        v = report.violations[0]

        assert v.file == "src/app.py"
        assert v.line == 42
        assert v.adr_id == "ADR-0001"
        assert v.adr_title == "Use FastAPI"
        assert v.message == "Import disallowed"
        assert v.severity == "error"
        assert v.level == "commit"
        assert v.fix_suggestion == "Replace with fastapi"

    def test_schema_version_present(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=0,
            checks_run=0,
        )
        report = build_report(result)
        assert report.schema_version == "1.0"

    def test_timestamp_is_iso_format(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=0,
            checks_run=0,
        )
        report = build_report(result)
        # Should parse as ISO 8601 without error
        assert "T" in report.timestamp
        assert report.timestamp.endswith("+00:00") or report.timestamp.endswith("Z")

    def test_errors_forwarded(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=0,
            checks_run=0,
            errors=["Could not read file X", "Invalid ADR format"],
        )
        report = build_report(result)
        assert len(report.errors) == 2
        assert "Could not read file X" in report.errors

    def test_json_roundtrip(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=5,
            checks_run=3,
            violations=[
                Violation(
                    file="src/app.py",
                    adr_id="ADR-0001",
                    message="Disallowed",
                    level=EnforcementLevel.COMMIT,
                    severity="error",
                    line=10,
                    adr_title="Test ADR",
                    fix_suggestion="Fix it",
                ),
            ],
        )
        report = build_report(result)

        # Serialize to JSON and back
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        restored = EnforcementReport.model_validate(parsed)

        assert restored.passed == report.passed
        assert restored.level == report.level
        assert restored.summary.error_count == 1
        assert len(restored.violations) == 1
        assert restored.violations[0].adr_id == "ADR-0001"

    def test_multiple_violations_mixed_severity(self):
        result = ValidationResult(
            level=EnforcementLevel.CI,
            files_checked=10,
            checks_run=5,
            violations=[
                Violation(
                    file="a.py",
                    adr_id="ADR-0001",
                    message="error1",
                    level=EnforcementLevel.COMMIT,
                    severity="error",
                ),
                Violation(
                    file="b.py",
                    adr_id="ADR-0002",
                    message="warn1",
                    level=EnforcementLevel.PUSH,
                    severity="warning",
                ),
                Violation(
                    file="c.py",
                    adr_id="ADR-0001",
                    message="error2",
                    level=EnforcementLevel.COMMIT,
                    severity="error",
                ),
            ],
        )
        report = build_report(result)

        assert report.passed is False
        assert report.summary.error_count == 2
        assert report.summary.warning_count == 1
        assert len(report.violations) == 3
