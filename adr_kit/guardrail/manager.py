"""Main Guardrail Manager - orchestrates automatic configuration application."""

import json
from pathlib import Path
from typing import Any

from ..contract import ConstraintsContractBuilder
from .config_writer import ConfigWriter
from .file_monitor import ChangeEvent, ChangeType, FileMonitor
from .models import (
    ApplicationStatus,
    ApplyResult,
    ConfigFragment,
    ConfigTemplate,
    FragmentTarget,
    FragmentType,
    GuardrailConfig,
)


class GuardrailManager:
    """Main service for automatic guardrail management.

    Orchestrates the application of configuration fragments when
    ADR policies change, implementing the "Guardrail Manager" component
    from the architectural vision.
    """

    def __init__(self, adr_dir: Path, config: GuardrailConfig | None = None):
        self.adr_dir = Path(adr_dir)
        self.config = config or self._create_default_config()

        self.contract_builder = ConstraintsContractBuilder(adr_dir)
        self.config_writer = ConfigWriter(
            backup_enabled=self.config.backup_enabled, backup_dir=self.config.backup_dir
        )
        self.file_monitor = FileMonitor(adr_dir)

        self._last_contract_hash = ""

    def _create_default_config(self) -> GuardrailConfig:
        """Create default guardrail configuration."""

        # Default targets for common configuration files
        targets = [
            FragmentTarget(
                file_path=Path(".eslintrc.adrs.json"), fragment_type=FragmentType.ESLINT
            ),
            FragmentTarget(
                file_path=Path("pyproject.toml"),
                fragment_type=FragmentType.RUFF,
                section_name="tool.ruff",
            ),
            FragmentTarget(
                file_path=Path(".import-linter.adrs.ini"),
                fragment_type=FragmentType.IMPORT_LINTER,
            ),
        ]

        # Default templates
        templates = [
            ConfigTemplate(
                fragment_type=FragmentType.ESLINT,
                template_content="""{
  "rules": {
    "no-restricted-imports": [
      "error",
      {
        "paths": [
          {disallow_rules}
        ]
      }
    ]
  }
}""",
                variables={"disallow_rules": "[]"},
            ),
            ConfigTemplate(
                fragment_type=FragmentType.RUFF,
                template_content="""[tool.ruff.flake8-banned-api]
banned-api = [
{disallow_imports}
]""",
                variables={"disallow_imports": ""},
            ),
        ]

        return GuardrailConfig(targets=targets, templates=templates)

    def apply_guardrails(self, force: bool = False) -> list[ApplyResult]:
        """Apply guardrails based on current ADR policies."""

        results: list[ApplyResult] = []

        if not self.config.enabled:
            return results

        # Build current constraints contract
        try:
            contract = self.contract_builder.build_contract(force_rebuild=force)
        except Exception as e:
            # If contract building fails, skip guardrail application
            return [
                ApplyResult(
                    target=target,
                    status=ApplicationStatus.FAILED,
                    message=f"Failed to build constraints contract: {e}",
                )
                for target in self.config.targets
            ]

        # Check if contract has changed (optimization)
        if not force and contract.metadata.hash == self._last_contract_hash:
            return results  # No changes needed

        # Generate fragments for each target type
        fragment_map = self._generate_fragments(contract)

        # Apply fragments to each target
        for target in self.config.targets:
            if target.fragment_type in fragment_map:
                fragments = fragment_map[target.fragment_type]
                if fragments or self.config_writer.has_managed_section(target):
                    # Apply fragments (or remove section if no fragments)
                    result = self.config_writer.apply_fragments(target, fragments)
                    results.append(result)

        # Update contract hash
        self._last_contract_hash = contract.metadata.hash

        return results

    def watch_and_apply(self) -> list[ApplyResult]:
        """Watch for ADR changes and apply guardrails automatically."""

        results: list[ApplyResult] = []

        if not self.config.auto_apply:
            return results

        # Detect changes
        changes = self.file_monitor.detect_changes()
        policy_changes = self.file_monitor.get_policy_relevant_changes(changes)

        if policy_changes:
            # Apply guardrails due to policy changes
            results = self.apply_guardrails(force=False)

            # Log changes for audit
            self._log_policy_changes(policy_changes, results)

        return results

    def _generate_fragments(
        self, contract: Any
    ) -> dict[FragmentType, list[ConfigFragment]]:
        """Generate configuration fragments from constraints contract."""

        fragments: dict[FragmentType, list[ConfigFragment]] = {
            FragmentType.ESLINT: [],
            FragmentType.RUFF: [],
            FragmentType.IMPORT_LINTER: [],
        }

        if contract.constraints.is_empty():
            return fragments

        # Generate ESLint fragments
        if contract.constraints.imports:
            eslint_fragment = self._generate_eslint_fragment(contract)
            if eslint_fragment:
                fragments[FragmentType.ESLINT].append(eslint_fragment)

        # Generate Ruff fragments
        if contract.constraints.python and contract.constraints.python.disallow_imports:
            ruff_fragment = self._generate_ruff_fragment(contract)
            if ruff_fragment:
                fragments[FragmentType.RUFF].append(ruff_fragment)

        # Generate import-linter fragments
        if contract.constraints.boundaries:
            import_linter_fragment = self._generate_import_linter_fragment(contract)
            if import_linter_fragment:
                fragments[FragmentType.IMPORT_LINTER].append(import_linter_fragment)

        return fragments

    def _generate_eslint_fragment(self, contract: Any) -> ConfigFragment | None:
        """Generate ESLint configuration fragment."""

        if (
            not contract.constraints.imports
            or not contract.constraints.imports.disallow
        ):
            return None

        # Build disallow rules
        disallow_rules = []
        for item in contract.constraints.imports.disallow:
            # Find source ADRs for this constraint by checking rule paths
            source_adrs = []
            for adr_id, provenance in contract.provenance.items():
                # Check if this provenance rule matches our import constraint
                if f"imports.disallow.{item}" in provenance.rule_path:
                    source_adrs.append(adr_id)

            adr_refs = f" ({', '.join(source_adrs)})" if source_adrs else ""
            rule = {
                "name": item,
                "message": f"Use approved alternative instead{adr_refs}",
            }
            disallow_rules.append(json.dumps(rule))

        # Use template to generate content
        template = self.config.get_template_for_type(FragmentType.ESLINT)
        if template:
            content = template.render(
                disallow_rules=",\n          ".join(disallow_rules)
            )
        else:
            # Fallback content generation
            content = f"""{{
  "rules": {{
    "no-restricted-imports": [
      "error",
      {{
        "paths": [
          {",".join(disallow_rules)}
        ]
      }}
    ]
  }}
}}"""

        return ConfigFragment(
            fragment_type=FragmentType.ESLINT,
            content=content,
            source_adr_ids=list(contract.provenance.keys()),
        )

    def _generate_ruff_fragment(self, contract: Any) -> ConfigFragment | None:
        """Generate Ruff configuration fragment."""

        if (
            not contract.constraints.python
            or not contract.constraints.python.disallow_imports
        ):
            return None

        # Build banned import rules
        banned_imports = []
        for item in contract.constraints.python.disallow_imports:
            # Find source ADRs by checking rule paths
            source_adrs = []
            for adr_id, provenance in contract.provenance.items():
                if f"python.disallow_imports.{item}" in provenance.rule_path:
                    source_adrs.append(adr_id)

            adr_refs = f" ({', '.join(source_adrs)})" if source_adrs else ""
            rule = f'    "{item} = Use approved alternative instead{adr_refs}"'
            banned_imports.append(rule)

        # Use template to generate content
        template = self.config.get_template_for_type(FragmentType.RUFF)
        if template:
            content = template.render(disallow_imports=",\n".join(banned_imports))
        else:
            # Fallback content generation
            content = f"""[tool.ruff.flake8-banned-api]
banned-api = [
{",".join(banned_imports)}
]"""

        return ConfigFragment(
            fragment_type=FragmentType.RUFF,
            content=content,
            source_adr_ids=list(contract.provenance.keys()),
        )

    def _generate_import_linter_fragment(self, contract: Any) -> ConfigFragment | None:
        """Generate import-linter configuration fragment."""

        if (
            not contract.constraints.boundaries
            or not contract.constraints.boundaries.rules
        ):
            return None

        # Build import-linter contracts
        contracts = []
        for i, rule in enumerate(contract.constraints.boundaries.rules):
            contract_name = f"adr-boundary-{i+1}"
            contracts.append(
                f"""[contracts.{contract_name}]
name = "ADR Boundary Rule"
type = "forbidden"
source_modules = ["**"]
forbidden_modules = ["{rule.forbid}"]"""
            )

        content = "\n\n".join(contracts)

        return ConfigFragment(
            fragment_type=FragmentType.IMPORT_LINTER,
            content=content,
            source_adr_ids=list(contract.provenance.keys()),
        )

    def _log_policy_changes(
        self, changes: list[ChangeEvent], results: list[ApplyResult]
    ) -> None:
        """Log policy changes for audit purposes."""

        if not self.config.notify_on_apply:
            return

        # Simple logging - could be enhanced with structured logging
        print(f"🔧 ADR-Kit: Applied guardrails due to {len(changes)} policy changes:")

        for change in changes:
            if change.change_type == ChangeType.STATUS_CHANGED:
                print(f"  - {change.adr_id}: {change.old_status} → {change.new_status}")
            elif change.change_type == ChangeType.POLICY_CHANGED:
                print(f"  - {change.adr_id}: Policy updated")
            elif change.change_type == ChangeType.CREATED:
                print(f"  - New ADR: {change.file_path.name}")

        success_count = len(
            [r for r in results if r.status == ApplicationStatus.SUCCESS]
        )
        print(f"  ✅ {success_count}/{len(results)} configurations updated")

    def remove_all_guardrails(self) -> list[ApplyResult]:
        """Remove all managed guardrail sections from target files."""

        results = []

        for target in self.config.targets:
            if self.config_writer.has_managed_section(target):
                result = self.config_writer.remove_managed_sections(target)
                results.append(result)

        return results

    def get_status(self) -> dict[str, Any]:
        """Get current status of the guardrail management system."""

        try:
            contract = self.contract_builder.build_contract()
            contract_valid = True
            constraint_count = (
                len(contract.constraints.imports.disallow or [])
                if contract.constraints.imports
                else (
                    0 + len(contract.constraints.imports.prefer or [])
                    if contract.constraints.imports
                    else (
                        0 + len(contract.constraints.boundaries.rules or [])
                        if contract.constraints.boundaries
                        else (
                            0 + len(contract.constraints.python.disallow_imports or [])
                            if contract.constraints.python
                            else 0
                        )
                    )
                )
            )
        except Exception:
            contract_valid = False
            constraint_count = 0

        # Check target file status
        target_status = {}
        for target in self.config.targets:
            target_status[str(target.file_path)] = {
                "exists": target.file_path.exists(),
                "has_managed_section": (
                    self.config_writer.has_managed_section(target)
                    if target.file_path.exists()
                    else False
                ),
                "fragment_type": target.fragment_type.value,
            }

        return {
            "enabled": self.config.enabled,
            "auto_apply": self.config.auto_apply,
            "contract_valid": contract_valid,
            "active_constraints": constraint_count,
            "target_count": len(self.config.targets),
            "targets": target_status,
            "last_contract_hash": self._last_contract_hash,
        }
