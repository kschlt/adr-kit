"""ADR validation using JSON Schema and semantic rules.

Design decisions:
- Use jsonschema library for schema validation against adr.schema.json
- Implement semantic rules as separate validation functions
- Provide detailed validation results with clear error messages
- Support both individual ADR validation and batch validation
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError as JsonSchemaError

from .immutability import ImmutabilityManager
from .model import ADR, ADRStatus
from .parse import ParseError, find_adr_files, parse_adr_file
from .policy_extractor import PolicyExtractor


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""

    level: str  # 'error' or 'warning'
    message: str
    field: str | None = None
    rule: str | None = None
    file_path: Path | None = None

    def __str__(self) -> str:
        parts = [f"[{self.level.upper()}]"]
        if self.file_path:
            parts.append(f"{self.file_path}:")
        if self.field:
            parts.append(f"field '{self.field}':")
        parts.append(self.message)
        if self.rule:
            parts.append(f"(rule: {self.rule})")
        return " ".join(parts)


@dataclass
class ValidationResult:
    """Result of ADR validation."""

    is_valid: bool
    issues: list[ValidationIssue]
    adr: ADR | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get only error-level issues."""
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get only warning-level issues."""
        return [issue for issue in self.issues if issue.level == "warning"]

    def __bool__(self) -> bool:
        """Return True if validation passed."""
        return self.is_valid


class ADRValidator:
    """ADR validator with JSON Schema and semantic rule support."""

    def __init__(
        self, schema_path: Path | None = None, project_root: Path | None = None
    ):
        """Initialize validator with JSON schema and immutability manager.

        Args:
            schema_path: Path to ADR JSON schema. If None, uses bundled schema.
            project_root: Project root directory for immutability manager.
        """
        self.schema_path = schema_path or self._get_default_schema_path()
        self.schema = self._load_schema()
        self.validator = jsonschema.Draft202012Validator(self.schema)
        self.policy_extractor = PolicyExtractor()
        self.immutability_manager = ImmutabilityManager(project_root)

    def _get_default_schema_path(self) -> Path:
        """Get path to the bundled ADR schema."""
        # Assume schema is in the schemas/ directory relative to project root
        # __file__ = .../adr-kit/adr_kit/core/validate.py
        # current_dir = .../adr-kit/adr_kit/core
        # project_root = .../adr-kit
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        return project_root / "schemas" / "adr.schema.json"

    def _load_schema(self) -> dict[str, Any]:
        """Load and parse the JSON schema."""
        if not self.schema_path.exists():
            raise ValueError(f"Schema file not found: {self.schema_path}")

        try:
            with open(self.schema_path) as f:
                schema = json.load(f)
                if not isinstance(schema, dict):
                    raise ValueError(
                        f"Schema must be a JSON object, got {type(schema)}"
                    )
                return schema
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Cannot load schema from {self.schema_path}: {e}") from e

    def _convert_for_schema_validation(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert Pydantic model data to JSON Schema compatible format.

        This handles the mismatch where Pydantic models use Python types (like datetime.date)
        but JSON Schema validation expects JSON-compatible types (like strings).

        Args:
            data: Dictionary from Pydantic model

        Returns:
            Schema-compatible dictionary with converted types
        """
        from datetime import date

        converted: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, date):
                # Convert datetime.date to ISO format string
                converted[key] = value.isoformat()
            elif isinstance(value, dict):
                # Recursively handle nested dictionaries
                converted[key] = self._convert_for_schema_validation(value)
            elif isinstance(value, list) and value:
                # Handle lists that might contain dates
                converted[key] = [
                    (
                        item.isoformat()
                        if isinstance(item, date)
                        else (
                            self._convert_for_schema_validation(item)
                            if isinstance(item, dict)
                            else item
                        )
                    )
                    for item in value
                ]
            else:
                # Keep other types as-is
                converted[key] = value
        return converted

    def validate_schema(
        self, front_matter: dict[str, Any], file_path: Path | None = None
    ) -> list[ValidationIssue]:
        """Validate front-matter against JSON schema.

        Args:
            front_matter: The front-matter dictionary to validate
            file_path: Optional file path for error reporting

        Returns:
            List of validation issues found
        """
        issues = []

        try:
            # Convert datetime.date objects back to strings for JSON Schema validation
            # This handles the mismatch between Pydantic model (uses datetime.date)
            # and JSON Schema (expects string)
            schema_compatible_data = self._convert_for_schema_validation(front_matter)
            self.validator.validate(schema_compatible_data)
        except JsonSchemaError as e:
            # Convert jsonschema errors to our issue format
            field_path = (
                ".".join(str(p) for p in e.absolute_path) if e.absolute_path else None
            )
            issues.append(
                ValidationIssue(
                    level="error",
                    message=e.message,
                    field=field_path,
                    rule="json_schema",
                    file_path=file_path,
                )
            )

        return issues

    def validate_semantic_rules(self, adr: ADR) -> list[ValidationIssue]:
        """Apply semantic validation rules to an ADR.

        Args:
            adr: The ADR to validate

        Returns:
            List of validation issues found
        """
        issues = []

        # Rule: superseded ADRs must have superseded_by
        if adr.front_matter.status == ADRStatus.SUPERSEDED and (
            not adr.front_matter.superseded_by
            or len(adr.front_matter.superseded_by) == 0
        ):
            issues.append(
                ValidationIssue(
                    level="error",
                    message="ADRs with status 'superseded' must specify 'superseded_by'",
                    field="superseded_by",
                    rule="superseded_requires_superseded_by",
                    file_path=adr.file_path,
                )
            )

        # Rule: check for self-references in supersedes/superseded_by
        if (
            adr.front_matter.supersedes
            and adr.front_matter.id in adr.front_matter.supersedes
        ):
            issues.append(
                ValidationIssue(
                    level="error",
                    message="ADR cannot supersede itself",
                    field="supersedes",
                    rule="no_self_reference",
                    file_path=adr.file_path,
                )
            )

        if (
            adr.front_matter.superseded_by
            and adr.front_matter.id in adr.front_matter.superseded_by
        ):
            issues.append(
                ValidationIssue(
                    level="error",
                    message="ADR cannot be superseded by itself",
                    field="superseded_by",
                    rule="no_self_reference",
                    file_path=adr.file_path,
                )
            )

        # Rule: proposed ADRs shouldn't have superseded_by
        if (
            adr.front_matter.status == ADRStatus.PROPOSED
            and adr.front_matter.superseded_by
            and len(adr.front_matter.superseded_by) > 0
        ):
            issues.append(
                ValidationIssue(
                    level="warning",
                    message="Proposed ADRs typically should not have 'superseded_by'",
                    field="superseded_by",
                    rule="proposed_not_superseded",
                    file_path=adr.file_path,
                )
            )

        return issues

    def validate_policy_requirements(self, adr: ADR) -> list[ValidationIssue]:
        """Validate policy requirements for ADRs.

        V3 spec requirements:
        - Accepted ADRs must have extractable policy information
        - Policy structure should be valid if present
        - Provide actionable guidance for missing policies

        Args:
            adr: The ADR to validate

        Returns:
            List of validation issues found
        """
        issues = []

        # Use policy extractor to validate completeness
        policy_errors = self.policy_extractor.validate_policy_completeness(adr)
        for error_msg in policy_errors:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=error_msg,
                    rule="policy_required_for_accepted",
                    file_path=adr.file_path,
                )
            )

        # Validate structured policy format if present
        if adr.front_matter.policy:
            issues.extend(self._validate_policy_structure(adr))

        # Check if accepted ADR has policy but it's incomplete
        if adr.front_matter.status == ADRStatus.ACCEPTED and adr.front_matter.policy:
            extracted_policy = self.policy_extractor.extract_policy(adr)
            if not self._is_policy_actionable(extracted_policy):
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"ADR {adr.front_matter.id} has policy block but no actionable enforcement rules. "
                        "Consider adding imports.disallow, boundaries.rules, or python.disallow_imports.",
                        rule="policy_actionability_check",
                        file_path=adr.file_path,
                    )
                )

        return issues

    def _validate_policy_structure(self, adr: ADR) -> list[ValidationIssue]:
        """Validate the structure of the policy block."""
        issues: list[ValidationIssue] = []
        policy = adr.front_matter.policy

        if not policy:
            return issues

        # Check that at least one policy type is specified
        has_policy_content = any(
            [
                policy.imports and (policy.imports.disallow or policy.imports.prefer),
                policy.boundaries
                and (policy.boundaries.layers or policy.boundaries.rules),
                policy.python and policy.python.disallow_imports,
                policy.rationales,
            ]
        )

        if not has_policy_content:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message="Policy block is present but empty. Consider removing it or adding policy content.",
                    field="policy",
                    rule="non_empty_policy",
                    file_path=adr.file_path,
                )
            )

        return issues

    def validate_immutability_requirements(self, adr: ADR) -> list[ValidationIssue]:
        """Validate ADR immutability requirements (V3 feature).

        Args:
            adr: The ADR to validate

        Returns:
            List of immutability violation issues
        """
        issues = []

        # Check for integrity violations (tamper detection)
        violations = self.immutability_manager.validate_adr_integrity(adr)
        for violation in violations:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=violation,
                    rule="immutability_integrity",
                    file_path=adr.file_path,
                )
            )

        # Check if locked ADR has invalid status transitions
        if self.immutability_manager.is_adr_locked(adr.front_matter.id):
            lock = self.immutability_manager.get_adr_lock(adr.front_matter.id)
            if lock:
                # Only certain status transitions are allowed for locked ADRs
                current_status = adr.front_matter.status
                if current_status not in [
                    ADRStatus.ACCEPTED,
                    ADRStatus.SUPERSEDED,
                    ADRStatus.DEPRECATED,
                ]:
                    issues.append(
                        ValidationIssue(
                            level="error",
                            message=f"Invalid status '{current_status}' for locked ADR {adr.front_matter.id}. "
                            f"Locked ADRs can only have status: accepted, superseded, or deprecated.",
                            field="status",
                            rule="immutability_status_transition",
                            file_path=adr.file_path,
                        )
                    )

        return issues

    def _is_policy_actionable(self, policy: Any) -> bool:
        """Check if policy has actionable enforcement rules."""
        return any(
            [
                policy.imports and policy.imports.disallow,
                policy.boundaries and policy.boundaries.rules,
                policy.python and policy.python.disallow_imports,
            ]
        )

    def validate_adr(self, adr: ADR) -> ValidationResult:
        """Validate a single ADR.

        Args:
            adr: The ADR to validate

        Returns:
            ValidationResult with issues found
        """
        issues = []

        # Schema validation on front-matter
        front_matter_dict = adr.front_matter.model_dump(exclude_none=True)
        issues.extend(self.validate_schema(front_matter_dict, adr.file_path))

        # Semantic rule validation
        issues.extend(self.validate_semantic_rules(adr))

        # Policy validation (V3 spec requirement)
        issues.extend(self.validate_policy_requirements(adr))

        # Immutability validation (V3 feature - Phase 3)
        issues.extend(self.validate_immutability_requirements(adr))

        # Determine if validation passed (no errors, warnings OK)
        has_errors = any(issue.level == "error" for issue in issues)

        return ValidationResult(is_valid=not has_errors, issues=issues, adr=adr)

    def validate_file(self, file_path: Path | str) -> ValidationResult:
        """Validate an ADR file.

        Args:
            file_path: Path to the ADR file to validate

        Returns:
            ValidationResult with issues found
        """
        try:
            adr = parse_adr_file(file_path, strict=False)
            return self.validate_adr(adr)
        except ParseError as e:
            return ValidationResult(
                is_valid=False,
                issues=[
                    ValidationIssue(
                        level="error",
                        message=str(e),
                        rule="parse_error",
                        file_path=Path(file_path),
                    )
                ],
            )

    def validate_directory(
        self, directory: Path | str = "docs/adr"
    ) -> list[ValidationResult]:
        """Validate all ADR files in a directory.

        Args:
            directory: Directory containing ADR files

        Returns:
            List of ValidationResult objects, one per file
        """
        results = []
        adr_files = find_adr_files(directory)

        for file_path in adr_files:
            results.append(self.validate_file(file_path))

        return results


