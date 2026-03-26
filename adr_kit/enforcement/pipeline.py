"""Canonical Enforcement Pipeline.

Single entry point for all enforcement compilation. Reads from the compiled
ConstraintsContract and never from raw ADRs. Produces a stable EnforcementResult
audit artifact on every run.

Pipeline stages:
  1. Read MergedConstraints from the contract
  2. Detect project technology stack
  3. Route via PolicyRouter → select adapters for the detected stack
  4. Run selected adapters → collect ConfigFragments, write to disk
  5. Generate secondary artifacts (validation scripts, git hooks, CI workflow)
  6. Return EnforcementResult envelope

Conflict detection (CFD task) will slot between stages 3 and 4 once implemented.
"""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from ..contract.builder import ConstraintsContractBuilder
from ..contract.models import ConstraintsContract


class AppliedFragment(BaseModel):
    """A config fragment that was successfully written to disk."""

    adapter: str = Field(..., description="Adapter name, e.g. 'eslint', 'ruff'")
    target_file: str = Field(..., description="Path of the file that was written")
    policy_keys: list[str] = Field(
        default_factory=list,
        description="Contract policy keys that this fragment covers",
    )
    fragment_type: str = Field(
        ..., description="Fragment format, e.g. 'json_file', 'toml_section'"
    )


class EnforcementConflict(BaseModel):
    """A contradiction detected between fragments or with existing user config."""

    adapter: str = Field(..., description="Adapter that detected the conflict")
    description: str = Field(..., description="Human-readable conflict description")
    source_adrs: list[str] = Field(
        default_factory=list, description="ADR IDs whose policies conflict"
    )


class SkippedAdapter(BaseModel):
    """An adapter that did not run."""

    adapter: str = Field(..., description="Adapter name")
    reason: str = Field(
        ..., description="Why it was skipped, e.g. 'no matching policy keys'"
    )


class ProvenanceEntry(BaseModel):
    """Maps one contract rule back to its source ADR and clause."""

    rule: str = Field(..., description="Policy key, e.g. 'imports.disallow.axios'")
    source_adr_id: str = Field(..., description="ADR that defined this rule")
    clause_id: str = Field(
        ..., description="Deterministic 12-char clause identifier from contract"
    )
    artifact_refs: list[str] = Field(
        default_factory=list,
        description="Files/fragments generated from this rule (populated by adapters)",
    )


class EnforcementResult(BaseModel):
    """Stable audit artifact produced by every enforcement compilation run."""

    fragments_applied: list[AppliedFragment] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    conflicts: list[EnforcementConflict] = Field(default_factory=list)
    skipped_adapters: list[SkippedAdapter] = Field(default_factory=list)
    fallback_promptlets: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    idempotency_hash: str = Field(
        default="",
        description="SHA-256 of all outputs — identical on re-run with same inputs",
    )

    def compute_idempotency_hash(self) -> str:
        """Compute and store the idempotency hash from current outputs."""
        payload = {
            "fragments": sorted(
                [f.model_dump() for f in self.fragments_applied],
                key=lambda x: (x["adapter"], x["target_file"]),
            ),
            "files_touched": sorted(self.files_touched),
            "conflicts": sorted(
                [c.model_dump() for c in self.conflicts], key=lambda x: x["adapter"]
            ),
            "skipped_adapters": sorted(
                [s.model_dump() for s in self.skipped_adapters],
                key=lambda x: x["adapter"],
            ),
            "fallback_promptlets": sorted(self.fallback_promptlets),
            "provenance": sorted(
                [p.model_dump() for p in self.provenance], key=lambda x: x["rule"]
            ),
        }
        hash_str = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        self.idempotency_hash = hash_str
        return hash_str


