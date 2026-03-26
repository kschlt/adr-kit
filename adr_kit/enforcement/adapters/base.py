"""Base adapter interface for enforcement config generation.

All adapters must implement BaseAdapter. Capabilities are declared via
properties so the PolicyRouter can match adapters to contract policy keys
and the detected technology stack without instantiating every adapter.

ConfigFragment is the in-memory artifact produced by generate_fragments();
the pipeline is responsible for writing it to disk.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ...contract.models import MergedConstraints


@dataclass
class ConfigFragment:
    """In-memory config fragment produced by an adapter before it is written to disk."""

    adapter: str
    """Adapter that produced this fragment, e.g. 'eslint'."""

    target_file: str
    """Relative path (from project root) where this fragment should be written."""

    content: str
    """Serialized content ready to write (JSON string, TOML string, etc.)."""

    fragment_type: str
    """Format hint: 'json_file', 'toml_file', 'ini_file', etc."""

    policy_keys: list[str] = field(default_factory=list)
    """Contract policy keys covered by this fragment, e.g. ['imports.disallow.axios']."""


class BaseAdapter(ABC):
    """Abstract base class for all enforcement adapters.

    Subclasses declare their capabilities via properties so the PolicyRouter
    can select them without running them. Only generate_fragments() is called
    when the adapter is actually selected.
    """

    # ------------------------------------------------------------------
    # Required capability declarations
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter identifier, e.g. 'eslint', 'ruff'."""
        ...

    @property
    @abstractmethod
    def supported_policy_keys(self) -> list[str]:
        """Contract constraint fields this adapter can enforce.

        Match the field names on MergedConstraints, e.g. ['imports', 'python'].
        The router uses this to determine which adapters handle which policy keys.
        """
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Languages / ecosystems this adapter targets, e.g. ['javascript', 'typescript'].

        The router uses this to filter adapters by the detected project stack.
        Values should be lower-case language identifiers that StackDetector emits.
        """
        ...

    @property
    @abstractmethod
    def config_targets(self) -> list[str]:
        """File paths (relative to project root) this adapter may write to."""
        ...

    # ------------------------------------------------------------------
    # Optional capability declarations (with sensible defaults)
    # ------------------------------------------------------------------

    @property
    def supported_clause_kinds(self) -> list[str]:
        """Clause families this adapter can enforce, e.g. 'forbidden_import'.

        Provisional — ENF-CLA will define the canonical vocabulary. Until then,
        free-form strings are acceptable. Defaults to empty (adapter handles all).
        """
        return []

    @property
    def output_modes(self) -> list[str]:
        """Kinds of artifacts this adapter emits.

        Values: native_config, native_rules, generated_checker, policy_file, script_fallback.
        ENF-MODE will formalise these as a first-class enum. Defaults to native_config.
        """
        return ["native_config"]

    @property
    def supported_stages(self) -> list[str]:
        """Enforcement stages this adapter targets (commit, push, ci).

        Defaults to ['ci'].
        """
        return ["ci"]

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_fragments(
        self, constraints: MergedConstraints
    ) -> list[ConfigFragment]:
        """Generate in-memory config fragments from the merged constraints.

        The pipeline calls this after routing. Implementations must be
        deterministic — identical inputs must produce identical outputs.

        Args:
            constraints: The merged policy constraints from the ConstraintsContract.

        Returns:
            List of ConfigFragment objects (may be empty if nothing to emit).
        """
        ...