# Convenience functions for common validation tasks


def validate_adr(
    adr: ADR, schema_path: Path | None = None, project_root: Path | None = None
) -> ValidationResult:
    """Validate a single ADR object.

    Args:
        adr: The ADR to validate
        schema_path: Optional path to JSON schema file
        project_root: Optional project root for immutability validation

    Returns:
        ValidationResult
    """
    validator = ADRValidator(schema_path, project_root)
    return validator.validate_adr(adr)


def validate_adr_file(
    file_path: Path | str,
    schema_path: Path | None = None,
    project_root: Path | None = None,
) -> ValidationResult:
    """Validate an ADR file.

    Args:
        file_path: Path to ADR file
        schema_path: Optional path to JSON schema file
        project_root: Optional project root for immutability validation

    Returns:
        ValidationResult
    """
    # Auto-detect project root from file path if not provided
    if project_root is None:
        file_path_obj = Path(file_path)
        # Look for common project indicators (docs/adr suggests project root is 2 levels up)
        if "docs/adr" in str(file_path_obj):
            project_root = file_path_obj.parent.parent.parent
        else:
            project_root = file_path_obj.parent.parent

    validator = ADRValidator(schema_path, project_root)
    return validator.validate_file(file_path)


def validate_adr_directory(
    directory: Path | str = "docs/adr", schema_path: Path | None = None
) -> list[ValidationResult]:
    """Validate all ADR files in a directory.

    Args:
        directory: Directory containing ADR files
        schema_path: Optional path to JSON schema file

    Returns:
        List of ValidationResult objects
    """
    validator = ADRValidator(schema_path)
    return validator.validate_directory(directory)
