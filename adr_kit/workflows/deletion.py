"""Workflow for safe ADR deletion with immutability protection."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.immutability import ImmutabilityManager
from ..core.model import ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from ..index.json_index import generate_adr_index
from .base import BaseWorkflow, WorkflowError, WorkflowResult, WorkflowStatus

logger = logging.getLogger(__name__)


@dataclass
class DeletionInput:
    """Input data for ADR deletion workflow."""

    adr_id: str
    force: bool = False
    reason: str | None = None


class DeletionWorkflow(BaseWorkflow):
    """Workflow for safely deleting ADRs with immutability protection.

    Implements the following protection rules:
    1. PROPOSED ADRs: Can be deleted freely (with confirmation)
    2. ACCEPTED ADRs: Cannot be deleted (suggest supersede/deprecate)
    3. SUPERSEDED ADRs: Cannot be deleted (historical record)
    4. DEPRECATED ADRs: Cannot be deleted (historical record)
    5. REJECTED ADRs: Can be deleted (with confirmation)

    With --force flag: Allows deletion of any ADR with explicit confirmation.
    """

    def __init__(self, adr_dir: Path | str, project_root: Path | None = None):
        super().__init__(adr_dir)
        self.project_root = project_root or Path.cwd()
        self.immutability_mgr = ImmutabilityManager(self.project_root)

    def execute(self, **kwargs: Any) -> WorkflowResult:
        """Execute safe ADR deletion workflow.

        Args:
            **kwargs: Must include ``input_data`` (:class:`DeletionInput`).

        Returns:
            WorkflowResult with deletion status and guidance
        """
        input_data: DeletionInput = kwargs["input_data"]
        self._start_workflow("ADR Deletion")

        try:
            # Step 1: Validate ADR directory
            self._execute_step("Validate ADR directory", self._validate_adr_directory)

            # Step 2: Find the ADR file
            adr, file_path = self._execute_step(
                "Find ADR file", self._find_adr_file, input_data.adr_id
            )

            # Step 3: Check deletion permissions
            can_delete, reason = self._execute_step(
                "Check deletion permissions",
                self._check_deletion_permissions,
                adr,
                input_data.force,
            )

            if not can_delete:
                # Deletion blocked - return guidance
                self._complete_workflow(
                    success=False,
                    message=reason,
                    status=WorkflowStatus.VALIDATION_ERROR,
                )
                self._add_agent_guidance(
                    guidance=self._get_blocking_guidance(adr.status),
                    next_steps=self._get_blocking_next_steps(
                        adr.status, input_data.adr_id
                    ),
                )
                # Get status value safely
                status_value = (
                    adr.status.value
                    if isinstance(adr.status, ADRStatus)
                    else str(adr.status)
                )
                self._set_workflow_data(
                    adr_id=input_data.adr_id,
                    status=status_value,
                    file_path=str(file_path),
                    deletion_allowed=False,
                    blocking_reason=reason,
                )
                return self.result

            # Step 4: Check for relationships
            relationship_warnings = self._execute_step(
                "Check ADR relationships",
                self._check_relationships,
                adr,
                input_data.adr_id,
            )

            # Step 5: Delete the ADR file
            self._execute_step(
                "Delete ADR file", self._delete_adr_file, file_path, input_data.adr_id
            )

            # Step 6: Update immutability locks (if locked)
            if self.immutability_mgr.is_adr_locked(input_data.adr_id):
                self._execute_step(
                    "Remove immutability lock",
                    self._remove_immutability_lock,
                    input_data.adr_id,
                    input_data.reason,
                )

            # Step 7: Regenerate index
            self._execute_step("Regenerate ADR index", self._regenerate_index)

            # Success
            message = f"Successfully deleted ADR {input_data.adr_id}"
            if input_data.force:
                message += " (forced deletion)"

            self._complete_workflow(
                success=True, message=message, status=WorkflowStatus.SUCCESS
            )

            self._add_agent_guidance(
                guidance="ADR has been deleted and index updated.",
                next_steps=[
                    "Review index to confirm removal",
                    "Check for any broken references in other ADRs",
                    "Consider rebuilding constraints contract if needed",
                ],
            )

            self._set_workflow_data(
                adr_id=input_data.adr_id,
                deleted_file=str(file_path),
                was_forced=input_data.force,
                warnings=relationship_warnings,
            )

            # Add warnings about relationships
            for warning in relationship_warnings:
                self.result.add_warning(warning)

            return self.result

        except WorkflowError as e:
            self._complete_workflow(
                success=False,
                message=f"Deletion failed: {e.message}",
                status=WorkflowStatus.FAILED,
            )
            self.result.add_error(e.message)
            return self.result

        except Exception as e:
            logger.error(f"Unexpected error in deletion workflow: {e}")
            self._complete_workflow(
                success=False,
                message=f"Deletion failed: {str(e)}",
                status=WorkflowStatus.FAILED,
            )
            self.result.add_error(str(e))
            return self.result

    def _find_adr_file(self, adr_id: str) -> tuple[Any, Path]:
        """Find the ADR file by ID.

        Args:
            adr_id: ADR ID to find

        Returns:
            Tuple of (ADR object, file path)

        Raises:
            WorkflowError: If ADR not found
        """
        adr_files = find_adr_files(self.adr_dir)

        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr and adr.front_matter.id == adr_id:
                    return adr, file_path
            except ParseError:
                continue

        raise WorkflowError(f"ADR with ID '{adr_id}' not found in {self.adr_dir}")

    def _check_deletion_permissions(self, adr: Any, force: bool) -> tuple[bool, str]:
        """Check if ADR can be deleted.

        Args:
            adr: ADR object to check
            force: Whether force deletion is enabled

        Returns:
            Tuple of (can_delete: bool, reason: str)
        """
        status = adr.status

        # Ensure status is ADRStatus enum (handle both enum and string)
        if isinstance(status, str):
            try:
                status = ADRStatus(status)
            except ValueError:
                return (False, f"Cannot delete ADR with unknown status: {status}")

        # Get status value for messages
        status_value = status.value if isinstance(status, ADRStatus) else str(status)

        # Force flag allows deletion of any ADR
        if force:
            return (
                True,
                f"Forced deletion allowed for {status_value} ADR (requires explicit confirmation)",
            )

        # PROPOSED and REJECTED ADRs can be deleted freely
        if status in (ADRStatus.PROPOSED, ADRStatus.REJECTED):
            return (True, f"{status_value.capitalize()} ADRs can be deleted")

        # ACCEPTED, SUPERSEDED, DEPRECATED ADRs cannot be deleted (immutability principle)
        if status in (ADRStatus.ACCEPTED, ADRStatus.SUPERSEDED, ADRStatus.DEPRECATED):
            reason = (
                f"Cannot delete {status_value} ADR (immutability principle). "
                f"{status_value.capitalize()} ADRs represent historical decisions and must be preserved."
            )
            return (False, reason)

        # Unknown status - be conservative and block
        return (False, f"Cannot delete ADR with unknown status: {status_value}")

    def _check_relationships(self, adr: Any, adr_id: str) -> list[str]:
        """Check for relationships that might be broken by deletion.

        Args:
            adr: ADR object being deleted
            adr_id: ADR ID being deleted

        Returns:
            List of warning messages about broken relationships
        """
        warnings: list[str] = []

        # Check if this ADR supersedes others
        if adr.supersedes:
            for superseded_id in adr.supersedes:
                warnings.append(
                    f"Warning: ADR {adr_id} supersedes {superseded_id}. "
                    f"Deleting this ADR will orphan the supersession relationship."
                )

        # Check if this ADR is superseded by others
        if adr.superseded_by:
            for superseding_id in adr.superseded_by:
                warnings.append(
                    f"Warning: ADR {adr_id} is superseded by {superseding_id}. "
                    f"Deleting this ADR will create a broken reference."
                )

        # Check if other ADRs reference this one
        all_adr_files = find_adr_files(self.adr_dir)
        for file_path in all_adr_files:
            try:
                other_adr = parse_adr_file(file_path, strict=False)
                if not other_adr or other_adr.id == adr_id:
                    continue

                # Check if other ADR supersedes this one
                if other_adr.supersedes and adr_id in other_adr.supersedes:
                    warnings.append(
                        f"Warning: ADR {other_adr.id} supersedes this ADR. "
                        f"You should update {other_adr.id} after deletion."
                    )

                # Check if other ADR is superseded by this one
                if other_adr.superseded_by and adr_id in other_adr.superseded_by:
                    warnings.append(
                        f"Warning: ADR {other_adr.id} references this ADR as superseding it. "
                        f"You should update {other_adr.id} after deletion."
                    )

            except ParseError:
                continue

        return warnings

    def _delete_adr_file(self, file_path: Path, adr_id: str) -> None:
        """Delete the ADR file from disk.

        Args:
            file_path: Path to ADR file
            adr_id: ADR ID (for error messages)

        Raises:
            WorkflowError: If deletion fails
        """
        try:
            # Check if file is read-only (from immutability lock)
            if not file_path.exists():
                raise WorkflowError(f"ADR file does not exist: {file_path}")

            # Try to delete
            file_path.unlink()
            logger.info(f"Deleted ADR file: {file_path}")

        except PermissionError as e:
            raise WorkflowError(
                f"Cannot delete {file_path}: Permission denied. "
                f"File may be read-only from immutability lock. "
                f"Try unlocking first or use force flag."
            ) from e

        except Exception as e:
            raise WorkflowError(f"Failed to delete ADR file: {e}") from e

    def _remove_immutability_lock(self, adr_id: str, reason: str | None) -> None:
        """Remove immutability lock for deleted ADR.

        Args:
            adr_id: ADR ID
            reason: Reason for unlocking (for audit trail)
        """
        reason_msg = reason or "ADR deleted"
        success = self.immutability_mgr.unlock_adr(adr_id, reason=reason_msg)

        if success:
            logger.info(f"Removed immutability lock for {adr_id}")
        else:
            logger.warning(f"No immutability lock found for {adr_id}")

    def _regenerate_index(self) -> None:
        """Regenerate ADR index after deletion.

        Raises:
            WorkflowError: If index regeneration fails
        """
        try:
            index_path = self.adr_dir / "adr-index.json"
            generate_adr_index(self.adr_dir, index_path, validate=False)
            logger.info(f"Regenerated ADR index at {index_path}")

        except Exception as e:
            raise WorkflowError(f"Failed to regenerate index: {e}") from e

    def _get_blocking_guidance(self, status: ADRStatus | str) -> str:
        """Get guidance message when deletion is blocked.

        Args:
            status: Status of the ADR that blocks deletion

        Returns:
            Guidance message for the agent
        """
        # Ensure status is ADRStatus enum
        if isinstance(status, str):
            try:
                status = ADRStatus(status)
            except ValueError:
                pass  # Use as-is if can't convert

        if status == ADRStatus.ACCEPTED or (
            isinstance(status, str) and status == "accepted"
        ):
            return (
                "Accepted ADRs cannot be deleted due to the immutability principle. "
                "Architectural decisions must be preserved for audit trail and historical context. "
                "To retire this decision, use supersede (replace with new ADR) or deprecate (soft retirement)."
            )
        elif status == ADRStatus.SUPERSEDED or (
            isinstance(status, str) and status == "superseded"
        ):
            return (
                "Superseded ADRs cannot be deleted as they are part of the decision history. "
                "They provide context for why decisions changed and must be preserved for audit trail."
            )
        elif status == ADRStatus.DEPRECATED or (
            isinstance(status, str) and status == "deprecated"
        ):
            return (
                "Deprecated ADRs cannot be deleted as they document historical decisions. "
                "They explain why certain approaches are no longer recommended and must be preserved."
            )
        else:
            return (
                "This ADR cannot be deleted. Use --force flag only if absolutely necessary "
                "and you understand the implications for audit trail and decision history."
            )

    def _get_blocking_next_steps(
        self, status: ADRStatus | str, adr_id: str
    ) -> list[str]:
        """Get next steps when deletion is blocked.

        Args:
            status: Status of the ADR
            adr_id: ADR ID

        Returns:
            List of suggested next steps
        """
        # Ensure status is ADRStatus enum
        if isinstance(status, str):
            try:
                status = ADRStatus(status)
            except ValueError:
                pass  # Use as-is if can't convert

        if status == ADRStatus.ACCEPTED or (
            isinstance(status, str) and status == "accepted"
        ):
            return [
                f"To replace this decision: Use adr_supersede to create a new ADR that supersedes {adr_id}",
                f"To soft-retire: Use adr_deprecate (if available) to mark {adr_id} as deprecated",
                "Only use --force flag if you have a specific reason to delete an accepted ADR",
            ]
        elif status in (ADRStatus.SUPERSEDED, ADRStatus.DEPRECATED) or (
            isinstance(status, str) and status in ("superseded", "deprecated")
        ):
            return [
                "Superseded/deprecated ADRs should be kept for historical context",
                "If you must delete for a specific reason, use the --force flag",
                "Consider that deleting may break audit trails and decision history",
            ]
        else:
            return [
                "Review the ADR status and confirm deletion is appropriate",
                "Use --force flag if deletion is necessary despite the status",
            ]
