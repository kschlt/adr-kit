"""Unit tests for version checking logic."""

from packaging.version import parse


class TestVersionComparison:
    """Test version comparison logic used in update checks."""

    def test_same_version_no_update(self):
        """Same version should not trigger update notification."""
        current = "0.2.5"
        latest = "0.2.5"

        # String comparison
        assert current == latest

        # Semantic version comparison
        assert not (parse(current) < parse(latest))

    def test_newer_version_triggers_update(self):
        """Newer version should trigger update notification."""
        current = "0.2.5"
        latest = "0.3.0"

        # String comparison shows they're different
        assert current != latest

        # Semantic version comparison confirms latest is newer
        assert parse(current) < parse(latest)

    def test_patch_version_update(self):
        """Patch version bump should trigger update."""
        current = "0.2.5"
        latest = "0.2.6"

        assert parse(current) < parse(latest)

    def test_major_version_update(self):
        """Major version bump should trigger update."""
        current = "0.2.5"
        latest = "1.0.0"

        assert parse(current) < parse(latest)

    def test_older_version_no_update(self):
        """Older version should not trigger update (downgrade protection)."""
        current = "0.3.0"
        latest = "0.2.5"

        assert not (parse(current) < parse(latest))

    def test_dev_version_comparison(self):
        """Dev versions should compare correctly."""
        current = "0.0.0.dev"
        latest = "0.2.5"

        # Dev version is always older than release
        assert parse(current) < parse(latest)

    def test_prerelease_versions(self):
        """Pre-release versions should compare correctly."""
        current = "0.2.5"
        latest_beta = "0.3.0b1"

        # 0.2.5 is older than 0.3.0b1
        assert parse(current) < parse(latest_beta)

        latest_rc = "0.3.0rc1"
        assert parse(current) < parse(latest_rc)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
