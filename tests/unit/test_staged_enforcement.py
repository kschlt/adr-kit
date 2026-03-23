"""Unit tests for staged enforcement: stage classification model and validator."""

import re
import tempfile
from pathlib import Path

import pytest

from adr_kit.enforce.stages import (
    EnforcementLevel,
    StagedCheck,
    checks_for_level,
    classify_adr_checks,
)
from adr_kit.enforce.validator import StagedValidator, ValidationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adr(
    adr_id: str = "ADR-0001",
    title: str = "Test ADR",
    imports_disallow: list[str] | None = None,
    python_disallow: list[str] | None = None,
    patterns: dict | None = None,
    architecture_boundaries: list[dict] | None = None,
    required_structure: list[dict] | None = None,
    config_enforcement: dict | None = None,
):
    """Create a minimal ADR-like object with given policies (no file I/O)."""
    from unittest.mock import MagicMock

    from adr_kit.core.model import (
        ArchitecturePolicy,
        ConfigEnforcementPolicy,
        ImportPolicy,
        LayerBoundaryRule,
        PatternPolicy,
        PatternRule,
        PolicyModel,
        PythonPolicy,
        RequiredStructure,
    )

    policy_kwargs: dict = {}

    if imports_disallow is not None:
        policy_kwargs["imports"] = ImportPolicy(disallow=imports_disallow)

    if python_disallow is not None:
        policy_kwargs["python"] = PythonPolicy(disallow_imports=python_disallow)

    if patterns is not None:
        rules = {
            name: PatternRule(
                description=data["description"],
                rule=data["rule"],
                language=data.get("language"),
                severity=data.get("severity", "error"),
            )
            for name, data in patterns.items()
        }
        policy_kwargs["patterns"] = PatternPolicy(patterns=rules)

    if architecture_boundaries is not None:
        boundary_rules = [
            LayerBoundaryRule(
                rule=b["rule"],
                check=b.get("check"),
                action=b.get("action", "block"),
                message=b.get("message"),
            )
            for b in architecture_boundaries
        ]
        arch = policy_kwargs.get("architecture") or ArchitecturePolicy()
        policy_kwargs["architecture"] = ArchitecturePolicy(
            layer_boundaries=boundary_rules,
            required_structure=arch.required_structure,
        )

    if required_structure is not None:
        structs = [
            RequiredStructure(path=s["path"], description=s.get("description"))
            for s in required_structure
        ]
        arch = policy_kwargs.get("architecture") or ArchitecturePolicy()
        policy_kwargs["architecture"] = ArchitecturePolicy(
            layer_boundaries=arch.layer_boundaries,
            required_structure=structs,
        )

    if config_enforcement is not None:
        policy_kwargs["config_enforcement"] = ConfigEnforcementPolicy(
            **config_enforcement
        )

    policy = PolicyModel(**policy_kwargs) if policy_kwargs else None

    adr = MagicMock()
    adr.id = adr_id
    adr.title = title
    adr.policy = policy
    return adr


# ---------------------------------------------------------------------------
# classify_adr_checks
# ---------------------------------------------------------------------------


