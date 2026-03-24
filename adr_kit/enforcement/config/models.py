"""Data models for the Automatic Guardrail Management System."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FragmentType(str, Enum):
    """Types of configuration fragments."""

    ESLINT = "eslint"
    RUFF = "ruff"
    IMPORT_LINTER = "import_linter"
    PRETTIER = "prettier"
    MYPY = "mypy"
    CUSTOM = "custom"


class ApplicationStatus(str, Enum):
    """Status of configuration fragment application."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


@dataclass
class FragmentTarget:
    """Target configuration for applying a fragment."""

    file_path: Path
    fragment_type: FragmentType
    section_name: str | None = None  # For multi-section configs
    backup_enabled: bool = True


class ConfigFragment(BaseModel):
    """A configuration fragment to be applied to a target file."""

    fragment_type: FragmentType
    content: str = Field(..., description="The configuration content")
    source_adr_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SentinelBlock(BaseModel):
    """Sentinel block markers for tool-owned configuration sections."""

    start_marker: str
    end_marker: str
    description: str | None = None

    @classmethod
    def for_fragment_type(
        cls, fragment_type: FragmentType, tool_name: str = "adr-kit"
    ) -> "SentinelBlock":
        """Create standard sentinel block for a fragment type."""
        markers = {
            FragmentType.ESLINT: (
                f"/* === {tool_name.upper()} ADR RULES START === */",
                f"/* === {tool_name.upper()} ADR RULES END === */",
            ),
            FragmentType.RUFF: (
                f"# === {tool_name.upper()} ADR RULES START ===",
                f"# === {tool_name.upper()} ADR RULES END ===",
            ),
            FragmentType.IMPORT_LINTER: (
                f"# === {tool_name.upper()} ADR CONTRACTS START ===",
                f"# === {tool_name.upper()} ADR CONTRACTS END ===",
            ),
            FragmentType.PRETTIER: (
                f"// === {tool_name.upper()} ADR RULES START ===",
                f"// === {tool_name.upper()} ADR RULES END ===",
            ),
            FragmentType.MYPY: (
                f"# === {tool_name.upper()} ADR RULES START ===",
                f"# === {tool_name.upper()} ADR RULES END ===",
            ),
            FragmentType.CUSTOM: (
                f"# === {tool_name.upper()} START ===",
                f"# === {tool_name.upper()} END ===",
            ),
        }

        start_marker, end_marker = markers.get(
            fragment_type, markers[FragmentType.CUSTOM]
        )

        return cls(
            start_marker=start_marker,
            end_marker=end_marker,
            description=f"Auto-managed {fragment_type.value} rules from ADR policies",
        )


class ApplyResult(BaseModel):
    """Result of applying configuration fragments."""

    target: FragmentTarget
    status: ApplicationStatus
    message: str
    fragments_applied: int = 0
    backup_created: Path | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConfigTemplate(BaseModel):
    """Template for generating configuration fragments."""

    fragment_type: FragmentType
    template_content: str
    variables: dict[str, Any] = Field(default_factory=dict)

    def render(self, **kwargs: Any) -> str:
        """Render template with provided variables."""
        merged_vars = {**self.variables, **kwargs}
        try:
            return self.template_content.format(**merged_vars)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}") from e


class GuardrailConfig(BaseModel):
    """Configuration for the guardrail management system."""

    enabled: bool = True
    auto_apply: bool = True  # Whether to automatically apply changes
    backup_enabled: bool = True
    backup_dir: Path | None = None

    # Target configurations
    targets: list[FragmentTarget] = Field(default_factory=list)

    # Fragment type settings
    fragment_settings: dict[FragmentType, dict[str, Any]] = Field(default_factory=dict)

    # Templates for different configuration types
    templates: list[ConfigTemplate] = Field(default_factory=list)

    # Notification settings
    notify_on_apply: bool = True
    notify_on_error: bool = True

    model_config = ConfigDict(use_enum_values=True)

    def get_targets_for_type(self, fragment_type: FragmentType) -> list[FragmentTarget]:
        """Get all targets for a specific fragment type."""
        return [
            target for target in self.targets if target.fragment_type == fragment_type
        ]

    def get_template_for_type(
        self, fragment_type: FragmentType
    ) -> ConfigTemplate | None:
        """Get template for a specific fragment type."""
        for template in self.templates:
            if template.fragment_type == fragment_type:
                return template
        return None
