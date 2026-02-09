"""Knowledge loader for evaluation criteria and category mappings.

Loads machine-readable JSON data files and provides typed access
to criteria, category mappings, and guidance strings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent


class KnowledgeLoadError(Exception):
    """Raised when knowledge data cannot be loaded or validated."""


@dataclass(frozen=True)
class Criterion:
    """A single evaluation criterion with its promptlet template."""

    id: str
    label: str
    promptlet_template: str
    evaluation_questions: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Criterion:
        return cls(
            id=data["id"],
            label=data["label"],
            promptlet_template=data["promptlet_template"],
            evaluation_questions=tuple(data["evaluation_questions"]),
        )


@dataclass(frozen=True)
class CategoryCriteria:
    """Resolved criteria for a specific decision category.

    Contains full ``Criterion`` objects (not just IDs) so callers
    never need a second lookup.
    """

    category: str
    primary: tuple[Criterion, ...]
    secondary: tuple[Criterion, ...]
    guidance: str


class KnowledgeLoader:
    """Loads evaluation criteria and category mappings from bundled JSON files.

    Features:
    - File caching: JSON files loaded once, served from memory on subsequent calls
    - Graceful degradation: Warns on missing/malformed files, returns partial data
    - Promptlet assembly: Combines category guidance + criteria templates

    Usage::

        loader = KnowledgeLoader()
        result = loader.load_criteria("database")
        print(result.guidance)
        for c in result.primary:
            print(c.promptlet_template)

        # Assemble a promptlet for AI evaluation
        promptlet = loader.assemble_promptlet("database")
    """

    def __init__(
        self,
        criteria_path: Path | None = None,
        mappings_path: Path | None = None,
    ) -> None:
        self._criteria_path = criteria_path or _DATA_DIR / "evaluation_criteria.json"
        self._mappings_path = mappings_path or _DATA_DIR / "category_mappings.json"

        # Caching: load once, serve from memory
        self._criteria: dict[str, Criterion] | None = None
        self._mappings: dict[str, dict[str, Any]] | None = None
        self._load_attempted = False

    # -- public API ----------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Ensure data files are loaded. Only loads once (caching)."""
        if self._load_attempted:
            return
        self._load_attempted = True
        self._criteria = self._load_criteria()
        self._mappings = self._load_mappings()

    def load_criteria(self, category: str) -> CategoryCriteria:
        """Return resolved primary + secondary criteria for *category*.

        Raises ``KeyError`` if *category* is not a known mapping.
        """
        self._ensure_loaded()

        if not self._mappings:
            raise KeyError(
                f"Cannot load category {category!r}: mappings data unavailable"
            )

        mapping = self._mappings.get(category)
        if mapping is None:
            known = sorted(self._mappings)
            raise KeyError(
                f"Unknown category {category!r}. "
                f"Known categories: {', '.join(known)}"
            )

        criteria = self._criteria or {}
        primary = tuple(
            criteria[cid] for cid in mapping["primary_criteria"] if cid in criteria
        )
        secondary = tuple(
            criteria[cid] for cid in mapping["secondary_criteria"] if cid in criteria
        )
        return CategoryCriteria(
            category=category,
            primary=primary,
            secondary=secondary,
            guidance=mapping["category_guidance"],
        )

    def get_category_guidance(self, category: str) -> str:
        """Return the guidance string for *category*.

        Raises ``KeyError`` if *category* is not a known mapping.
        """
        self._ensure_loaded()

        if not self._mappings:
            raise KeyError(
                f"Cannot get guidance for {category!r}: mappings data unavailable"
            )

        mapping = self._mappings.get(category)
        if mapping is None:
            known = sorted(self._mappings)
            raise KeyError(
                f"Unknown category {category!r}. "
                f"Known categories: {', '.join(known)}"
            )
        return str(mapping["category_guidance"])

    def get_all_criteria(self) -> dict[str, Criterion]:
        """Return all loaded criteria keyed by criterion ID."""
        self._ensure_loaded()
        return dict(self._criteria or {})

    @property
    def categories(self) -> list[str]:
        """Return sorted list of known category names."""
        self._ensure_loaded()
        return sorted(self._mappings or {})

    def assemble_promptlet(self, category: str) -> str:
        """Assemble a ready-to-use promptlet string for *category*.

        Combines category guidance with primary criteria promptlet templates
        into a single focused evaluation prompt.

        Raises ``KeyError`` if *category* is not a known mapping.
        """
        result = self.load_criteria(category)

        if not result.primary:
            logger.warning(f"Category {category!r} has no primary criteria")
            return result.guidance

        sections = [
            f"# Category Guidance: {category.title()}\n",
            result.guidance,
            "\n\n# Primary Evaluation Criteria\n",
        ]

        for i, criterion in enumerate(result.primary, 1):
            sections.append(f"\n## {i}. {criterion.label}\n")
            sections.append(criterion.promptlet_template)

        return "".join(sections)

    # -- internal loading ----------------------------------------------------

    def _load_criteria(self) -> dict[str, Criterion]:
        """Load criteria with graceful degradation on errors."""
        try:
            raw = self._read_json(self._criteria_path)
            self._check_version(raw, self._criteria_path)
            if "criteria" not in raw:
                logger.warning(
                    f"Missing 'criteria' key in {self._criteria_path}, "
                    "returning empty criteria"
                )
                return {}
            return {
                cid: Criterion.from_dict(cdata)
                for cid, cdata in raw["criteria"].items()
            }
        except KnowledgeLoadError as exc:
            logger.warning(f"Failed to load criteria: {exc}. Returning empty dict.")
            return {}

    def _load_mappings(self) -> dict[str, dict[str, Any]]:
        """Load mappings with graceful degradation on errors."""
        try:
            raw = self._read_json(self._mappings_path)
            self._check_version(raw, self._mappings_path)
            if "mappings" not in raw:
                logger.warning(
                    f"Missing 'mappings' key in {self._mappings_path}, "
                    "returning empty mappings"
                )
                return {}
            return dict(raw["mappings"])
        except KnowledgeLoadError as exc:
            logger.warning(f"Failed to load mappings: {exc}. Returning empty dict.")
            return {}

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise KnowledgeLoadError(f"Knowledge file not found: {path}") from None
        try:
            data: dict[str, Any] = json.loads(text)
            return data
        except json.JSONDecodeError as exc:
            raise KnowledgeLoadError(f"Invalid JSON in {path}: {exc}") from None

    @staticmethod
    def _check_version(data: dict[str, Any], path: Path) -> None:
        version = data.get("version")
        if version is None:
            raise KnowledgeLoadError(f"Missing 'version' key in {path}")
        if version != "1.0":
            raise KnowledgeLoadError(
                f"Unsupported version {version!r} in {path} (expected '1.0')"
            )