class TestClassifyAdrChecks:
    def test_no_policy_produces_no_checks(self):
        adr = _make_adr()
        assert classify_adr_checks([adr]) == []

    def test_imports_disallow_produces_commit_checks(self):
        adr = _make_adr(imports_disallow=["flask", "django"])
        checks = classify_adr_checks([adr])
        assert len(checks) == 2
        for c in checks:
            assert c.check_type == "import"
            assert c.level == EnforcementLevel.COMMIT
            assert c.adr_id == "ADR-0001"

    def test_python_disallow_produces_commit_checks(self):
        adr = _make_adr(python_disallow=["requests"])
        checks = classify_adr_checks([adr])
        assert len(checks) == 1
        assert checks[0].check_type == "python_import"
        assert checks[0].level == EnforcementLevel.COMMIT
        assert checks[0].file_glob == "*.py"

    def test_pattern_rule_produces_commit_check(self):
        adr = _make_adr(
            patterns={
                "no_console": {
                    "description": "No console.log",
                    "rule": r"console\.log",
                    "language": "typescript",
                }
            }
        )
        checks = classify_adr_checks([adr])
        assert len(checks) == 1
        assert checks[0].check_type == "pattern"
        assert checks[0].level == EnforcementLevel.COMMIT
        assert checks[0].file_glob == "*.typescript"

    def test_architecture_boundaries_produce_push_checks(self):
        adr = _make_adr(
            architecture_boundaries=[{"rule": "ui -> database", "action": "block"}]
        )
        checks = classify_adr_checks([adr])
        arch_checks = [c for c in checks if c.check_type == "architecture"]
        assert len(arch_checks) == 1
        assert arch_checks[0].level == EnforcementLevel.PUSH

    def test_required_structure_produces_ci_checks(self):
        adr = _make_adr(
            required_structure=[{"path": "docs/adr", "description": "ADR dir"}]
        )
        checks = classify_adr_checks([adr])
        struct_checks = [c for c in checks if c.check_type == "required_structure"]
        assert len(struct_checks) == 1
        assert struct_checks[0].level == EnforcementLevel.CI

    def test_config_enforcement_produces_ci_check(self):
        adr = _make_adr(config_enforcement={})
        checks = classify_adr_checks([adr])
        config_checks = [c for c in checks if c.check_type == "config"]
        assert len(config_checks) == 1
        assert config_checks[0].level == EnforcementLevel.CI

    def test_violation_message_includes_adr_id(self):
        adr = _make_adr(imports_disallow=["flask"])
        checks = classify_adr_checks([adr])
        assert "ADR-0001" in checks[0].message

    def test_multiple_adrs_classified_independently(self):
        adr1 = _make_adr("ADR-0001", imports_disallow=["flask"])
        adr2 = _make_adr("ADR-0002", python_disallow=["requests"])
        checks = classify_adr_checks([adr1, adr2])
        assert len(checks) == 2
        assert {c.adr_id for c in checks} == {"ADR-0001", "ADR-0002"}

    def test_architecture_block_action_maps_to_error_severity(self):
        adr = _make_adr(
            architecture_boundaries=[{"rule": "ui -> db", "action": "block"}]
        )
        checks = classify_adr_checks([adr])
        assert checks[0].severity == "error"

    def test_architecture_warn_action_maps_to_warning_severity(self):
        adr = _make_adr(
            architecture_boundaries=[{"rule": "ui -> db", "action": "warn"}]
        )
        checks = classify_adr_checks([adr])
        assert checks[0].severity == "warning"


# ---------------------------------------------------------------------------
# checks_for_level
# ---------------------------------------------------------------------------


class TestChecksForLevel:
    def _make_check(self, level: EnforcementLevel) -> StagedCheck:
        return StagedCheck(
            adr_id="ADR-0001",
            adr_title="T",
            check_type="import",
            level=level,
            pattern="flask",
            message="msg",
        )

    def test_commit_level_includes_only_commit_checks(self):
        checks = [
            self._make_check(EnforcementLevel.COMMIT),
            self._make_check(EnforcementLevel.PUSH),
            self._make_check(EnforcementLevel.CI),
        ]
        result = checks_for_level(checks, EnforcementLevel.COMMIT)
        assert len(result) == 1
        assert result[0].level == EnforcementLevel.COMMIT

    def test_push_level_includes_commit_and_push(self):
        checks = [
            self._make_check(EnforcementLevel.COMMIT),
            self._make_check(EnforcementLevel.PUSH),
            self._make_check(EnforcementLevel.CI),
        ]
        result = checks_for_level(checks, EnforcementLevel.PUSH)
        assert len(result) == 2
        levels = {c.level for c in result}
        assert EnforcementLevel.CI not in levels

    def test_ci_level_includes_all_checks(self):
        checks = [
            self._make_check(EnforcementLevel.COMMIT),
            self._make_check(EnforcementLevel.PUSH),
            self._make_check(EnforcementLevel.CI),
        ]
        result = checks_for_level(checks, EnforcementLevel.CI)
        assert len(result) == 3

    def test_empty_checks_returns_empty(self):
        assert checks_for_level([], EnforcementLevel.COMMIT) == []