class EnforcementPipeline:
    """Compiles a ConstraintsContract into enforcement artifacts.

    This is the single entry point for all enforcement. Callers pass the
    already-built contract; the pipeline reads constraints from it and never
    touches raw ADR files.
    """

    def __init__(self, adr_dir: Path, project_path: Path | None = None) -> None:
        self.adr_dir = adr_dir
        self.project_path = project_path or Path.cwd()

    def compile(
        self,
        contract: ConstraintsContract | None = None,
        detected_stack: list[str] | None = None,
    ) -> EnforcementResult:
        """Run the full enforcement pipeline and return a result envelope.

        Args:
            contract: Pre-built contract. If None, builds from adr_dir.
            detected_stack: Override the auto-detected technology stack.
                If None, StackDetector scans project_path automatically.

        Returns:
            EnforcementResult with fragments applied, conflicts, provenance, and hash.
        """
        from .adapters.eslint import ESLintAdapter
        from .adapters.ruff import RuffAdapter
        from .detection.stack import StackDetector
        from .router import PolicyRouter

        if contract is None:
            builder = ConstraintsContractBuilder(adr_dir=self.adr_dir)
            contract = builder.build()

        constraints = contract.constraints
        result = EnforcementResult()

        # Build provenance index from contract
        provenance_index = self._build_provenance_index(contract)
        result.provenance = list(provenance_index.values())

        # Stage 1: Detect project stack
        if detected_stack is None:
            detected_stack = StackDetector(self.project_path).detect()

        # Stage 2: Route via PolicyRouter
        router = PolicyRouter([ESLintAdapter(), RuffAdapter()])
        decisions, unroutable_keys = router.route(contract, detected_stack)

        # Record unroutable policy keys
        for key in unroutable_keys:
            result.skipped_adapters.append(
                SkippedAdapter(
                    adapter="none",
                    reason=f"no adapter for policy key: {key}",
                )
            )

        # Stage 3: Run selected adapters
        for decision in decisions:
            self._run_adapter(decision.adapter, constraints, result)

        # Record adapters not selected (skipped due to stack mismatch or no matching keys)
        selected_names = {d.adapter.name for d in decisions}
        for adapter in router.adapters:
            if adapter.name not in selected_names:
                # Determine why it was skipped
                stack_set = set(detected_stack)
                if not set(adapter.supported_languages) & stack_set:
                    reason = (
                        f"stack mismatch: adapter supports {adapter.supported_languages}, "
                        f"detected {detected_stack}"
                    )
                else:
                    reason = "no matching policy keys"
                result.skipped_adapters.append(
                    SkippedAdapter(adapter=adapter.name, reason=reason)
                )

        # Stage 4: Generate secondary artifacts
        self._run_script_generator(result)
        self._run_hook_generator(result)

        # Deduplicate files_touched
        result.files_touched = sorted(set(result.files_touched))

        # Compute idempotency hash
        result.compute_idempotency_hash()

        return result

    # ------------------------------------------------------------------
    # Internal adapter execution
    # ------------------------------------------------------------------

    def _run_adapter(
        self,
        adapter: object,
        constraints: object,
        result: EnforcementResult,
    ) -> None:
        """Call an adapter, write its fragments to disk, and record results."""
        from ..contract.models import MergedConstraints
        from .adapters.base import BaseAdapter

        if not isinstance(adapter, BaseAdapter):
            return
        if not isinstance(constraints, MergedConstraints):
            result.skipped_adapters.append(
                SkippedAdapter(
                    adapter=getattr(adapter, "name", "unknown"),
                    reason="invalid constraints object",
                )
            )
            return

        try:
            fragments = adapter.generate_fragments(constraints)
            for fragment in fragments:
                output_file = self.project_path / fragment.target_file
                output_file.write_text(fragment.content)
                result.fragments_applied.append(
                    AppliedFragment(
                        adapter=fragment.adapter,
                        target_file=str(output_file),
                        policy_keys=fragment.policy_keys,
                        fragment_type=fragment.fragment_type,
                    )
                )
                result.files_touched.append(str(output_file))
        except Exception as e:
            result.skipped_adapters.append(
                SkippedAdapter(
                    adapter=getattr(adapter, "name", "unknown"),
                    reason=f"adapter error: {e}",
                )
            )

    def _run_script_generator(self, result: EnforcementResult) -> None:
        """Generate per-ADR validation scripts."""
        try:
            from ..core.model import ADRStatus
            from ..core.parse import find_adr_files, parse_adr_file
            from .generation.scripts import ScriptGenerator

            generator = ScriptGenerator(adr_dir=self.adr_dir)
            output_dir = self.project_path / "scripts" / "adr"

            adr_files = find_adr_files(self.adr_dir)
            for file_path in adr_files:
                try:
                    adr = parse_adr_file(file_path, strict=False)
                    if adr and adr.front_matter.status == ADRStatus.ACCEPTED:
                        path = generator.generate_for_adr(adr, output_dir)
                        if path:
                            result.files_touched.append(str(path))
                except Exception:
                    continue

        except Exception as e:
            result.skipped_adapters.append(
                SkippedAdapter(adapter="script_generator", reason=f"error: {e}")
            )

    def _run_hook_generator(self, result: EnforcementResult) -> None:
        """Update git hooks for staged enforcement."""
        try:
            from .generation.hooks import HookGenerator

            generator = HookGenerator()
            hook_results = generator.generate(project_root=self.project_path)

            for name, action in hook_results.items():
                if action not in ("unchanged", "skipped"):
                    result.files_touched.append(
                        str(self.project_path / ".git" / "hooks" / name)
                    )

        except Exception as e:
            result.skipped_adapters.append(
                SkippedAdapter(adapter="hook_generator", reason=f"error: {e}")
            )

    def _build_provenance_index(
        self, contract: ConstraintsContract
    ) -> dict[str, ProvenanceEntry]:
        """Convert contract provenance into ProvenanceEntry objects."""
        index: dict[str, ProvenanceEntry] = {}
        for rule_path, prov in contract.provenance.items():
            index[rule_path] = ProvenanceEntry(
                rule=rule_path,
                source_adr_id=prov.adr_id,
                clause_id=prov.clause_id,
                artifact_refs=[],
            )
        return index
