"""Pydantic models for ADR data structures.

Design decisions:
- Use Pydantic for strong typing and validation
- ADRFrontMatter maps directly to JSON schema requirements
- ADR combines front-matter with content for complete representation
- Status enum ensures valid values according to MADR spec
"""

import re
from datetime import date as Date
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ADRStatus(str, Enum):
    """Valid ADR status values according to MADR specification."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class ImportPolicy(BaseModel):
    """Policy for import restrictions and preferences."""

    disallow: list[str] | None = Field(
        None, description="List of disallowed imports/libraries"
    )
    prefer: list[str] | None = Field(
        None, description="List of preferred imports/libraries"
    )


# Legacy boundary models (deprecated - use ArchitecturePolicy instead)
# These will be removed in POL-3 when contract integration is updated
class BoundaryLayer(BaseModel):
    """Definition of an architectural layer (DEPRECATED)."""

    name: str = Field(..., description="Name of the layer")
    path: str | None = Field(None, description="Path pattern for the layer")


class BoundaryRule(BaseModel):
    """Rule for architectural boundaries (DEPRECATED)."""

    forbid: str = Field(
        ..., description="Forbidden dependency pattern (e.g., 'ui -> database')"
    )


class BoundaryPolicy(BaseModel):
    """Policy for architectural boundaries (DEPRECATED - use ArchitecturePolicy)."""

    layers: list[BoundaryLayer] | None = Field(None, description="Architectural layers")
    rules: list[BoundaryRule] | None = Field(None, description="Boundary rules")


# New architecture models (replaces BoundaryPolicy)
class LayerBoundaryRule(BaseModel):
    """Architectural layer boundary enforcement rule.

    Defines rules for which layers can/cannot access other layers.
    """

    rule: str = Field(..., description="Boundary rule (e.g., 'ui -> database')")
    check: str | None = Field(None, description="Path pattern to check (glob)")
    action: str = Field(default="block", description="Action to take: block or warn")
    message: str | None = Field(None, description="Custom error message")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Ensure action is one of: block, warn."""
        allowed = {"block", "warn"}
        if v not in allowed:
            raise ValueError(f"Action must be one of {allowed}, got: {v}")
        return v


class RequiredStructure(BaseModel):
    """Required file or directory structure.

    Defines files/directories that must exist in the project.
    """

    path: str = Field(..., description="Required path (glob pattern supported)")
    description: str | None = Field(
        None, description="Human-readable description of why this is required"
    )


class ArchitecturePolicy(BaseModel):
    """Comprehensive architecture policy replacing old BoundaryPolicy.

    Supports both layer boundaries and required file structure enforcement.
    """

    layer_boundaries: list[LayerBoundaryRule] | None = Field(
        None, description="Layer boundary rules"
    )
    required_structure: list[RequiredStructure] | None = Field(
        None, description="Required files/directories"
    )


class PythonPolicy(BaseModel):
    """Python-specific policy rules."""

    disallow_imports: list[str] | None = Field(
        None, description="Disallowed Python imports"
    )


