"""Staged validation runner.

Executes ADR policy checks against files based on enforcement level:
- commit: staged files only (git diff --cached) — fast grep, <5s
- push:   changed files (git diff @{upstream}..HEAD) — broader, <15s
- ci:     all project files — comprehensive safety net, <2min

Architecture and config checks are classified but not yet executed
(reserved for ENF task). They appear in the check count but produce
no violations today — this is intentional and documented.
"""

import fnmatch
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..core.model import ADR, ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from .stages import EnforcementLevel, StagedCheck, checks_for_level, classify_adr_checks

# Source file extensions scanned during CI full-codebase pass
_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".kt"}

# Directories never scanned — generated/installed content
_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".adr-kit",
    ".project-index",
}


@dataclass
class Violation:
    """A single policy violation found during validation."""

    file: str
    adr_id: str
    message: str
    level: EnforcementLevel
    severity: str = "error"
    line: int | None = None
    adr_title: str | None = None
    fix_suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of a staged validation run."""

    level: EnforcementLevel
    files_checked: int
    checks_run: int
    violations: list[Violation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when no error-severity violations exist."""
        return not any(v.severity == "error" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return any(v.severity == "warning" for v in self.violations)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")


class StagedValidator:
    """Runs ADR policy checks classified by enforcement level."""

    def __init__(self, adr_dir: str | Path = "docs/adr"):
        self.adr_dir = Path(adr_dir)

    def validate(
        self,
        level: EnforcementLevel,
        project_root: Path | None = None,
    ) -> ValidationResult:
        """Run all checks active at the given level.

        Args:
            level: Enforcement level to run (commit/push/ci).
            project_root: Root directory for file resolution. Defaults to cwd.

        Returns:
            ValidationResult with all violations and metadata.
        """
        project_root = project_root or Path.cwd()

        adrs = self._load_accepted_adrs()
        all_checks = classify_adr_checks(adrs)
        active_checks = checks_for_level(all_checks, level)
        files = self._get_files(level, project_root)

        result = ValidationResult(
            level=level,
            files_checked=len(files),
            checks_run=len(active_checks),
        )

        for check in active_checks:
            violations = self._run_check(check, files, project_root)
            result.violations.extend(violations)

        return result

    # --- ADR loading ---

    def _load_accepted_adrs(self) -> list[ADR]:
        adrs: list[ADR] = []
        if not self.adr_dir.exists():
            return adrs
        for file_path in find_adr_files(self.adr_dir):
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.status == ADRStatus.ACCEPTED:
                    adrs.append(adr)
            except ParseError:
                continue
        return adrs

    # --- File collection ---

    def _get_files(self, level: EnforcementLevel, project_root: Path) -> list[Path]:
        if level == EnforcementLevel.COMMIT:
            return self._get_staged_files(project_root)
        elif level == EnforcementLevel.PUSH:
            files = self._get_changed_files(project_root)
            # Fall back to staged if no upstream info available
            return files or self._get_staged_files(project_root)
        else:  # CI
            return self._get_all_files(project_root)

    def _get_staged_files(self, project_root: Path) -> list[Path]:
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                capture_output=True,
                text=True,
                cwd=project_root,
            )
            if result.returncode != 0:
                return []
            files = [project_root / f for f in result.stdout.strip().splitlines() if f]
            return [f for f in files if f.exists()]
        except Exception:
            return []

    def _get_changed_files(self, project_root: Path) -> list[Path]:
        """Files changed since last push. Falls back gracefully if no upstream."""
        for cmd in [
            ["git", "diff", "--name-only", "@{upstream}..HEAD"],
            ["git", "diff", "--name-only", "HEAD~1..HEAD"],
        ]:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, cwd=project_root
                )
                if result.returncode == 0 and result.stdout.strip():
                    files = [
                        project_root / f
                        for f in result.stdout.strip().splitlines()
                        if f
                    ]
                    return [f for f in files if f.exists()]
            except Exception:
                continue
        return []

    def _get_all_files(self, project_root: Path) -> list[Path]:
        files = []
        for f in project_root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in _SOURCE_EXTENSIONS:
                continue
            # Skip excluded directories
            if any(part in _EXCLUDE_DIRS for part in f.parts):
                continue
            files.append(f)
        return files

    # --- Check dispatch ---

    def _run_check(
        self, check: StagedCheck, files: list[Path], project_root: Path
    ) -> list[Violation]:
        if check.check_type in ("import", "python_import"):
            return self._run_import_check(check, files, project_root)
        elif check.check_type == "pattern":
            return self._run_pattern_check(check, files, project_root)
        elif check.check_type == "required_structure":
            return self._run_structure_check(check, project_root)
        elif check.check_type == "architecture":
            return self._run_architecture_check(check, files, project_root)
        # config: classified but not yet executed
        return []

    def _filter_files_for_check(
        self, files: list[Path], check: StagedCheck
    ) -> list[Path]:
        """Filter file list to those relevant for the check type."""
        if check.check_type == "python_import":
            return [f for f in files if f.suffix == ".py"]
        if check.check_type == "import":
            return [f for f in files if f.suffix in {".js", ".ts", ".jsx", ".tsx"}]
        if check.file_glob and check.file_glob.startswith("*."):
            ext = check.file_glob[1:]  # "*.py" → ".py"
            return [f for f in files if f.name.endswith(ext)]
        return files

    def _run_import_check(
        self, check: StagedCheck, files: list[Path], project_root: Path
    ) -> list[Violation]:
        target_files = self._filter_files_for_check(files, check)
        violations = []
        escaped = re.escape(check.pattern)

        # Matches: import 'lib', from 'lib', require('lib') — with or without path prefix
        import_patterns = [
            re.compile(rf"""(import|from)\s+['"]([^'"]*?/)?{escaped}['"]"""),
            re.compile(rf"""require\s*\(\s*['"]([^'"]*?/)?{escaped}['"]\s*\)"""),
            re.compile(rf"""(import|from)\s+{escaped}(\s|$|;)"""),  # Python style
        ]

        for file_path in target_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for line_num, line in enumerate(content.splitlines(), 1):
                    for pattern in import_patterns:
                        if pattern.search(line):
                            violations.append(
                                Violation(
                                    file=str(file_path.relative_to(project_root)),
                                    adr_id=check.adr_id,
                                    message=check.message,
                                    level=check.level,
                                    severity=check.severity,
                                    line=line_num,
                                    adr_title=check.adr_title,
                                    fix_suggestion=f"Remove or replace this import — see {check.adr_id}",
                                )
                            )
                            break  # one violation per line
            except Exception:
                continue

        return violations

    def _run_pattern_check(
        self, check: StagedCheck, files: list[Path], project_root: Path
    ) -> list[Violation]:
        target_files = self._filter_files_for_check(files, check)
        violations = []

        try:
            compiled = re.compile(check.pattern)
        except re.error:
            return []  # invalid regex in ADR policy — skip silently

        for file_path in target_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for line_num, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        violations.append(
                            Violation(
                                file=str(file_path.relative_to(project_root)),
                                adr_id=check.adr_id,
                                message=check.message,
                                level=check.level,
                                severity=check.severity,
                                line=line_num,
                                adr_title=check.adr_title,
                            )
                        )
            except Exception:
                continue

        return violations

    def _run_structure_check(
        self, check: StagedCheck, project_root: Path
    ) -> list[Violation]:
        """Check that a required path (glob pattern) exists in the project."""
        import glob

        matches = list(glob.glob(check.pattern, root_dir=str(project_root)))
        if not matches:
            return [
                Violation(
                    file=check.pattern,
                    adr_id=check.adr_id,
                    message=check.message,
                    level=check.level,
                    severity=check.severity,
                    adr_title=check.adr_title,
                    fix_suggestion=f"Create the required path: {check.pattern} — see {check.adr_id}",
                )
            ]
        return []

    def _run_architecture_check(
        self, check: StagedCheck, files: list[Path], project_root: Path
    ) -> list[Violation]:
        """Check that source-layer files don't import from the target layer.

        Parses the rule string "source -> target" from check.pattern.
        Uses metadata["check"] glob to identify source-layer files.
        Scans those files for imports referencing the target layer.
        """
        # Parse "source -> target" from the rule string
        parts = check.pattern.split("->")
        if len(parts) != 2:
            return []  # malformed rule — degrade gracefully
        source_layer = parts[0].strip().lower()
        target_layer = parts[1].strip().lower()
        if not source_layer or not target_layer:
            return []

        # Filter files to source layer
        check_glob = check.metadata.get("check")
        source_files = self._filter_architecture_files(
            files, project_root, check_glob, source_layer
        )

        # Build regex patterns for imports containing target layer
        escaped = re.escape(target_layer)
        target_patterns = [
            # Python: from target_layer or from target_layer.sub
            re.compile(rf"(from|import)\s+{escaped}(\.\w+)*(\s|$|;)", re.IGNORECASE),
            # JS/TS: from '...target_layer...' or require('...target_layer...')
            re.compile(
                rf"""(import|from)\s+['"]([^'"]*[/\\])?{escaped}([/\\][^'"]*)?['"]""",
                re.IGNORECASE,
            ),
            re.compile(
                rf"""require\s*\(\s*['"]([^'"]*[/\\])?{escaped}([/\\][^'"]*)?['"]\s*\)""",
                re.IGNORECASE,
            ),
        ]

        violations = []
        for file_path in source_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(file_path.relative_to(project_root))
                for line_num, line in enumerate(content.splitlines(), 1):
                    for pattern in target_patterns:
                        if pattern.search(line):
                            violations.append(
                                Violation(
                                    file=rel_path,
                                    adr_id=check.adr_id,
                                    message=check.message,
                                    level=check.level,
                                    severity=check.severity,
                                    line=line_num,
                                    adr_title=check.adr_title,
                                    fix_suggestion=(
                                        f"Move this import out of {source_layer} code, "
                                        f"or refactor to avoid direct {target_layer} "
                                        f"dependency — see {check.adr_id}"
                                    ),
                                )
                            )
                            break  # one violation per line
            except Exception:
                continue

        return violations

    def _filter_architecture_files(
        self,
        files: list[Path],
        project_root: Path,
        check_glob: str | None,
        source_layer: str,
    ) -> list[Path]:
        """Filter files to those belonging to the source layer.

        Uses check_glob if provided, otherwise falls back to matching
        source_layer as a directory segment in the file path.
        """
        if check_glob:
            return [
                f
                for f in files
                if fnmatch.fnmatch(str(f.relative_to(project_root)), check_glob)
            ]

        # Fallback: match source_layer as a directory segment
        return [
            f
            for f in files
            if source_layer in [p.lower() for p in f.relative_to(project_root).parts]
        ]