# ---------------------------------------------------------------------------
# StagedValidator — file filtering and import detection
# ---------------------------------------------------------------------------


class TestStagedValidatorImportCheck:
    def _run_ci_validate(
        self, files: dict[str, str], imports_disallow: list[str]
    ) -> ValidationResult:
        """Helper: write files to temp dir, run CI-level validation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            # Write a minimal accepted ADR with given policy
            adr_content = f"""---
id: ADR-0001
title: Test
status: accepted
date: 2026-01-01
policy:
  imports:
    disallow: {imports_disallow}
---

## Context
test
"""
            (adr_dir / "ADR-0001-test.md").write_text(adr_content)

            validator = StagedValidator(adr_dir=adr_dir)
            return validator.validate(EnforcementLevel.CI, project_root=root)

    def test_detects_js_import_violation(self):
        result = self._run_ci_validate(
            {"src/index.ts": "import { app } from 'flask'\nconsole.log(app)"},
            ["flask"],
        )
        assert not result.passed
        assert result.error_count == 1
        assert "flask" in result.violations[0].message

    def test_detects_require_violation(self):
        result = self._run_ci_validate(
            {"src/index.js": "const flask = require('flask')"},
            ["flask"],
        )
        assert not result.passed

    def test_no_violation_when_import_absent(self):
        result = self._run_ci_validate(
            {
                "src/index.ts": "import { something } from 'fastapi'\nconsole.log(something)"
            },
            ["flask"],
        )
        assert result.passed
        assert result.error_count == 0

    def test_python_import_only_checks_py_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            # TS file with "requests" — should NOT trigger python_import check
            (root / "index.ts").write_text("import requests from 'requests'")
            # PY file with "requests" — SHOULD trigger
            (root / "app.py").write_text(
                "import requests\nrequests.get('http://example.com')"
            )

            adr_content = """---
id: ADR-0001
title: No requests
status: accepted
date: 2026-01-01
policy:
  python:
    disallow_imports: [requests]
---

## Context
Use httpx instead.
"""
            (adr_dir / "ADR-0001-no-requests.md").write_text(adr_content)

            validator = StagedValidator(adr_dir=adr_dir)
            result = validator.validate(EnforcementLevel.CI, project_root=root)

        # Only app.py should be flagged
        assert result.error_count == 1
        assert "app.py" in result.violations[0].file

    def test_no_adr_dir_returns_clean_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            validator = StagedValidator(adr_dir=root / "nonexistent")
            result = validator.validate(EnforcementLevel.CI, project_root=root)
        assert result.passed
        assert result.checks_run == 0

    def test_result_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            (root / "app.py").write_text("import flask")

            adr_content = """---
id: ADR-0001
title: No flask
status: accepted
date: 2026-01-01
policy:
  python:
    disallow_imports: [flask]
---

## Context
Use FastAPI.
"""
            (adr_dir / "ADR-0001.md").write_text(adr_content)
            validator = StagedValidator(adr_dir=adr_dir)
            result = validator.validate(EnforcementLevel.CI, project_root=root)

        assert result.level == EnforcementLevel.CI
        assert result.checks_run >= 1
        assert result.files_checked >= 1

    def test_violation_includes_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            (root / "app.py").write_text("# line 1\nimport flask\n# line 3")

            adr_content = """---
id: ADR-0001
title: No flask
status: accepted
date: 2026-01-01
policy:
  python:
    disallow_imports: [flask]
