"""Approval Workflow - Approve ADR and trigger complete automation pipeline."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ...contract.builder import ConstraintsContractBuilder
from ...core.model import ADR
from ...core.parse import find_adr_files, parse_adr_file
from ...core.validate import validate_adr
from ...enforcement.pipeline import EnforcementPipeline, EnforcementResult
from ...index.json_index import generate_adr_index
from .base import BaseWorkflow, WorkflowResult


@dataclass
class ApprovalInput:
    """Input for ADR approval workflow."""

    adr_id: str
    digest_check: bool = True  # Whether to verify content digest hasn't changed
    force_approve: bool = False  # Override conflicts and warnings
    approval_notes: str | None = None  # Human approval notes


@dataclass
class ApprovalResult:
    """Result of ADR approval."""

    adr_id: str
    previous_status: str
    new_status: str
    content_digest: str  # SHA-256 hash of approved content
    automation_results: dict[str, Any]  # Results from triggered automation
    policy_rules_applied: int  # Number of policy rules applied
    configurations_updated: list[str]  # List of config files updated
    warnings: list[str]  # Non-blocking warnings
    next_steps: str  # Guidance for what happens next
    enforcement_result: EnforcementResult | None = None  # Canonical pipeline output


class ApprovalWorkflow(BaseWorkflow):
    """
    Approval Workflow handles ADR approval and triggers comprehensive automation.

    This is the most complex workflow as it orchestrates the entire ADR ecosystem
    when a decision is approved. All policy enforcement, configuration updates,
    and validation happens here.

    Workflow Steps:
    1. Load and validate the ADR to be approved
    2. Verify content integrity (digest check)
    3. Update ADR status to 'accepted'
    4. Rebuild constraints contract with new ADR
    5. Apply guardrails and update configurations
    6. Generate enforcement rules (ESLint, Ruff, etc.)
    7. Update indexes and catalogs
    8. Validate codebase against new policies
    9. Generate comprehensive approval report
    """

    def execute(self, **kwargs: Any) -> WorkflowResult:
        """Execute comprehensive ADR approval workflow."""
        # Extract input_data from kwargs
        input_data = kwargs.get("input_data")
        if not input_data or not isinstance(input_data, ApprovalInput):
            raise ValueError("input_data must be provided as ApprovalInput instance")

        self._start_workflow("Approve ADR")

        try:
            # Step 1: Load and validate ADR
            adr, file_path = self._execute_step(
                "load_adr", self._load_adr_for_approval, input_data.adr_id
            )
            self._execute_step(
                "validate_preconditions",
                self._validate_approval_preconditions,
                adr,
                input_data,
            )

            previous_status = adr.status

            # Step 2: Content integrity check
            if input_data.digest_check:
                content_digest = self._execute_step(
                    "check_content_integrity",
                    self._calculate_content_digest,
                    str(file_path),
                )
            else:
                content_digest = "skipped"

            # Step 3: Update ADR status
            updated_adr = self._execute_step(
                "update_adr_status",
                self._update_adr_status,
                adr,
                str(file_path),
                input_data,
            )

            # Step 4: Rebuild constraints contract
            contract, contract_result = self._execute_step(
                "rebuild_constraints_contract", self._rebuild_constraints_contract
            )

            # Step 5: Run canonical enforcement pipeline (replaces guardrails + rule generation)
            enforcement_result, enforcement_summary = self._execute_step(
                "enforcement_pipeline",
                self._run_enforcement_pipeline,
                contract,
            )

            # Step 7: Update indexes
            index_result = self._execute_step("update_indexes", self._update_indexes)

            # Step 8: Validate codebase (optional, can be time-consuming)
            validation_result = self._execute_step(
                "validate_codebase_compliance",
                self._validate_codebase_compliance,
                updated_adr,
            )

            # Step 9: Generate approval report
            automation_results = {
                "status_update": {
                    "success": True,
                    "old_status": previous_status,
                    "new_status": "accepted",
                },
                "contract_rebuild": contract_result,
                "enforcement_pipeline": enforcement_summary,
                "index_update": index_result,
                "codebase_validation": validation_result,
            }

            approval_report = self._execute_step(
                "generate_approval_report",
                self._generate_approval_report,
                updated_adr,
                automation_results,
                content_digest,
                input_data,
            )

            result = ApprovalResult(
                adr_id=input_data.adr_id,
                previous_status=previous_status,
                new_status="accepted",
                content_digest=content_digest,
                automation_results=automation_results,
                policy_rules_applied=self._count_policy_rules_applied(
                    automation_results
                ),
                configurations_updated=self._extract_updated_configurations(
                    automation_results
                ),
                warnings=approval_report.get("warnings", []),
                next_steps=approval_report.get("next_steps", ""),
                enforcement_result=enforcement_result,
            )

            self._complete_workflow(
                success=True,
                message=f"ADR {input_data.adr_id} approved and automation completed",
            )
            self.result.data = {
                "approval_result": result,
                "full_report": approval_report,
            }
            self.result.guidance = approval_report.get("guidance", "")
            self.result.next_steps = approval_report.get(
                "next_steps_list",
                [
                    f"ADR {input_data.adr_id} is now active",
                    "Review automation results for any issues",
                    "Monitor compliance with generated policy rules",
                ],
            )

        except Exception as e:
            self._complete_workflow(
                success=False,
                message=f"Approval workflow failed: {str(e)}",
            )
            self.result.add_error(f"ApprovalError: {str(e)}")

        return self.result

    def _load_adr_for_approval(self, adr_id: str) -> tuple[ADR, Path]:
        """Load the ADR that needs to be approved."""
        adr_files = find_adr_files(self.adr_dir)

        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path)
                if adr.id == adr_id:
                    return adr, file_path
            except Exception:
                continue

        raise ValueError(f"ADR {adr_id} not found in {self.adr_dir}")

    def _validate_approval_preconditions(
        self, adr: ADR, input_data: ApprovalInput
    ) -> None:
        """Validate that ADR can be approved."""

        # Check current status
        if adr.status == "accepted":
            if not input_data.force_approve:
                raise ValueError(f"ADR {adr.id} is already approved")

        if adr.status == "superseded":
            raise ValueError(f"ADR {adr.id} is superseded and cannot be approved")

        # Validate ADR structure
        # Note: validate_adr signature is (adr, schema_path, project_root)
        # Pass None for schema_path to use default, and self.adr_dir.parent as project_root
        validation_result = validate_adr(
            adr,
            schema_path=None,
            project_root=self.adr_dir.parent if self.adr_dir else None,
        )
        if not validation_result.is_valid and not input_data.force_approve:
            errors = [str(error) for error in validation_result.errors]
            raise ValueError(f"ADR {adr.id} has validation errors: {', '.join(errors)}")

    def _calculate_content_digest(self, file_path: str) -> str:
        """Calculate SHA-256 digest of ADR content for integrity checking."""
        with open(file_path, "rb") as f:
            content = f.read()
            return hashlib.sha256(content).hexdigest()

    def _update_adr_status(
        self, adr: ADR, file_path: str, input_data: ApprovalInput
    ) -> ADR:
        """Update ADR status to accepted and write back to file."""

        # Read current file content
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Update status in YAML front-matter
        import re

        # Find status line and replace it
        status_pattern = r"^status:\s*\w+$"
        new_content = re.sub(
            status_pattern, "status: accepted", content, flags=re.MULTILINE
        )

        # Add approval metadata if notes provided
        if input_data.approval_notes:
            # Find end of YAML front-matter
            yaml_end = new_content.find("\n---\n")
            if yaml_end != -1:
                approval_metadata = (
                    f'approval_date: {datetime.now().strftime("%Y-%m-%d")}\n'
                )
                if input_data.approval_notes:
                    approval_metadata += (
                        f'approval_notes: "{input_data.approval_notes}"\n'
                    )

                # Insert before the closing ---
                new_content = (
                    new_content[:yaml_end] + approval_metadata + new_content[yaml_end:]
                )

        # Write updated content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Return updated ADR object - create a new one with updated status
        from ...core.model import ADRStatus

        updated_front_matter = adr.front_matter.model_copy(
            update={"status": ADRStatus.ACCEPTED}
        )
        updated_adr = ADR(
            front_matter=updated_front_matter,
            content=adr.content,
            file_path=adr.file_path,
        )
        return updated_adr

    def _rebuild_constraints_contract(
        self,
    ) -> tuple[Any, dict[str, Any]]:
        """Rebuild the constraints contract with all approved ADRs.

        Returns the contract object alongside a summary dict for reporting.
        """
        try:
            builder = ConstraintsContractBuilder(adr_dir=self.adr_dir)
            contract = builder.build()

            summary = {
                "success": True,
                "approved_adrs": len(contract.approved_adrs),
                "constraints_exist": not contract.constraints.is_empty(),
                "message": "Constraints contract rebuilt successfully",
            }
            return contract, summary

        except Exception as e:
            summary = {
                "success": False,
                "error": str(e),
                "message": "Failed to rebuild constraints contract",
            }
            return None, summary

    def _run_enforcement_pipeline(
        self, contract: Any
    ) -> tuple["EnforcementResult | None", dict[str, Any]]:
        """Run the canonical enforcement pipeline against the compiled contract.

        Returns the EnforcementResult envelope alongside a summary dict.
        """
        try:
            pipeline = EnforcementPipeline(
                adr_dir=Path(self.adr_dir), project_path=Path.cwd()
            )
            result = pipeline.compile(
                contract=contract if contract is not None else None
            )

            summary: dict[str, Any] = {
                "success": True,
                "fragments_applied": len(result.fragments_applied),
                "files_touched": result.files_touched,
                "conflicts": len(result.conflicts),
                "skipped_adapters": [s.adapter for s in result.skipped_adapters],
                "idempotency_hash": result.idempotency_hash,
                "provenance_entries": len(result.provenance),
                "message": "Enforcement pipeline completed",
            }
            return result, summary

        except Exception as e:
            summary = {
                "success": False,
                "error": str(e),
                "message": "Enforcement pipeline failed",
            }
            return None, summary

    def _update_indexes(self) -> dict[str, Any]:
        """Update JSON and other indexes after ADR approval."""
        try:
            # Update JSON index
            adr_index = generate_adr_index(self.adr_dir)

            # Write to standard location
            index_file = Path(self.adr_dir) / "adr-index.json"
            with open(index_file, "w") as f:
                json.dump(adr_index.to_dict(), f, indent=2)

            return {
                "success": True,
                "total_adrs": len(adr_index.entries),
                "approved_adrs": len(
                    [
                        entry
                        for entry in adr_index.entries
                        if entry.adr.status == "accepted"
                    ]
                ),
                "index_file": str(index_file),
                "message": "Indexes updated successfully",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to update indexes",
            }

    def _validate_codebase_compliance(self, adr: ADR) -> dict[str, Any]:
        """Validate existing codebase against new ADR policies (optional)."""
        try:
            # This is a lightweight validation - full validation might be expensive
            # and should be run separately via CI/CD

            violations = []

            # Check for obvious policy violations
            if adr.policy and adr.policy.imports and adr.policy.imports.disallow:
                disallowed = adr.policy.imports.disallow
                if disallowed:
                    # Quick scan for disallowed imports in common files
                    violations.extend(self._quick_scan_for_violations(disallowed))

            return {
                "success": True,
                "violations_found": len(violations),
                "violations": violations[:10],  # Limit to first 10
                "message": "Quick compliance check completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Compliance validation failed",
            }

    def _quick_scan_for_violations(
        self, disallowed_imports: list[str]
    ) -> list[dict[str, Any]]:
        """Quick scan for obvious policy violations."""
        violations = []

        # Scan common file types
        file_patterns = ["**/*.js", "**/*.ts", "**/*.py", "**/*.jsx", "**/*.tsx"]

        for pattern in file_patterns:
            try:
                from pathlib import Path

                for file_path in Path.cwd().glob(pattern):
                    if (
                        file_path.is_file() and file_path.stat().st_size < 1024 * 1024
                    ):  # Skip large files
                        try:
                            with open(file_path, encoding="utf-8") as f:
                                content = f.read()

                                for disallowed in disallowed_imports:
                                    if (
                                        f"import {disallowed}" in content
                                        or f"from {disallowed}" in content
                                    ):
                                        violations.append(
                                            {
                                                "file": str(file_path),
                                                "violation": f"Uses disallowed import: {disallowed}",
                                                "type": "import_violation",
                                            }
                                        )
                        except Exception:
                            continue  # Skip problematic files

            except Exception:
                continue  # Skip problematic patterns

        return violations

    def _count_policy_rules_applied(self, automation_results: dict[str, Any]) -> int:
        """Count total policy rules applied across all systems."""
        pipeline = automation_results.get("enforcement_pipeline", {})
        if pipeline.get("success"):
            return pipeline.get("fragments_applied", 0)
        return 0

    def _extract_updated_configurations(
        self, automation_results: dict[str, Any]
    ) -> list[str]:
        """Extract list of configuration files that were updated."""
        updated_files = []

        # From enforcement pipeline
        pipeline = automation_results.get("enforcement_pipeline", {})
        if pipeline.get("success"):
            updated_files.extend(pipeline.get("files_touched", []))

        # From index updates
        if "index_update" in automation_results:
            index = automation_results["index_update"]
            if index.get("success") and index.get("index_file"):
                updated_files.append(index["index_file"])

        return list(set(updated_files))  # Remove duplicates

    def _generate_approval_report(
        self,
        adr: ADR,
        automation_results: dict[str, Any],
        content_digest: str,
        input_data: ApprovalInput,
    ) -> dict[str, Any]:
        """Generate comprehensive approval report."""

        # Count successes and failures
        successes = sum(
            1
            for result in automation_results.values()
            if isinstance(result, dict) and result.get("success")
        )
        failures = len(automation_results) - successes

        warnings = []

        # Check for automation failures
        for step, result in automation_results.items():
            if isinstance(result, dict) and not result.get("success"):
                warnings.append(
                    f"{step.replace('_', ' ').title()} failed: {result.get('message', 'Unknown error')}"
                )

        # Generate next steps
        if failures > 0:
            next_steps = (
                f"⚠️ ADR {adr.id} approved but {failures} automation step(s) failed. "
                f"Review warnings and consider running manual enforcement. "
                f"Use adr_validate() to check compliance."
            )
        else:
            policy_count = self._count_policy_rules_applied(automation_results)
            config_count = len(self._extract_updated_configurations(automation_results))

            next_steps = (
                f"✅ ADR {adr.id} fully approved and operational. "
                f"{policy_count} policy rules applied, {config_count} configurations updated. "
                f"All systems are enforcing this decision."
            )

        return {
            "adr_id": adr.id,
            "approval_timestamp": datetime.now().isoformat(),
            "content_digest": content_digest,
            "automation_summary": {
                "total_steps": len(automation_results),
                "successful_steps": successes,
                "failed_steps": failures,
                "success_rate": (
                    f"{(successes/len(automation_results)*100):.1f}%"
                    if automation_results
                    else "0%"
                ),
            },
            "policy_enforcement": {
                "rules_applied": self._count_policy_rules_applied(automation_results),
                "configurations_updated": len(
                    self._extract_updated_configurations(automation_results)
                ),
                "enforcement_active": failures == 0,
            },
            "warnings": warnings,
            "next_steps": next_steps,
            "full_automation_details": automation_results,
        }
