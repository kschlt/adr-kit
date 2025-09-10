"""Immutability and approval system for ADRs.

Design decisions:
- Compute SHA-256 digest over normalized ADR content
- Store digests in .project-index/adr-locks.json for tamper detection
- Support optional file read-only protection (chmod 0444)
- Allow only status transitions and supersession updates after approval
"""

import hashlib
import json
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .model import ADR


@dataclass
class ADRLock:
    """Represents an immutable ADR with its content digest."""

    adr_id: str
    digest: str
    locked_at: str  # ISO timestamp
    file_path: str | None = None
    is_readonly: bool = False


class ImmutabilityManager:
    """Manages ADR immutability through content digests and locks."""

    def __init__(self, project_root: Path | None = None):
        """Initialize immutability manager.

        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = project_root or Path.cwd()
        self.index_dir = self.project_root / ".project-index"
        self.locks_file = self.index_dir / "adr-locks.json"

        # Ensure index directory exists
        self.index_dir.mkdir(exist_ok=True)

    def compute_content_digest(self, adr: ADR) -> str:
        """Compute SHA-256 digest of ADR content for immutability tracking.

        Args:
            adr: The ADR to compute digest for

        Returns:
            SHA-256 hex digest of normalized content
        """
        # Create normalized representation for hashing
        # Only include immutable fields (exclude status transitions and supersession)
        normalized_content = {
            # Core immutable fields
            "id": adr.front_matter.id,
            "title": adr.front_matter.title,
            "date": adr.front_matter.date.isoformat(),
            "content": adr.content.strip(),
            # Optional immutable fields (if present)
            "deciders": adr.front_matter.deciders,
            "tags": adr.front_matter.tags,
            "supersedes": adr.front_matter.supersedes,
            "policy": (
                adr.front_matter.policy.model_dump()
                if adr.front_matter.policy
                else None
            ),
        }

        # Remove None values for consistent hashing
        normalized_content = {
            k: v for k, v in normalized_content.items() if v is not None
        }

        # Create deterministic JSON representation
        content_json = json.dumps(
            normalized_content, sort_keys=True, ensure_ascii=False
        )

        # Compute SHA-256 digest
        return hashlib.sha256(content_json.encode("utf-8")).hexdigest()

    def load_locks(self) -> dict[str, ADRLock]:
        """Load existing ADR locks from storage.

        Returns:
            Dictionary mapping ADR ID to ADRLock
        """
        if not self.locks_file.exists():
            return {}

        try:
            with open(self.locks_file, encoding="utf-8") as f:
                data = json.load(f)

            locks = {}
            for adr_id, lock_data in data.get("locks", {}).items():
                locks[adr_id] = ADRLock(
                    adr_id=adr_id,
                    digest=lock_data["digest"],
                    locked_at=lock_data["locked_at"],
                    file_path=lock_data.get("file_path"),
                    is_readonly=lock_data.get("is_readonly", False),
                )

            return locks

        except (OSError, json.JSONDecodeError, KeyError) as e:
            raise ValueError(
                f"Cannot load ADR locks from {self.locks_file}: {e}"
            ) from e

    def save_locks(self, locks: dict[str, ADRLock]) -> None:
        """Save ADR locks to storage.

        Args:
            locks: Dictionary mapping ADR ID to ADRLock
        """
        # Convert locks to serializable format
        locks_data = {}
        for adr_id, lock in locks.items():
            locks_data[adr_id] = {
                "digest": lock.digest,
                "locked_at": lock.locked_at,
                "file_path": lock.file_path,
                "is_readonly": lock.is_readonly,
            }

        # Create locks file structure
        data = {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "generated_by": "ADR Kit v3",
            "locks": locks_data,
        }

        # Atomic write
        temp_file = self.locks_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self.locks_file)

        except OSError as e:
            if temp_file.exists():
                temp_file.unlink()
            raise ValueError(f"Cannot save ADR locks to {self.locks_file}: {e}") from e

    def approve_adr(self, adr: ADR, make_readonly: bool = False) -> ADRLock:
        """Approve an ADR and create immutability lock.

        Args:
            adr: The ADR to approve
            make_readonly: Whether to make the file read-only (chmod 0444)

        Returns:
            ADRLock representing the approved ADR

        Raises:
            ValueError: If ADR cannot be approved
        """
        # Compute content digest
        digest = self.compute_content_digest(adr)

        # Create lock
        lock = ADRLock(
            adr_id=adr.front_matter.id,
            digest=digest,
            locked_at=datetime.now().isoformat(),
            file_path=str(adr.file_path) if adr.file_path else None,
            is_readonly=make_readonly,
        )

        # Load existing locks
        locks = self.load_locks()

        # Add/update lock
        locks[adr.front_matter.id] = lock

        # Save locks
        self.save_locks(locks)

        # Optionally make file read-only
        if make_readonly and adr.file_path and adr.file_path.exists():
            try:
                # Remove write permissions (make read-only)
                adr.file_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                lock.is_readonly = True

                # Update lock with readonly status
                locks[adr.front_matter.id] = lock
                self.save_locks(locks)

            except OSError as e:
                # Log warning but don't fail approval
                print(f"Warning: Could not make {adr.file_path} read-only: {e}")

        return lock

    def is_adr_locked(self, adr_id: str) -> bool:
        """Check if an ADR is locked (approved and immutable).

        Args:
            adr_id: ID of the ADR to check

        Returns:
            True if ADR is locked, False otherwise
        """
        locks = self.load_locks()
        return adr_id in locks

    def get_adr_lock(self, adr_id: str) -> ADRLock | None:
        """Get lock information for an ADR.

        Args:
            adr_id: ID of the ADR

        Returns:
            ADRLock if exists, None otherwise
        """
        locks = self.load_locks()
        return locks.get(adr_id)

    def validate_adr_integrity(self, adr: ADR) -> list[str]:
        """Validate that a locked ADR hasn't been tampered with.

        Args:
            adr: The ADR to validate

        Returns:
            List of integrity violation messages (empty if valid)
        """
        violations: list[str] = []

        # Check if ADR is locked
        lock = self.get_adr_lock(adr.front_matter.id)
        if not lock:
            return violations  # Not locked, no integrity to validate

        # Compute current digest
        current_digest = self.compute_content_digest(adr)

        # Check if digest matches
        if current_digest != lock.digest:
            violations.append(
                f"ADR {adr.front_matter.id} has been modified after approval. "
                f"Approved ADRs are immutable except for status transitions and supersession updates. "
                f"Expected digest: {lock.digest[:8]}..., Current digest: {current_digest[:8]}..."
            )

        return violations

    def get_mutable_fields(self) -> set[str]:
        """Get the set of fields that can be modified after approval.

        Returns:
            Set of field names that remain mutable
        """
        return {
            "status",  # Can transition accepted -> superseded/deprecated
            "superseded_by",  # Managed by supersede workflow
        }

    def can_modify_field(self, adr_id: str, field_name: str) -> bool:
        """Check if a field can be modified for a locked ADR.

        Args:
            adr_id: ID of the ADR
            field_name: Name of the field to check

        Returns:
            True if field can be modified, False otherwise
        """
        if not self.is_adr_locked(adr_id):
            return True  # Not locked, all fields can be modified

        return field_name in self.get_mutable_fields()

    def unlock_adr(self, adr_id: str, reason: str | None = None) -> bool:
        """Unlock an ADR (emergency use only).

        Args:
            adr_id: ID of the ADR to unlock
            reason: Reason for unlocking (for audit trail)

        Returns:
            True if unlocked successfully, False if not locked
        """
        locks = self.load_locks()

        if adr_id not in locks:
            return False

        lock = locks[adr_id]

        # Remove read-only protection if enabled
        if lock.is_readonly and lock.file_path:
            file_path = Path(lock.file_path)
            if file_path.exists():
                try:
                    # Restore write permissions
                    file_path.chmod(
                        stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
                    )
                except OSError as e:
                    print(
                        f"Warning: Could not restore write permissions to {file_path}: {e}"
                    )

        # Remove lock
        del locks[adr_id]
        self.save_locks(locks)

        # Log unlock event (could be extended with proper audit logging)
        print(f"ADR {adr_id} unlocked. Reason: {reason or 'Not specified'}")

        return True