---
"""
            (adr_dir / "ADR-0001.md").write_text(adr_content)
            validator = StagedValidator(adr_dir=adr_dir)
            result = validator.validate(EnforcementLevel.CI, project_root=root)

        assert result.violations[0].line == 2


class TestStagedValidatorPatternCheck:
    def test_detects_pattern_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            (root / "app.py").write_text("x = eval('dangerous')")

            adr_content = """---
id: ADR-0001
title: No eval
status: accepted
date: 2026-01-01
policy:
  patterns:
    patterns:
      no_eval:
        description: No eval usage
        rule: "\\\\beval\\\\("
        severity: error
---
"""
            (adr_dir / "ADR-0001.md").write_text(adr_content)
            validator = StagedValidator(adr_dir=adr_dir)
            result = validator.validate(EnforcementLevel.CI, project_root=root)

        assert result.error_count >= 1

    def test_invalid_regex_pattern_skipped_gracefully(self):
        """An invalid regex in an ADR policy should not crash the validator."""
        from adr_kit.enforce.stages import StagedCheck
        from adr_kit.enforce.validator import StagedValidator

        check = StagedCheck(
            adr_id="ADR-0001",
            adr_title="T",
            check_type="pattern",
            level=EnforcementLevel.CI,
            pattern="[invalid regex",
            message="bad",
        )
        validator = StagedValidator()
        result = validator._run_pattern_check(check, [], Path("."))
        assert result == []


class TestValidationResult:
    def test_passed_true_when_no_violations(self):
        result = ValidationResult(
            level=EnforcementLevel.COMMIT, files_checked=5, checks_run=3
        )
        assert result.passed

    def test_passed_false_when_error_violation_present(self):
        from adr_kit.enforce.validator import Violation

        result = ValidationResult(
            level=EnforcementLevel.COMMIT, files_checked=5, checks_run=3
        )
        result.violations.append(
            Violation(
                file="x.py",
                adr_id="ADR-0001",
                message="m",
                level=EnforcementLevel.COMMIT,
                severity="error",
            )
        )
        assert not result.passed

    def test_passed_true_with_only_warnings(self):
        from adr_kit.enforce.validator import Violation

        result = ValidationResult(
            level=EnforcementLevel.COMMIT, files_checked=5, checks_run=3
        )
        result.violations.append(
            Violation(
                file="x.py",
                adr_id="ADR-0001",
                message="m",
                level=EnforcementLevel.COMMIT,
                severity="warning",
            )
        )
        assert result.passed
        assert result.has_warnings

    def test_error_and_warning_counts(self):
        from adr_kit.enforce.validator import Violation

        result = ValidationResult(
            level=EnforcementLevel.CI, files_checked=10, checks_run=5
        )
        result.violations.append(
            Violation(
                file="a.py",
                adr_id="ADR-0001",
                message="e",
                level=EnforcementLevel.CI,
                severity="error",
            )
        )
        result.violations.append(
            Violation(
                file="b.py",
                adr_id="ADR-0001",
                message="w",
                level=EnforcementLevel.CI,
                severity="warning",
            )
        )
        assert result.error_count == 1
        assert result.warning_count == 1


# ---------------------------------------------------------------------------
# StagedValidator — architecture layer boundary checks
# ---------------------------------------------------------------------------


class TestStagedValidatorArchitectureCheck:
    """Test layer boundary enforcement via architecture checks."""

    def _run_arch_validate(
        self,
        files: dict[str, str],
        boundaries: list[dict],
        adr_id: str = "ADR-0001",
        title: str = "Layer Architecture",
    ) -> "ValidationResult":
        """Helper: write files + ADR to temp dir, run CI-level validation."""
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adr_dir = root / "docs" / "adr"
            adr_dir.mkdir(parents=True)

            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            # Build ADR with architecture policy
            policy: dict = {"architecture": {"layer_boundaries": boundaries}}
            front_matter = {
                "id": adr_id,
                "title": title,
                "status": "accepted",
                "date": "2026-01-01",
                "policy": policy,
            }
            adr_content = f"---\n{yaml.dump(front_matter, default_flow_style=False)}---\n\n## Context\ntest\n"
            (adr_dir / f"{adr_id}-test.md").write_text(adr_content)

            validator = StagedValidator(adr_dir=adr_dir)
            return validator.validate(EnforcementLevel.CI, project_root=root)

    def test_detects_python_cross_layer_import(self):
        result = self._run_arch_validate(
            files={
                "src/ui/views.py": "from database.models import User\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "src/ui/**",
                    "action": "block",
                    "message": "UI must not import database directly",
                }
            ],
        )
        assert not result.passed
        assert result.error_count == 1
        v = result.violations[0]
        assert v.file == "src/ui/views.py"
        assert v.line == 1
        assert "UI must not import database directly" in v.message

    def test_detects_js_cross_layer_import(self):
        result = self._run_arch_validate(
            files={
                "src/ui/App.tsx": "import { query } from '../database/client'\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "src/ui/**",
                    "action": "block",
                }
            ],
        )
        assert not result.passed
        assert result.error_count == 1

    def test_no_violation_when_import_in_allowed_direction(self):
        """database importing from database is fine — only ui->database blocked."""
        result = self._run_arch_validate(
            files={
                "src/database/repo.py": "from database.models import User\n",
                "src/ui/views.py": "print('no imports here')\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "src/ui/**",
                    "action": "block",
                }
            ],
        )
        assert result.passed

    def test_check_glob_filters_source_files(self):
        """Only files matching check glob are scanned, not all files."""
        result = self._run_arch_validate(
            files={
                # This file imports database but is NOT in src/ui/
                "src/api/handler.py": "from database.models import User\n",
                # This file is in src/ui/ but doesn't import database
                "src/ui/home.py": "print('clean')\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "src/ui/**",
                    "action": "block",
                }
            ],
        )
        assert result.passed

    def test_no_check_glob_falls_back_to_directory_matching(self):
        """Without check glob, matches source_layer as a directory segment."""
        result = self._run_arch_validate(
            files={
                "src/ui/views.py": "from database.models import User\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "action": "block",
                }
            ],
        )
        assert not result.passed
        assert result.error_count == 1

    def test_warn_action_produces_warning_severity(self):
        result = self._run_arch_validate(
            files={
                "src/ui/views.py": "from database.models import User\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "src/ui/**",
                    "action": "warn",
                }
            ],
        )
        # Warnings don't fail the check
        assert result.passed
        assert result.warning_count == 1
        assert result.violations[0].severity == "warning"

    def test_violation_includes_line_number_and_fix_suggestion(self):
        result = self._run_arch_validate(
            files={
                "src/ui/views.py": "# header\nfrom database.models import User\n",
            },
            boundaries=[
                {
                    "rule": "ui -> database",
                    "check": "src/ui/**",
                    "action": "block",
                }
            ],
        )
        assert result.error_count == 1
        v = result.violations[0]
        assert v.line == 2
        assert v.fix_suggestion is not None
        assert "database" in v.fix_suggestion
        assert v.adr_title == "Layer Architecture"

    def test_malformed_rule_degrades_gracefully(self):
        """A rule without '->' should produce no violations, not crash."""
        result = self._run_arch_validate(
            files={
                "src/ui/views.py": "from database.models import User\n",
            },
            boundaries=[
                {
                    "rule": "invalid rule format",
                    "check": "src/ui/**",
                    "action": "block",
                }
            ],
        )
        # No violations — malformed rule is skipped
        assert result.violations == [] or result.passed

    def test_multiple_boundary_rules(self):
        result = self._run_arch_validate(
            files={
                "src/ui/views.py": "from database.models import User\nimport api.client\n",
            },
            boundaries=[
                {"rule": "ui -> database", "check": "src/ui/**", "action": "block"},
                {"rule": "ui -> api", "check": "src/ui/**", "action": "warn"},
            ],
        )
        assert result.error_count == 1  # database -> error
        assert result.warning_count == 1  # api -> warning
