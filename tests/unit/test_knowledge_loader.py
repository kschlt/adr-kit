"""Tests for the knowledge module loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

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
            assert (
                len(criterion.evaluation_questions) >= 1
            ), f"{criterion.id} missing questions"

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

    def test_unknown_category_raises_key_error(self, loader: KnowledgeLoader) -> None:
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

    def test_unknown_category_raises_key_error(self, loader: KnowledgeLoader) -> None:
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
# Validation & error handling (legacy tests - now covered by graceful degradation)
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for JSON validation behavior.

    Note: With graceful degradation, these scenarios now warn instead of raising.
    See TestGracefulDegradation for the new behavior tests.
    """

    def test_missing_criteria_file_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing criteria file should warn (graceful degradation)."""
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=tmp_path / "missing.json",
                mappings_path=tmp_path / "also_missing.json",
            )
            criteria = loader.get_all_criteria()
        assert criteria == {}
        assert "Failed to load" in caplog.text

    def test_invalid_json_warns(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Invalid JSON should warn (graceful degradation)."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(criteria_path=bad, mappings_path=tmp_mappings)
            criteria = loader.get_all_criteria()
        assert criteria == {}
        assert "Invalid JSON" in caplog.text

    def test_missing_version_warns(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing version should warn (graceful degradation)."""
        no_ver = tmp_path / "no_ver.json"
        no_ver.write_text(json.dumps({"criteria": {}}))
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(criteria_path=no_ver, mappings_path=tmp_mappings)
            criteria = loader.get_all_criteria()
        assert criteria == {}

    def test_wrong_version_warns(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Wrong version should warn (graceful degradation)."""
        wrong = tmp_path / "wrong.json"
        wrong.write_text(json.dumps({"version": "99.0", "criteria": {}}))
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(criteria_path=wrong, mappings_path=tmp_mappings)
            criteria = loader.get_all_criteria()
        assert criteria == {}

    def test_missing_criteria_key_warns(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing 'criteria' key should warn (graceful degradation)."""
        no_key = tmp_path / "no_key.json"
        no_key.write_text(json.dumps({"version": "1.0"}))
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(criteria_path=no_key, mappings_path=tmp_mappings)
            criteria = loader.get_all_criteria()
        assert criteria == {}
        assert "Missing 'criteria' key" in caplog.text

    def test_missing_mappings_key_warns(
        self, tmp_criteria: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing 'mappings' key should warn (graceful degradation)."""
        no_key = tmp_path / "no_map.json"
        no_key.write_text(json.dumps({"version": "1.0"}))
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(criteria_path=tmp_criteria, mappings_path=no_key)
            categories = loader.categories
        assert categories == []


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


# ---------------------------------------------------------------------------
# Caching behavior
# ---------------------------------------------------------------------------


class TestCaching:
    """Tests for file caching behavior."""

    def test_second_call_does_not_reload_files(
        self, tmp_criteria: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify that data files are loaded only once."""
        loader = KnowledgeLoader(
            criteria_path=tmp_criteria,
            mappings_path=tmp_mappings,
        )

        # First call triggers load
        loader.get_all_criteria()

        # Modify files after first load
        tmp_criteria.write_text(json.dumps({"version": "1.0", "criteria": {}}))
        tmp_mappings.write_text(json.dumps({"version": "1.0", "mappings": {}}))

        # Second call should return cached data, not re-read
        criteria = loader.get_all_criteria()
        assert "alpha" in criteria  # Still has original data

    def test_multiple_loaders_load_independently(
        self, tmp_criteria: Path, tmp_mappings: Path
    ) -> None:
        """Each loader instance has its own cache."""
        loader1 = KnowledgeLoader(
            criteria_path=tmp_criteria,
            mappings_path=tmp_mappings,
        )
        loader2 = KnowledgeLoader(
            criteria_path=tmp_criteria,
            mappings_path=tmp_mappings,
        )

        # Both load independently
        assert "alpha" in loader1.get_all_criteria()
        assert "alpha" in loader2.get_all_criteria()

    def test_lazy_loading(self, tmp_criteria: Path, tmp_mappings: Path) -> None:
        """Files are not loaded until first access."""
        loader = KnowledgeLoader(
            criteria_path=tmp_criteria,
            mappings_path=tmp_mappings,
        )

        # Delete files before any access
        tmp_criteria.unlink()
        tmp_mappings.unlink()

        # Should fail on first access, not construction
        with pytest.raises(KeyError):
            loader.load_criteria("test_cat")


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Tests for graceful degradation on missing/malformed data."""

    def test_missing_criteria_file_warns_and_returns_empty(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing criteria file should warn but not crash."""
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=tmp_path / "nonexistent.json",
                mappings_path=tmp_mappings,
            )
            criteria = loader.get_all_criteria()

        assert criteria == {}
        assert "Failed to load criteria" in caplog.text

    def test_missing_mappings_file_warns_and_returns_empty(
        self, tmp_criteria: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing mappings file should warn but not crash."""
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=tmp_criteria,
                mappings_path=tmp_path / "nonexistent.json",
            )
            categories = loader.categories

        assert categories == []
        assert "Failed to load mappings" in caplog.text

    def test_malformed_json_warns_and_continues(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Malformed JSON should warn but not crash."""
        bad_criteria = tmp_path / "bad.json"
        bad_criteria.write_text("{not valid json")

        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=bad_criteria,
                mappings_path=tmp_mappings,
            )
            criteria = loader.get_all_criteria()

        assert criteria == {}
        assert "Failed to load criteria" in caplog.text
        assert "Invalid JSON" in caplog.text

    def test_missing_criteria_key_warns_and_returns_empty(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """File with missing 'criteria' key should warn."""
        no_key = tmp_path / "no_key.json"
        no_key.write_text(json.dumps({"version": "1.0"}))

        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=no_key,
                mappings_path=tmp_mappings,
            )
            criteria = loader.get_all_criteria()

        assert criteria == {}
        assert "Missing 'criteria' key" in caplog.text

    def test_wrong_version_warns_and_returns_empty(
        self, tmp_path: Path, tmp_mappings: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """File with wrong version should warn."""
        wrong_ver = tmp_path / "wrong.json"
        wrong_ver.write_text(json.dumps({"version": "99.0", "criteria": {}}))

        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=wrong_ver,
                mappings_path=tmp_mappings,
            )
            criteria = loader.get_all_criteria()

        assert criteria == {}
        assert "Failed to load criteria" in caplog.text

    def test_partial_data_still_usable(
        self, tmp_path: Path, tmp_criteria: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If criteria loads but mappings fail, criteria still accessible."""
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=tmp_criteria,
                mappings_path=tmp_path / "missing.json",
            )
            criteria = loader.get_all_criteria()

        assert "alpha" in criteria
        assert loader.categories == []

    def test_load_criteria_with_missing_data_raises(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """load_criteria() should raise KeyError if mappings unavailable."""
        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=tmp_path / "missing1.json",
                mappings_path=tmp_path / "missing2.json",
            )

        with pytest.raises(KeyError, match="mappings data unavailable"):
            loader.load_criteria("database")


# ---------------------------------------------------------------------------
# Promptlet assembly
# ---------------------------------------------------------------------------


class TestAssemblePromptlet:
    """Tests for assemble_promptlet(category) method."""

    def test_assembles_database_promptlet(self, loader: KnowledgeLoader) -> None:
        """Should combine guidance + primary criteria into single string."""
        promptlet = loader.assemble_promptlet("database")

        # Should include category guidance
        assert "migration reversibility" in promptlet

        # Should include primary criteria headers
        assert "Primary Evaluation Criteria" in promptlet

        # Should include primary criterion labels and templates
        result = loader.load_criteria("database")
        for criterion in result.primary:
            assert criterion.label in promptlet
            assert criterion.promptlet_template in promptlet

    def test_includes_category_header(self, loader: KnowledgeLoader) -> None:
        """Should include formatted category name in header."""
        promptlet = loader.assemble_promptlet("frontend")
        assert "Category Guidance: Frontend" in promptlet

    def test_numbers_criteria(self, loader: KnowledgeLoader) -> None:
        """Should number primary criteria sequentially."""
        promptlet = loader.assemble_promptlet("backend")
        assert "## 1." in promptlet
        assert "## 2." in promptlet

    def test_unknown_category_raises(self, loader: KnowledgeLoader) -> None:
        """Should raise KeyError for unknown category."""
        with pytest.raises(KeyError, match="Unknown category"):
            loader.assemble_promptlet("nonexistent")

    def test_empty_category_returns_guidance_only(
        self, tmp_criteria: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Category with no primary criteria should return guidance + warn."""
        empty_mappings = tmp_path / "empty_map.json"
        empty_mappings.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "mappings": {
                        "empty": {
                            "primary_criteria": [],
                            "secondary_criteria": [],
                            "category_guidance": "Just guidance.",
                        }
                    },
                }
            )
        )

        with caplog.at_level(logging.WARNING):
            loader = KnowledgeLoader(
                criteria_path=tmp_criteria,
                mappings_path=empty_mappings,
            )
            promptlet = loader.assemble_promptlet("empty")

        assert promptlet == "Just guidance."
        assert "has no primary criteria" in caplog.text

    def test_all_categories_have_valid_promptlets(
        self, loader: KnowledgeLoader
    ) -> None:
        """All six categories should produce non-empty promptlets."""
        for category in loader.categories:
            promptlet = loader.assemble_promptlet(category)
            assert len(promptlet) > 100, f"{category} promptlet too short"
            assert "Category Guidance" in promptlet
            assert "Primary Evaluation Criteria" in promptlet
