"""Enforcement stage classification model.

Maps ADR policy types to workflow stages (commit/push/ci) based on:
- Speed: how fast the check runs
- Scope: what files and context it needs

Stage semantics:
- commit (<5s): staged files only, fast grep — first checkpoint
- push  (<15s): changed files, broader context
- ci    (<2min): full codebase, all checks — safety net

A check assigned to level X also runs at all higher levels
(commit checks run at push and ci too).
"""

from dataclasses import dataclass, field
from enum import Enum


class EnforcementLevel(str, Enum):
    """Workflow stage at which enforcement checks run."""

    COMMIT = "commit"
    PUSH = "push"
    CI = "ci"


# Ordered levels for inclusion logic (lower index = earlier stage)
_LEVEL_ORDER: dict[EnforcementLevel, int] = {
    EnforcementLevel.COMMIT: 0,
    EnforcementLevel.PUSH: 1,
    EnforcementLevel.CI: 2,
}

# Policy type → minimum enforcement level
# A policy type at level X also runs at all higher levels.
POLICY_LEVEL_MAP: dict[str, EnforcementLevel] = {
    "imports": EnforcementLevel.COMMIT,  # fast grep — always first
    "python": EnforcementLevel.COMMIT,  # fast grep — always first
    "patterns": EnforcementLevel.COMMIT,  # fast regex — always first
    "architecture": EnforcementLevel.PUSH,  # needs broader file context
    "required_structure": EnforcementLevel.CI,  # full codebase check
    "config_enforcement": EnforcementLevel.CI,  # config deep check
}


@dataclass
class StagedCheck:
    """A single enforceable check classified to an enforcement level."""

    adr_id: str
    adr_title: str
    check_type: str  # "import" | "python_import" | "pattern" | "architecture" | "required_structure" | "config"
    level: EnforcementLevel
    pattern: str  # what to grep/check for
    message: str  # human-readable violation message
    file_glob: str | None = None  # file extension filter
    severity: str = "error"
    metadata: dict = field(default_factory=dict)  # extra context for complex checks


def classify_adr_checks(adrs: list) -> list[StagedCheck]:
    """Extract and classify all enforceable checks from a list of accepted ADRs.

    Returns one StagedCheck per enforceable rule across all policy types.
    Architecture and config checks are classified but not yet executed
    (reserved for ENF task — reported here for transparency).
    """
    checks: list[StagedCheck] = []

    for adr in adrs:
        if not adr.policy:
            continue

        policy = adr.policy
        adr_id = adr.id
        adr_title = adr.title

        # imports: disallowed JS/TS imports — COMMIT level
        if policy.imports and policy.imports.disallow:
            for lib in policy.imports.disallow:
                checks.append(
                    StagedCheck(
                        adr_id=adr_id,
                        adr_title=adr_title,
                        check_type="import",
                        level=EnforcementLevel.COMMIT,
                        pattern=lib,
                        message=f"Import of '{lib}' is disallowed — see {adr_id}: {adr_title}",
                    )
                )

        # python: disallowed Python imports — COMMIT level
        if policy.python and policy.python.disallow_imports:
            for lib in policy.python.disallow_imports:
                checks.append(
                    StagedCheck(
                        adr_id=adr_id,
                        adr_title=adr_title,
                        check_type="python_import",
                        level=EnforcementLevel.COMMIT,
                        pattern=lib,
                        message=f"Python import of '{lib}' is disallowed — see {adr_id}: {adr_title}",
                        file_glob="*.py",
                    )
                )

        # patterns: regex code pattern rules — COMMIT level (fast grep)
        if policy.patterns and policy.patterns.patterns:
            for name, rule in policy.patterns.patterns.items():
                if isinstance(rule.rule, str):  # only handle regex patterns
                    checks.append(
                        StagedCheck(
                            adr_id=adr_id,
                            adr_title=adr_title,
                            check_type="pattern",
                            level=EnforcementLevel.COMMIT,
                            pattern=rule.rule,
                            message=f"Pattern '{name}': {rule.description} — see {adr_id}",
                            file_glob=f"*.{rule.language}" if rule.language else None,
                            severity=rule.severity,
                        )
                    )

        # architecture: layer boundaries — PUSH level
        if policy.architecture and policy.architecture.layer_boundaries:
            for boundary in policy.architecture.layer_boundaries:
                checks.append(
                    StagedCheck(
                        adr_id=adr_id,
                        adr_title=adr_title,
                        check_type="architecture",
                        level=EnforcementLevel.PUSH,
                        pattern=boundary.rule,
                        message=boundary.message
                        or f"Architecture violation: {boundary.rule} — see {adr_id}",
                        severity="error" if boundary.action == "block" else "warning",
                        metadata={"rule": boundary.rule, "check": boundary.check},
                    )
                )

        # required_structure: file/dir existence — CI level
        if policy.architecture and policy.architecture.required_structure:
            for required in policy.architecture.required_structure:
                checks.append(
                    StagedCheck(
                        adr_id=adr_id,
                        adr_title=adr_title,
                        check_type="required_structure",
                        level=EnforcementLevel.CI,
                        pattern=required.path,
                        message=required.description
                        or f"Required path missing: {required.path} — see {adr_id}",
                    )
                )

        # config_enforcement — CI level
        if policy.config_enforcement:
            checks.append(
                StagedCheck(
                    adr_id=adr_id,
                    adr_title=adr_title,
                    check_type="config",
                    level=EnforcementLevel.CI,
                    pattern="config_check",
                    message=f"Configuration requirements from {adr_id}: {adr_title}",
                    metadata={
                        "policy": policy.config_enforcement.model_dump(
                            exclude_none=True
                        )
                    },
                )
            )

    return checks


def checks_for_level(
    checks: list[StagedCheck], level: EnforcementLevel
) -> list[StagedCheck]:
    """Return checks that should run at the given level (inclusive of lower levels).

    commit → runs commit checks only
    push   → runs commit + push checks
    ci     → runs all checks
    """
    target_order = _LEVEL_ORDER[level]
    return [c for c in checks if _LEVEL_ORDER[c.level] <= target_order]
