"""Tests for the knowledge module loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adr_kit.knowledge import CategoryCriteria, KnowledgeLoader
from adr_kit.knowledge.loader import Criterion, KnowledgeLoadError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def loader() -> KnowledgeLoader:
    """Return a loader backed by the real bundled data files."""
    return KnowledgeLoader()


@pytest.fixture()
def tmp_criteria(tmp_path: Path) -> Path:
    """Write a minimal valid criteria file and return its path."""
    data = {
        "version": "1.0",
        "criteria": {
            "alpha": {
                "id": "alpha",
                "label": "Alpha Criterion",
                "promptlet_template": "Is alpha good?",
                "evaluation_questions": ["Q1?", "Q2?"],
            }
        },
    }
    p = tmp_path / "criteria.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture()
def tmp_mappings(tmp_path: Path) -> Path:
    """Write a minimal valid mappings file and return its path."""
    data = {
        "version": "1.0",
        "mappings": {
            "test_cat": {
                "primary_criteria": ["alpha"],
                "secondary_criteria": [],
                "category_guidance": "Test guidance.",
            }
        },
    }
    p = tmp_path / "mappings.json"
    p.write_text(json.dumps(data))
    return p


# ---------------------------------------------------------------------------
# Loading all criteria
# ---------------------------------------------------------------------------


class TestGetAllCriteria:
    """Tests for get_all_criteria()."""

    def test_returns_all_ten_criteria(self, loader: KnowledgeLoader) -> None:
        all_criteria = loader.get_all_criteria()
        assert len(all_criteria) == 10

    def test_criteria_ids_match_keys(self, loader: KnowledgeLoader) -> None:
        for cid, criterion in loader.get_all_criteria().items():
            assert cid == criterion.id

    def test_all_criteria_have_promptlet_template(
        self, loader: KnowledgeLoader
    ) -> None:
        for criterion in loader.get_all_criteria().values():
            assert criterion.promptlet_template, f"{criterion.id} missing template"

    def test_all_criteria_have_evaluation_questions(
        self, loader: KnowledgeLoader
    ) -> None:
        for criterion in loader.get_all_criteria().values():
            assert len(criterion.evaluation_questions) >= 1, (
                f"{criterion.id} missing questions"
            )

    def test_expected_criterion_ids(self, loader: KnowledgeLoader) -> None:
        expected = {
            "feedback_loops",
            "documentation_accessibility",
            "decision_space",
            "executability",
            "modularity",
            "reversibility",
            "safety",
            "multi_agent",
            "reviewability",
            "ai_learning_curve",
        }
        assert set(loader.get_all_criteria()) == expected

    def test_returns_copy(self, loader: KnowledgeLoader) -> None:
        """Mutating the returned dict must not affect the loader."""
        d1 = loader.get_all_criteria()
        d1.pop(next(iter(d1)))
        d2 = loader.get_all_criteria()
        assert len(d2) == 10


# ---------------------------------------------------------------------------
# Per-category retrieval
# ---------------------------------------------------------------------------


class TestLoadCriteria:
    """Tests for load_criteria(category)."""

    def test_database_primary_criteria(self, loader: KnowledgeLoader) -> None:
        result = loader.load_criteria("database")
        primary_ids = [c.id for c in result.primary]
        assert primary_ids == [
            "feedback_loops",
            "reversibility",
            "safety",
            "executability",
        ]

    def test_database_secondary_criteria(self, loader: KnowledgeLoader) -> None:
        result = loader.load_criteria("database")
        secondary_ids = [c.id for c in result.secondary]
        assert secondary_ids == ["documentation_accessibility", "modularity"]

    def test_frontend_has_five_primary(self, loader: KnowledgeLoader) -> None:
        result = loader.load_criteria("frontend")
        assert len(result.primary) == 5

    def test_category_field_set(self, loader: KnowledgeLoader) -> None:
        result = loader.load_criteria("backend")
        assert result.category == "backend"

    def test_criteria_are_full_objects(self, loader: KnowledgeLoader) -> None:
        result = loader.load_criteria("database")
        for c in result.primary:
            assert isinstance(c, Criterion)
            assert c.label
            assert c.promptlet_template

    def test_all_six_categories_loadable(self, loader: KnowledgeLoader) -> None:
        for cat in [
            "database",
            "frontend",
            "backend",
            "architecture",
            "authentication",
            "technology",
        ]:
            result = loader.load_criteria(cat)
            assert isinstance(result, CategoryCriteria)
            assert len(result.primary) >= 1

    def test_unknown_category_raises_key_error(
        self, loader: KnowledgeLoader
    ) -> None:
        with pytest.raises(KeyError, match="Unknown category 'nonexistent'"):
            loader.load_criteria("nonexistent")

    def test_unknown_category_lists_known(self, loader: KnowledgeLoader) -> None:
        with pytest.raises(KeyError, match="database"):
            loader.load_criteria("nope")


# ---------------------------------------------------------------------------
# Category guidance
# ---------------------------------------------------------------------------


class TestGetCategoryGuidance:
    """Tests for get_category_guidance(category)."""

    def test_database_guidance(self, loader: KnowledgeLoader) -> None:
        guidance = loader.get_category_guidance("database")
        assert "migration reversibility" in guidance

    def test_frontend_guidance(self, loader: KnowledgeLoader) -> None:
        guidance = loader.get_category_guidance("frontend")
        assert "file-based routing" in guidance

    def test_authentication_guidance(self, loader: KnowledgeLoader) -> None:
        guidance = loader.get_category_guidance("authentication")
        assert "secure-by-default" in guidance

    def test_unknown_category_raises_key_error(
        self, loader: KnowledgeLoader
    ) -> None:
        with pytest.raises(KeyError, match="Unknown category"):
            loader.get_category_guidance("unknown")


# ---------------------------------------------------------------------------
# Categories property
# ---------------------------------------------------------------------------


class TestCategories:
    """Tests for the categories property."""

    def test_six_categories(self, loader: KnowledgeLoader) -> None:
        assert len(loader.categories) == 6

    def test_sorted(self, loader: KnowledgeLoader) -> None:
        cats = loader.categories
        assert cats == sorted(cats)


# ---------------------------------------------------------------------------
# Validation & error handling
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for JSON validation on load."""

    def test_missing_criteria_file(self, tmp_path: Path) -> None:
        with pytest.raises(KnowledgeLoadError, match="not found"):
            KnowledgeLoader(
                criteria_path=tmp_path / "missing.json",
                mappings_path=tmp_path / "also_missing.json",
            )

    def test_invalid_json(self, tmp_path: Path, tmp_mappings: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        with pytest.raises(KnowledgeLoadError, match="Invalid JSON"):
            KnowledgeLoader(criteria_path=bad, mappings_path=tmp_mappings)

    def test_missing_version(self, tmp_path: Path, tmp_mappings: Path) -> None:
        no_ver = tmp_path / "no_ver.json"
        no_ver.write_text(json.dumps({"criteria": {}}))
        with pytest.raises(KnowledgeLoadError, match="Missing 'version'"):
            KnowledgeLoader(criteria_path=no_ver, mappings_path=tmp_mappings)

    def test_wrong_version(self, tmp_path: Path, tmp_mappings: Path) -> None:
        wrong = tmp_path / "wrong.json"
        wrong.write_text(json.dumps({"version": "99.0", "criteria": {}}))
        with pytest.raises(KnowledgeLoadError, match="Unsupported version"):
            KnowledgeLoader(criteria_path=wrong, mappings_path=tmp_mappings)

    def test_missing_criteria_key(self, tmp_path: Path, tmp_mappings: Path) -> None:
        no_key = tmp_path / "no_key.json"
        no_key.write_text(json.dumps({"version": "1.0"}))
        with pytest.raises(KnowledgeLoadError, match="Missing 'criteria'"):
            KnowledgeLoader(criteria_path=no_key, mappings_path=tmp_mappings)

    def test_missing_mappings_key(
        self, tmp_criteria: Path, tmp_path: Path
    ) -> None:
        no_key = tmp_path / "no_map.json"
        no_key.write_text(json.dumps({"version": "1.0"}))
        with pytest.raises(KnowledgeLoadError, match="Missing 'mappings'"):
            KnowledgeLoader(criteria_path=tmp_criteria, mappings_path=no_key)


# ---------------------------------------------------------------------------
# Custom paths (e.g. for tmp_path fixtures)
# ---------------------------------------------------------------------------


class TestCustomPaths:
    """Loading from custom file paths (not bundled data)."""

    def test_load_from_custom_paths(
        self, tmp_criteria: Path, tmp_mappings: Path
    ) -> None:
        loader = KnowledgeLoader(
            criteria_path=tmp_criteria,
            mappings_path=tmp_mappings,
        )
        assert "alpha" in loader.get_all_criteria()
        result = loader.load_criteria("test_cat")
        assert result.primary[0].id == "alpha"
        assert result.guidance == "Test guidance."


# ---------------------------------------------------------------------------
# Criterion dataclass
# ---------------------------------------------------------------------------


class TestCriterion:
    """Tests for the Criterion dataclass."""

    def test_from_dict(self) -> None:
        data = {
            "id": "test",
            "label": "Test",
            "promptlet_template": "Template?",
            "evaluation_questions": ["Q1?"],
        }
        c = Criterion.from_dict(data)
        assert c.id == "test"
        assert c.evaluation_questions == ("Q1?",)

    def test_is_frozen(self) -> None:
        c = Criterion(
            id="x",
            label="X",
            promptlet_template="T",
            evaluation_questions=("Q?",),
        )
        with pytest.raises(AttributeError):
            c.id = "y"  # type: ignore[misc]