class PatternRule(BaseModel):
    """Single pattern enforcement rule for code patterns.

    Pattern rules define enforceable code patterns (e.g., "all FastAPI handlers
    must be async"). The rule field supports both regex strings (for POL scope)
    and structured queries (dict, for future ENF scope).
    """

    description: str = Field(..., description="Human-readable rule description")
    language: str | None = Field(
        None, description="Programming language (python, javascript, typescript, etc.)"
    )
    rule: str | dict[str, Any] = Field(
        ..., description="Pattern rule as regex string or structured query dict"
    )
    autofix: bool | None = Field(
        None, description="Whether autofix is available for this rule"
    )
    severity: str = Field(
        default="error", description="Severity level: error, warning, or info"
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Ensure severity is one of: error, warning, info."""
        allowed = {"error", "warning", "info"}
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}, got: {v}")
        return v

    @field_validator("rule")
    @classmethod
    def validate_rule(cls, v: str | dict[str, Any]) -> str | dict[str, Any]:
        """Validate regex pattern if rule is a string."""
        if isinstance(v, str):
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}") from e
        return v


class PatternPolicy(BaseModel):
    """Collection of named pattern enforcement rules.

    Uses dict storage for better conflict resolution and clearer error messages.
    Keys are rule names (e.g., "async_handlers", "no_any_types").
    """

    patterns: dict[str, PatternRule] | None = Field(
        None, description="Named pattern rules as dict"
    )


class TypeScriptConfig(BaseModel):
    """TypeScript configuration requirements.

    Defines minimum required TypeScript configuration values that must be
    present in tsconfig.json. Subset matching: ADR specifies minimums,
    projects can have additional config.
    """

    tsconfig: dict[str, Any] | None = Field(
        None, description="Required tsconfig.json values (subset matching)"
    )


class PythonConfig(BaseModel):
    """Python configuration requirements.

    Defines minimum required Python tool configuration values (ruff, mypy, etc).
    Subset matching: ADR specifies minimums, projects can have additional config.
    """

    ruff: dict[str, Any] | None = Field(
        None, description="Required ruff configuration (subset matching)"
    )
    mypy: dict[str, Any] | None = Field(
        None, description="Required mypy configuration (subset matching)"
    )


class ConfigEnforcementPolicy(BaseModel):
    """Configuration file enforcement policies.

    Defines required configuration values across different tools and languages.
    Uses subset matching: ADR requirements are minimums, not exact config.
    """

    typescript: TypeScriptConfig | None = Field(
        None, description="TypeScript configuration requirements"
    )
    python: PythonConfig | None = Field(
        None, description="Python tool configuration requirements"
    )


class PolicyModel(BaseModel):
    """Structured policy model for ADR enforcement.

    This model defines extractable policies that can be automatically
    enforced through lint rules and code validation.
    """

    imports: ImportPolicy | None = Field(None, description="Import/library policies")
    boundaries: BoundaryPolicy | None = Field(
        None,
        description="[DEPRECATED] Architectural boundary policies - use architecture instead",
    )
    python: PythonPolicy | None = Field(None, description="Python-specific policies")
    patterns: PatternPolicy | None = Field(
        None, description="Code pattern enforcement policies"
    )
    architecture: ArchitecturePolicy | None = Field(
        None, description="Architecture policies (boundaries + required structure)"
    )
    config_enforcement: ConfigEnforcementPolicy | None = Field(
        None, description="Configuration file enforcement policies"
    )
    rationales: list[str] | None = Field(
        None, description="Rationales for the policies"
    )

    @field_validator("rationales", mode="before")
    @classmethod
    def ensure_rationales_list_or_none(cls, v: Any) -> list[str] | None:
        """Ensure rationales is a list or None, not empty list."""
        if v == []:
            return None
        if v is None:
            return None
        if isinstance(v, list):
            return v
        return None

    def get_disallowed_imports(self) -> list[str]:
        """Get disallowed imports list, safe null-checking."""
        if self.imports and self.imports.disallow:
            return self.imports.disallow
        return []

    def get_preferred_imports(self) -> list[str]:
        """Get preferred imports list, safe null-checking."""
        if self.imports and self.imports.prefer:
            return self.imports.prefer
        return []

    def get_python_disallowed_imports(self) -> list[str]:
        """Get Python disallowed imports list, safe null-checking."""
        if self.python and self.python.disallow_imports:
            return self.python.disallow_imports
        return []

    def get_pattern_rules(self) -> dict[str, PatternRule]:
        """Get pattern rules dict, safe null-checking."""
        if self.patterns and self.patterns.patterns:
            return self.patterns.patterns
        return {}

    def get_architecture_boundaries(self) -> list[LayerBoundaryRule]:
        """Get architecture layer boundaries, safe null-checking."""
        if self.architecture and self.architecture.layer_boundaries:
            return self.architecture.layer_boundaries
        return []

    def get_required_structure(self) -> list[RequiredStructure]:
        """Get required file/directory structure, safe null-checking."""
        if self.architecture and self.architecture.required_structure:
            return self.architecture.required_structure
        return []

    def get_config_requirements(self) -> ConfigEnforcementPolicy:
        """Get config enforcement requirements, safe null-checking."""
        if self.config_enforcement:
            return self.config_enforcement
        return ConfigEnforcementPolicy(typescript=None, python=None)


class ADRFrontMatter(BaseModel):
    """ADR front-matter data structure matching schemas/adr.schema.json.

    This model enforces the JSON schema requirements and provides
    semantic validation for ADR metadata.
    """

    id: str = Field(
        ..., pattern=r"^ADR-\d{4}$", description="ADR ID in format ADR-NNNN"
    )
    title: str = Field(..., min_length=1, description="Human-readable ADR title")
    status: ADRStatus = Field(..., description="Current status of the ADR")
    date: Date = Field(..., description="Date when ADR was created/decided")
    deciders: list[str] | None = Field(
        None, description="List of people who made the decision"
    )
    tags: list[str] | None = Field(None, description="Tags for categorization")
    supersedes: list[str] | None = Field(
        None, description="List of ADR IDs this supersedes"
    )
    superseded_by: list[str] | None = Field(
        None, description="List of ADR IDs that supersede this one"
    )
    depends_on: list[str] | None = Field(
        None, description="ADR IDs this decision depends on"
    )
    related_to: list[str] | None = Field(
        None, description="ADR IDs with a non-hierarchical relationship to this one"
    )
    policy: PolicyModel | None = Field(
        None, description="Structured policy for enforcement"
    )

    @field_validator(
        "deciders",
        "tags",
        "supersedes",
        "superseded_by",
        "depends_on",
        "related_to",
        mode="before",
    )
    @classmethod
    def ensure_list_or_none(cls, v: Any) -> list[str] | None:
        """Ensure array fields are lists or None, not empty lists."""
        if v == []:
            return None
        if v is None:
            return None
        if isinstance(v, list):
            return v
        return None

    @field_validator("superseded_by")
    @classmethod
    def validate_superseded_status(cls, v: Any, info: Any) -> list[str] | None:
        """Enforce semantic rule: if status=superseded, must have superseded_by."""
        status = info.data.get("status")
        if status == ADRStatus.SUPERSEDED and (not v or len(v) == 0):
            raise ValueError(
                "ADRs with status 'superseded' must have 'superseded_by' field"
            )
        if v is None:
            return None
        if isinstance(v, list):
            return v
        return None

    model_config = ConfigDict(
        use_enum_values=True,
        extra="allow",  # Allow additional properties as per JSON schema
    )


class ParsedContent:
    """Lazy parser for ADR markdown content sections.

    Parses standard MADR sections from markdown content with caching.
    Only executed once during approval workflow for performance.
    """

    def __init__(self, content: str):
        self.content = content

    @cached_property
    def decision(self) -> str:
        """Parse the ## Decision section from markdown content."""
        return self._extract_section("Decision")

    @cached_property
    def context(self) -> str:
        """Parse the ## Context section from markdown content."""
        return self._extract_section("Context")

    @cached_property
    def consequences(self) -> str:
        """Parse the ## Consequences section from markdown content."""
        return self._extract_section("Consequences")

    @cached_property
    def alternatives(self) -> str:
        """Parse the ## Alternatives section from markdown content."""
        return self._extract_section("Alternatives")

    def _extract_section(self, section_name: str) -> str:
        """Extract content from a markdown section by header name."""
        # Pattern to match ## Section through next ## or end of content
        pattern = rf"^##\s+{section_name}\s*\n(.*?)(?=^##|\Z)"
        match = re.search(
            pattern, self.content, re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return ""


class ADR(BaseModel):
    """Complete ADR representation including front-matter and content.

    This model combines the structured front-matter data with the
    Markdown content to provide a complete ADR representation.
    """

    front_matter: ADRFrontMatter = Field(..., description="Structured ADR metadata")
    content: str = Field(..., description="Markdown content of the ADR")
    file_path: Path | None = Field(
        None, description="Original file path if loaded from disk"
    )

    @property
    def id(self) -> str:
        """Convenience property to access ADR ID."""
        return self.front_matter.id

    @property
    def title(self) -> str:
        """Convenience property to access ADR title."""
        return self.front_matter.title

    @property
    def status(self) -> ADRStatus:
        """Convenience property to access ADR status."""
        return self.front_matter.status

    @property
    def policy(self) -> PolicyModel | None:
        """Convenience property to access ADR policy."""
        return self.front_matter.policy

    @property
    def supersedes(self) -> list[str] | None:
        """Convenience property to access supersedes list."""
        return self.front_matter.supersedes

    @property
    def superseded_by(self) -> list[str] | None:
        """Convenience property to access superseded_by list."""
        return self.front_matter.superseded_by

    @property
    def tags(self) -> list[str] | None:
        """Convenience property to access tags list."""
        return self.front_matter.tags

    @property
    def deciders(self) -> list[str] | None:
        """Convenience property to access deciders list."""
        return self.front_matter.deciders

    @cached_property
    def parsed_content(self) -> ParsedContent:
        """Lazily parsed markdown content sections."""
        return ParsedContent(self.content)

    @property
    def decision(self) -> str:
        """Parse the Decision section from markdown content."""
        return self.parsed_content.decision

    @property
    def context(self) -> str:
        """Parse the Context section from markdown content."""
        return self.parsed_content.context

    @property
    def consequences(self) -> str:
        """Parse the Consequences section from markdown content."""
        return self.parsed_content.consequences

    @property
    def alternatives(self) -> str:
        """Parse the Alternatives section from markdown content."""
        return self.parsed_content.alternatives

    def to_markdown(self) -> str:
        """Convert ADR back to markdown format with YAML front-matter."""
        import yaml

        # Convert front-matter to dict for YAML serialization
        fm_dict = self.front_matter.model_dump(exclude_none=True)

        # Format YAML front-matter
        yaml_str = yaml.dump(fm_dict, default_flow_style=False, sort_keys=False)

        return f"---\n{yaml_str}---\n\n{self.content}"

    model_config = ConfigDict(arbitrary_types_allowed=True)
