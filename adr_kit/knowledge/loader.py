"""Knowledge loader for evaluation criteria and category mappings.

Loads machine-readable JSON data files and provides typed access
to criteria, category mappings, and guidance strings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

    Usage::

        loader = KnowledgeLoader()
        result = loader.load_criteria("database")
        print(result.guidance)
        for c in result.primary:
            print(c.promptlet_template)
    """

    def __init__(
        self,
        criteria_path: Path | None = None,
        mappings_path: Path | None = None,
    ) -> None:
        self._criteria_path = criteria_path or _DATA_DIR / "evaluation_criteria.json"
        self._mappings_path = mappings_path or _DATA_DIR / "category_mappings.json"

        # Eagerly load & validate on construction so callers fail fast.
        self._criteria: dict[str, Criterion] = self._load_criteria()
        self._mappings: dict[str, dict[str, Any]] = self._load_mappings()

    # -- public API ----------------------------------------------------------

    def load_criteria(self, category: str) -> CategoryCriteria:
        """Return resolved primary + secondary criteria for *category*.

        Raises ``KeyError`` if *category* is not a known mapping.
        """
        mapping = self._mappings.get(category)
        if mapping is None:
            known = sorted(self._mappings)
            raise KeyError(
                f"Unknown category {category!r}. "
                f"Known categories: {', '.join(known)}"
            )

        primary = tuple(
            self._criteria[cid]
            for cid in mapping["primary_criteria"]
            if cid in self._criteria
        )
        secondary = tuple(
            self._criteria[cid]
            for cid in mapping["secondary_criteria"]
            if cid in self._criteria
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
        mapping = self._mappings.get(category)
        if mapping is None:
            known = sorted(self._mappings)
            raise KeyError(
                f"Unknown category {category!r}. "
                f"Known categories: {', '.join(known)}"
            )
        return mapping["category_guidance"]

    def get_all_criteria(self) -> dict[str, Criterion]:
        """Return all loaded criteria keyed by criterion ID."""
        return dict(self._criteria)

    @property
    def categories(self) -> list[str]:
        """Return sorted list of known category names."""
        return sorted(self._mappings)

    # -- internal loading ----------------------------------------------------

    def _load_criteria(self) -> dict[str, Criterion]:
        raw = self._read_json(self._criteria_path)
        self._check_version(raw, self._criteria_path)
        if "criteria" not in raw:
            raise KnowledgeLoadError(
                f"Missing 'criteria' key in {self._criteria_path}"
            )
        return {
            cid: Criterion.from_dict(cdata)
            for cid, cdata in raw["criteria"].items()
        }

    def _load_mappings(self) -> dict[str, dict[str, Any]]:
        raw = self._read_json(self._mappings_path)
        self._check_version(raw, self._mappings_path)
        if "mappings" not in raw:
            raise KnowledgeLoadError(
                f"Missing 'mappings' key in {self._mappings_path}"
            )
        return dict(raw["mappings"])

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise KnowledgeLoadError(f"Knowledge file not found: {path}") from None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise KnowledgeLoadError(
                f"Invalid JSON in {path}: {exc}"
            ) from None

    @staticmethod
    def _check_version(data: dict[str, Any], path: Path) -> None:
        version = data.get("version")
        if version is None:
            raise KnowledgeLoadError(f"Missing 'version' key in {path}")
        if version != "1.0":
            raise KnowledgeLoadError(
                f"Unsupported version {version!r} in {path} (expected '1.0')"
            )
