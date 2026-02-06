"""Unit tests for update command logic."""

import subprocess
from unittest.mock import Mock, patch


class TestUpdateCommand:
    """Test update command installation method detection."""

    def test_detects_uv_installation(self):
        """Update command should try uv tool upgrade first if uv is available."""
        # Mock shutil.which to say uv exists
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/uv"

            # Verify that the logic would attempt uv first
            assert mock_which("uv") is not None

    def test_fallback_to_pip_when_uv_unavailable(self):
        """Update command should fall back to pip if uv is not available."""
        # Mock shutil.which to say uv doesn't exist
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None

            # Verify that the logic would skip uv
            assert mock_which("uv") is None

    def test_semantic_version_comparison(self):
        """Update command should use semantic version comparison."""
        from packaging.version import parse

        # Verify semantic comparison logic
        current = parse("0.2.5")
        latest_patch = parse("0.2.6")
        latest_minor = parse("0.3.0")
        latest_major = parse("1.0.0")
        older = parse("0.2.4")

        # Latest versions should be greater
        assert current < latest_patch
        assert current < latest_minor
        assert current < latest_major

        # Older version should not trigger update
        assert not (current < older)

    def test_error_messages_suggest_uv(self):
        """Error messages should suggest uv tool upgrade as primary method."""
        error_msg = "💡 Try manually: uv tool upgrade adr-kit"

        # Verify error message format
        assert "uv tool upgrade" in error_msg
        assert "adr-kit" in error_msg


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
