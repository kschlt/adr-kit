"""Pydantic models for ADR data structures.

Design decisions:
- Use Pydantic for strong typing and validation
- ADRFrontMatter maps directly to JSON schema requirements
- ADR combines front-matter with content for complete representation
- Status enum ensures valid values according to MADR spec
"""

from datetime import date as Date
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ADRStatus(str, Enum):
    """Valid ADR status values according to MADR specification."""
    
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


class ADRFrontMatter(BaseModel):
    """ADR front-matter data structure matching schemas/adr.schema.json.
    
    This model enforces the JSON schema requirements and provides
    semantic validation for ADR metadata.
    """
    
    id: str = Field(..., pattern=r"^ADR-\d{4}$", description="ADR ID in format ADR-NNNN")
    title: str = Field(..., min_length=1, description="Human-readable ADR title")
    status: ADRStatus = Field(..., description="Current status of the ADR")
    date: Date = Field(..., description="Date when ADR was created/decided")
    deciders: Optional[List[str]] = Field(None, description="List of people who made the decision")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    supersedes: Optional[List[str]] = Field(None, description="List of ADR IDs this supersedes")
    superseded_by: Optional[List[str]] = Field(None, description="List of ADR IDs that supersede this one")

    @field_validator('deciders', 'tags', 'supersedes', 'superseded_by', mode='before')
    @classmethod
    def ensure_list_or_none(cls, v):
        """Ensure array fields are lists or None, not empty lists."""
        if v == []:
            return None
        return v

    @field_validator('superseded_by')
    @classmethod
    def validate_superseded_status(cls, v, info):
        """Enforce semantic rule: if status=superseded, must have superseded_by."""
        status = info.data.get('status')
        if status == ADRStatus.SUPERSEDED and (not v or len(v) == 0):
            raise ValueError("ADRs with status 'superseded' must have 'superseded_by' field")
        return v

    model_config = ConfigDict(
        use_enum_values=True,
        extra="allow"  # Allow additional properties as per JSON schema
    )


class ADR(BaseModel):
    """Complete ADR representation including front-matter and content.
    
    This model combines the structured front-matter data with the
    Markdown content to provide a complete ADR representation.
    """
    
    front_matter: ADRFrontMatter = Field(..., description="Structured ADR metadata")
    content: str = Field(..., description="Markdown content of the ADR")
    file_path: Optional[Path] = Field(None, description="Original file path if loaded from disk")

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

    def to_markdown(self) -> str:
        """Convert ADR back to markdown format with YAML front-matter."""
        import yaml
        
        # Convert front-matter to dict for YAML serialization
        fm_dict = self.front_matter.model_dump(exclude_none=True)
        
        # Format YAML front-matter
        yaml_str = yaml.dump(fm_dict, default_flow_style=False, sort_keys=False)
        
        return f"---\n{yaml_str}---\n\n{self.content}"

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )