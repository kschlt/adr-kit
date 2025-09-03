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
from typing import List, Optional, Dict, Any, Union

import jsonschema
from jsonschema.exceptions import ValidationError as JsonSchemaError

from .model import ADR, ADRStatus
from .parse import parse_adr_file, ParseError, find_adr_files


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    
    level: str  # 'error' or 'warning'
    message: str
    field: Optional[str] = None
    rule: Optional[str] = None
    file_path: Optional[Path] = None

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
    issues: List[ValidationIssue]
    adr: Optional[ADR] = None
    
    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [issue for issue in self.issues if issue.level == 'error']
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [issue for issue in self.issues if issue.level == 'warning']
    
    def __bool__(self) -> bool:
        """Return True if validation passed."""
        return self.is_valid


class ADRValidator:
    """ADR validator with JSON Schema and semantic rule support."""
    
    def __init__(self, schema_path: Optional[Path] = None):
        """Initialize validator with JSON schema.
        
        Args:
            schema_path: Path to ADR JSON schema. If None, uses bundled schema.
        """
        self.schema_path = schema_path or self._get_default_schema_path()
        self.schema = self._load_schema()
        self.validator = jsonschema.Draft202012Validator(self.schema)
    
    def _get_default_schema_path(self) -> Path:
        """Get path to the bundled ADR schema."""
        # Assume schema is in the schemas/ directory relative to project root
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        return project_root / "schemas" / "adr.schema.json"
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load and parse the JSON schema."""
        if not self.schema_path.exists():
            raise ValueError(f"Schema file not found: {self.schema_path}")
        
        try:
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Cannot load schema from {self.schema_path}: {e}")
    
    def validate_schema(self, front_matter: Dict[str, Any], file_path: Optional[Path] = None) -> List[ValidationIssue]:
        """Validate front-matter against JSON schema.
        
        Args:
            front_matter: The front-matter dictionary to validate
            file_path: Optional file path for error reporting
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        try:
            self.validator.validate(front_matter)
        except JsonSchemaError as e:
            # Convert jsonschema errors to our issue format
            field_path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else None
            issues.append(ValidationIssue(
                level='error',
                message=e.message,
                field=field_path,
                rule='json_schema',
                file_path=file_path
            ))
        
        return issues
    
    def validate_semantic_rules(self, adr: ADR) -> List[ValidationIssue]:
        """Apply semantic validation rules to an ADR.
        
        Args:
            adr: The ADR to validate
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        # Rule: superseded ADRs must have superseded_by
        if (adr.front_matter.status == ADRStatus.SUPERSEDED and 
            (not adr.front_matter.superseded_by or len(adr.front_matter.superseded_by) == 0)):
            issues.append(ValidationIssue(
                level='error',
                message="ADRs with status 'superseded' must specify 'superseded_by'",
                field='superseded_by',
                rule='superseded_requires_superseded_by',
                file_path=adr.file_path
            ))
        
        # Rule: check for self-references in supersedes/superseded_by
        if adr.front_matter.supersedes and adr.front_matter.id in adr.front_matter.supersedes:
            issues.append(ValidationIssue(
                level='error',
                message="ADR cannot supersede itself",
                field='supersedes',
                rule='no_self_reference',
                file_path=adr.file_path
            ))
        
        if adr.front_matter.superseded_by and adr.front_matter.id in adr.front_matter.superseded_by:
            issues.append(ValidationIssue(
                level='error', 
                message="ADR cannot be superseded by itself",
                field='superseded_by',
                rule='no_self_reference',
                file_path=adr.file_path
            ))
        
        # Rule: proposed ADRs shouldn't have superseded_by
        if (adr.front_matter.status == ADRStatus.PROPOSED and 
            adr.front_matter.superseded_by and len(adr.front_matter.superseded_by) > 0):
            issues.append(ValidationIssue(
                level='warning',
                message="Proposed ADRs typically should not have 'superseded_by'",
                field='superseded_by',
                rule='proposed_not_superseded',
                file_path=adr.file_path
            ))
        
        return issues
    
    def validate_adr(self, adr: ADR) -> ValidationResult:
        """Validate a single ADR.
        
        Args:
            adr: The ADR to validate
            
        Returns:
            ValidationResult with issues found
        """
        issues = []
        
        # Schema validation on front-matter
        front_matter_dict = adr.front_matter.dict(exclude_none=True)
        issues.extend(self.validate_schema(front_matter_dict, adr.file_path))
        
        # Semantic rule validation
        issues.extend(self.validate_semantic_rules(adr))
        
        # Determine if validation passed (no errors, warnings OK)
        has_errors = any(issue.level == 'error' for issue in issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            adr=adr
        )
    
    def validate_file(self, file_path: Union[Path, str]) -> ValidationResult:
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
                issues=[ValidationIssue(
                    level='error',
                    message=str(e),
                    rule='parse_error',
                    file_path=Path(file_path)
                )]
            )
    
    def validate_directory(self, directory: Union[Path, str] = "docs/adr") -> List[ValidationResult]:
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

def validate_adr(adr: ADR, schema_path: Optional[Path] = None) -> ValidationResult:
    """Validate a single ADR object.
    
    Args:
        adr: The ADR to validate
        schema_path: Optional path to JSON schema file
        
    Returns:
        ValidationResult
    """
    validator = ADRValidator(schema_path)
    return validator.validate_adr(adr)


def validate_adr_file(file_path: Union[Path, str], schema_path: Optional[Path] = None) -> ValidationResult:
    """Validate an ADR file.
    
    Args:
        file_path: Path to ADR file
        schema_path: Optional path to JSON schema file
        
    Returns:
        ValidationResult
    """
    validator = ADRValidator(schema_path)
    return validator.validate_file(file_path)


def validate_adr_directory(directory: Union[Path, str] = "docs/adr", 
                          schema_path: Optional[Path] = None) -> List[ValidationResult]:
    """Validate all ADR files in a directory.
    
    Args:
        directory: Directory containing ADR files
        schema_path: Optional path to JSON schema file
        
    Returns:
        List of ValidationResult objects
    """
    validator = ADRValidator(schema_path)
    return validator.validate_directory(directory)