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


class BoundaryLayer(BaseModel):
    """Definition of an architectural layer."""

    name: str = Field(..., description="Name of the layer")
    path: str | None = Field(None, description="Path pattern for the layer")


class BoundaryRule(BaseModel):
    """Rule for architectural boundaries."""

    forbid: str = Field(
        ..., description="Forbidden dependency pattern (e.g., 'ui -> database')"
    )


class BoundaryPolicy(BaseModel):
    """Policy for architectural boundaries."""

    layers: list[BoundaryLayer] | None = Field(None, description="Architectural layers")
    rules: list[BoundaryRule] | None = Field(None, description="Boundary rules")


class PythonPolicy(BaseModel):
    """Python-specific policy rules."""

    disallow_imports: list[str] | None = Field(
        None, description="Disallowed Python imports"
    )


class PolicyModel(BaseModel):
    """Structured policy model for ADR enforcement.

    This model defines extractable policies that can be automatically
    enforced through lint rules and code validation.
    """

    imports: ImportPolicy | None = Field(None, description="Import/library policies")
    boundaries: BoundaryPolicy | None = Field(
        None, description="Architectural boundary policies"
    )
    python: PythonPolicy | None = Field(None, description="Python-specific policies")
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

    def get_boundary_rules(self) -> list[BoundaryRule]:
        """Get boundary rules list, safe null-checking."""
        if self.boundaries and self.boundaries.rules:
            return self.boundaries.rules
        return []

    def get_boundary_layers(self) -> list[BoundaryLayer]:
        """Get boundary layers list, safe null-checking."""
        if self.boundaries and self.boundaries.layers:
            return self.boundaries.layers
        return []

    def get_python_disallowed_imports(self) -> list[str]:
        """Get Python disallowed imports list, safe null-checking."""
        if self.python and self.python.disallow_imports:
            return self.python.disallow_imports
        return []


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
    policy: PolicyModel | None = Field(
        None, description="Structured policy for enforcement"
    )

    @field_validator("deciders", "tags", "supersedes", "superseded_by", mode="before")
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
