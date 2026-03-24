"""Configuration file writer with sentinel block management."""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import toml

from .models import (
    ApplicationStatus,
    ApplyResult,
    ConfigFragment,
    FragmentTarget,
    FragmentType,
    SentinelBlock,
)


class ConfigWriter:
    """Writes configuration fragments to target files with sentinel block management."""

    def __init__(self, backup_enabled: bool = True, backup_dir: Path | None = None):
        self.backup_enabled = backup_enabled
        self.backup_dir = backup_dir or Path(".adr-kit/backups")

    def apply_fragments(
        self, target: FragmentTarget, fragments: list[ConfigFragment]
    ) -> ApplyResult:
        """Apply configuration fragments to a target file."""

        result = ApplyResult(
            target=target,
            status=ApplicationStatus.SUCCESS,
            message="Fragments applied successfully",
        )

        try:
            # Ensure target file exists
            if not target.file_path.exists():
                result.status = ApplicationStatus.FAILED
                result.message = f"Target file does not exist: {target.file_path}"
                return result

            # Create backup if enabled
            if self.backup_enabled:
                backup_path = self._create_backup(target.file_path)
                result.backup_created = backup_path

            # Read current content
            original_content = target.file_path.read_text(encoding="utf-8")

            # Apply fragments based on file type
            if target.fragment_type in [FragmentType.ESLINT, FragmentType.PRETTIER]:
                updated_content = self._apply_json_fragments(
                    original_content, fragments, target
                )
            elif target.fragment_type in [
                FragmentType.RUFF,
                FragmentType.MYPY,
                FragmentType.IMPORT_LINTER,
            ]:
                updated_content = self._apply_toml_fragments(
                    original_content, fragments, target
                )
            else:
                updated_content = self._apply_text_fragments(
                    original_content, fragments, target
                )

            # Write updated content
            target.file_path.write_text(updated_content, encoding="utf-8")
            result.fragments_applied = len(fragments)

        except Exception as e:
            result.status = ApplicationStatus.FAILED
            result.message = f"Failed to apply fragments: {str(e)}"
            result.errors.append(str(e))

            # Restore from backup if available
            if result.backup_created and result.backup_created.exists():
                try:
                    shutil.copy2(result.backup_created, target.file_path)
                    result.warnings.append("Restored from backup after failure")
                except Exception as restore_error:
                    result.errors.append(f"Failed to restore backup: {restore_error}")

        return result

    def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of the target file."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}_{timestamp}.backup"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        return backup_path

    def _apply_json_fragments(
        self, content: str, fragments: list[ConfigFragment], target: FragmentTarget
    ) -> str:
        """Apply fragments to JSON configuration files (ESLint, Prettier)."""

        try:
            config = json.loads(content)
        except json.JSONDecodeError:
            # If not valid JSON, treat as text
            return self._apply_text_fragments(content, fragments, target)

        # Merge fragment content into config
        for fragment in fragments:
            try:
                fragment_config = json.loads(fragment.content)
                config = self._merge_json_configs(config, fragment_config)
            except json.JSONDecodeError:
                # Skip invalid JSON fragments
                continue

        return json.dumps(config, indent=2)

    def _apply_toml_fragments(
        self, content: str, fragments: list[ConfigFragment], target: FragmentTarget
    ) -> str:
        """Apply fragments to TOML configuration files (Ruff, Mypy)."""

        if toml is None:
            # TOML library not available, fall back to text mode
            return self._apply_text_fragments(content, fragments, target)

        try:
            config = toml.loads(content)
        except (
            Exception
        ):  # Broad exception handling since different TOML libs have different exceptions
            # If not valid TOML, treat as text
            return self._apply_text_fragments(content, fragments, target)

        # Merge fragment content into config
        for fragment in fragments:
            try:
                fragment_config = toml.loads(fragment.content)
                config = self._merge_dict_configs(config, fragment_config)
            except Exception:  # Broad exception handling
                # Skip invalid TOML fragments
                continue

        return toml.dumps(config)

    def _apply_text_fragments(
        self, content: str, fragments: list[ConfigFragment], target: FragmentTarget
    ) -> str:
        """Apply fragments to plain text files using sentinel blocks."""

        sentinel = SentinelBlock.for_fragment_type(target.fragment_type)

        # Combine all fragment content
        fragment_content = "\n".join(fragment.content for fragment in fragments)

        # Create the managed section
        managed_section = (
            f"{sentinel.start_marker}\n{fragment_content}\n{sentinel.end_marker}"
        )

        # Find and replace existing managed section
        pattern = (
            re.escape(sentinel.start_marker) + r".*?" + re.escape(sentinel.end_marker)
        )

        if re.search(pattern, content, re.DOTALL):
            # Replace existing section
            updated_content = re.sub(pattern, managed_section, content, flags=re.DOTALL)
        else:
            # Append new section
            updated_content = content.rstrip() + "\n\n" + managed_section + "\n"

        return updated_content

    def _merge_json_configs(
        self, base: dict[str, Any], fragment: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge JSON configuration objects."""
        return self._merge_dict_configs(base, fragment)

    def _merge_dict_configs(
        self, base: dict[str, Any], fragment: dict[str, Any]
    ) -> dict[str, Any]:
        """Deep merge dictionary configurations."""

        result = base.copy()

        for key, value in fragment.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._merge_dict_configs(result[key], value)
                elif isinstance(result[key], list) and isinstance(value, list):
                    # Merge lists, removing duplicates while preserving order
                    seen = set(result[key])
                    result[key] = result[key] + [
                        item for item in value if item not in seen
                    ]
                else:
                    # Fragment value overwrites base value
                    result[key] = value
            else:
                result[key] = value

        return result

    def remove_managed_sections(self, target: FragmentTarget) -> ApplyResult:
        """Remove all managed sections from a target file."""

        result = ApplyResult(
            target=target,
            status=ApplicationStatus.SUCCESS,
            message="Managed sections removed successfully",
        )

        try:
            if not target.file_path.exists():
                result.status = ApplicationStatus.SKIPPED
                result.message = "Target file does not exist"
                return result

            # Create backup if enabled
            if self.backup_enabled:
                backup_path = self._create_backup(target.file_path)
                result.backup_created = backup_path

            content = target.file_path.read_text(encoding="utf-8")
            sentinel = SentinelBlock.for_fragment_type(target.fragment_type)

            # Remove managed section
            pattern = (
                re.escape(sentinel.start_marker)
                + r".*?"
                + re.escape(sentinel.end_marker)
            )
            updated_content = re.sub(pattern, "", content, flags=re.DOTALL)

            # Clean up excessive blank lines
            updated_content = re.sub(r"\n{3,}", "\n\n", updated_content)

            target.file_path.write_text(updated_content, encoding="utf-8")

        except Exception as e:
            result.status = ApplicationStatus.FAILED
            result.message = f"Failed to remove managed sections: {str(e)}"
            result.errors.append(str(e))

        return result

    def has_managed_section(self, target: FragmentTarget) -> bool:
        """Check if target file has a managed section."""

        if not target.file_path.exists():
            return False

        content = target.file_path.read_text(encoding="utf-8")
        sentinel = SentinelBlock.for_fragment_type(target.fragment_type)

        return sentinel.start_marker in content and sentinel.end_marker in content
