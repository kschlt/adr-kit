"""File monitoring system for detecting ADR changes."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from ..core.model import ADR
from ..core.parse import ParseError, find_adr_files, parse_adr_file


class ChangeType(str, Enum):
    """Types of file changes that can be detected."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    STATUS_CHANGED = "status_changed"  # ADR status changed
    POLICY_CHANGED = "policy_changed"  # ADR policy changed


@dataclass
class ChangeEvent:
    """Represents a detected change in an ADR file."""

    file_path: Path
    change_type: ChangeType
    adr_id: str | None = None
    old_status: str | None = None
    new_status: str | None = None
    detected_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.detected_at is None:
            self.detected_at = datetime.now()


class FileMonitor:
    """Monitors ADR directory for changes and detects policy-relevant events."""

    def __init__(self, adr_dir: Path):
        self.adr_dir = Path(adr_dir)
        self._file_hashes: dict[Path, str] = {}
        self._adr_statuses: dict[str, str] = {}
        self._adr_policies: dict[str, str] = {}

        # Initialize baseline state
        self._update_baseline()

    def _update_baseline(self) -> None:
        """Update the baseline state of all ADR files."""

        adr_files = find_adr_files(self.adr_dir)

        for file_path in adr_files:
            try:
                # Calculate file hash
                file_hash = self._calculate_file_hash(file_path)
                self._file_hashes[file_path] = file_hash

                # Parse ADR and store status/policy
                adr = parse_adr_file(file_path, strict=False)
                if adr:
                    status_value = (
                        adr.front_matter.status.value
                        if hasattr(adr.front_matter.status, "value")
                        else str(adr.front_matter.status)
                    )
                    self._adr_statuses[adr.id] = status_value

                    # Create a simple hash of the policy for change detection
                    policy_hash = self._calculate_policy_hash(adr)
                    self._adr_policies[adr.id] = policy_hash

            except (OSError, ParseError):
                # Skip files that can't be read or parsed
                continue

    def detect_changes(self) -> list[ChangeEvent]:
        """Detect changes since last check and update baseline."""

        changes = []
        current_files = set(find_adr_files(self.adr_dir))
        previous_files = set(self._file_hashes.keys())

        # Check for deleted files
        for deleted_file in previous_files - current_files:
            changes.append(
                ChangeEvent(file_path=deleted_file, change_type=ChangeType.DELETED)
            )
            # Clean up tracking
            del self._file_hashes[deleted_file]

        # Check for new and modified files
        for file_path in current_files:
            current_hash = self._calculate_file_hash(file_path)

            if file_path not in self._file_hashes:
                # New file
                changes.append(
                    ChangeEvent(file_path=file_path, change_type=ChangeType.CREATED)
                )
            elif self._file_hashes[file_path] != current_hash:
                # Modified file - check what changed
                try:
                    adr = parse_adr_file(file_path, strict=False)
                    if adr:
                        # Check for status changes
                        old_status = self._adr_statuses.get(adr.id)
                        new_status = (
                            adr.front_matter.status.value
                            if hasattr(adr.front_matter.status, "value")
                            else str(adr.front_matter.status)
                        )

                        if old_status != new_status:
                            changes.append(
                                ChangeEvent(
                                    file_path=file_path,
                                    change_type=ChangeType.STATUS_CHANGED,
                                    adr_id=adr.id,
                                    old_status=old_status,
                                    new_status=new_status,
                                )
                            )

                        # Check for policy changes
                        old_policy_hash = self._adr_policies.get(adr.id, "")
                        new_policy_hash = self._calculate_policy_hash(adr)

                        if old_policy_hash != new_policy_hash:
                            changes.append(
                                ChangeEvent(
                                    file_path=file_path,
                                    change_type=ChangeType.POLICY_CHANGED,
                                    adr_id=adr.id,
                                )
                            )

                        # Update tracking
                        self._adr_statuses[adr.id] = new_status
                        self._adr_policies[adr.id] = new_policy_hash

                except (OSError, ParseError):
                    # If we can't parse, just mark as modified
                    changes.append(
                        ChangeEvent(
                            file_path=file_path, change_type=ChangeType.MODIFIED
                        )
                    )

            # Update hash tracking
            self._file_hashes[file_path] = current_hash

        return changes

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content."""
        try:
            content = file_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return ""

    def _calculate_policy_hash(self, adr: ADR) -> str:
        """Calculate a hash representing the ADR's policy content."""

        policy_parts = []

        if adr.front_matter.policy:
            policy = adr.front_matter.policy

            # Include import policies
            if policy.imports:
                if policy.imports.disallow:
                    policy_parts.extend(sorted(policy.imports.disallow))
                if policy.imports.prefer:
                    policy_parts.extend(sorted(policy.imports.prefer))

            # Include boundary policies
            if policy.boundaries and policy.boundaries.rules:
                for rule in policy.boundaries.rules:
                    policy_parts.append(rule.forbid)

            # Include Python policies
            if policy.python and policy.python.disallow_imports:
                policy_parts.extend(sorted(policy.python.disallow_imports))

        # Create hash from sorted policy parts
        policy_text = "|".join(sorted(policy_parts))
        return hashlib.sha256(policy_text.encode("utf-8")).hexdigest()

    def get_policy_relevant_changes(
        self, changes: list[ChangeEvent]
    ) -> list[ChangeEvent]:
        """Filter changes to only those that affect policy enforcement."""

        policy_relevant = []

        for change in changes:
            if change.change_type in [
                ChangeType.STATUS_CHANGED,
                ChangeType.POLICY_CHANGED,
                ChangeType.CREATED,  # New ADRs might have policies
            ]:
                policy_relevant.append(change)

            # Status changes to/from 'accepted' are always relevant
            elif change.change_type == ChangeType.STATUS_CHANGED:
                if change.old_status == "accepted" or change.new_status == "accepted":
                    policy_relevant.append(change)

        return policy_relevant

    def force_refresh(self) -> None:
        """Force a complete refresh of the baseline state."""
        self._file_hashes.clear()
        self._adr_statuses.clear()
        self._adr_policies.clear()
        self._update_baseline()
