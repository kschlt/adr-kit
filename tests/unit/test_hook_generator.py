"""Unit tests for the git hook generator."""

import stat
import tempfile
from pathlib import Path

import pytest

from adr_kit.enforcement.generation.hooks import (
    MANAGED_END,
    MANAGED_START,
    HookGenerator,
    _apply_managed_section,
)

# ---------------------------------------------------------------------------
# _apply_managed_section
# ---------------------------------------------------------------------------


class TestApplyManagedSection:
    CONTENT = f"{MANAGED_START}\nadr-kit enforce commit\n{MANAGED_END}"

    def test_creates_hook_when_file_missing(self, tmp_path):
        hook = tmp_path / "pre-commit"
        action = _apply_managed_section(hook, self.CONTENT)
        assert action == "created"
        assert hook.exists()
        assert MANAGED_START in hook.read_text()
        assert "adr-kit enforce commit" in hook.read_text()

    def test_created_hook_has_shebang(self, tmp_path):
        hook = tmp_path / "pre-commit"
        _apply_managed_section(hook, self.CONTENT)
        assert hook.read_text().startswith("#!/bin/sh")

    def test_created_hook_is_executable(self, tmp_path):
        hook = tmp_path / "pre-commit"
        _apply_managed_section(hook, self.CONTENT)
        mode = hook.stat().st_mode
        assert mode & stat.S_IXUSR

    def test_appends_to_existing_hook(self, tmp_path):
        hook = tmp_path / "pre-commit"
        hook.write_text("#!/bin/sh\nnpm test\n")
        action = _apply_managed_section(hook, self.CONTENT)
        assert action == "appended"
        text = hook.read_text()
        assert "npm test" in text
        assert MANAGED_START in text

    def test_updates_existing_managed_section(self, tmp_path):
        hook = tmp_path / "pre-commit"
        old_content = f"#!/bin/sh\n{MANAGED_START}\nold command\n{MANAGED_END}\n"
        hook.write_text(old_content)
        new_section = f"{MANAGED_START}\nadr-kit enforce commit\n{MANAGED_END}"
        action = _apply_managed_section(hook, new_section)
        assert action == "updated"
        text = hook.read_text()
        assert "old command" not in text
        assert "adr-kit enforce commit" in text

    def test_unchanged_when_content_identical(self, tmp_path):
        hook = tmp_path / "pre-commit"
        content = f"#!/bin/sh\n\n{self.CONTENT}\n"
        hook.write_text(content)
        action = _apply_managed_section(hook, self.CONTENT)
        assert action == "unchanged"

    def test_user_content_preserved_on_update(self, tmp_path):
        hook = tmp_path / "pre-commit"
        hook.write_text(
            f"#!/bin/sh\nnpm test\n\n{MANAGED_START}\nold\n{MANAGED_END}\n\necho done\n"
        )
        _apply_managed_section(hook, self.CONTENT)
        text = hook.read_text()
        assert "npm test" in text
        assert "echo done" in text
        assert "adr-kit enforce commit" in text

    def test_only_one_managed_section_after_multiple_calls(self, tmp_path):
        hook = tmp_path / "pre-commit"
        _apply_managed_section(hook, self.CONTENT)
        _apply_managed_section(hook, self.CONTENT)
        text = hook.read_text()
        assert text.count(MANAGED_START) == 1


# ---------------------------------------------------------------------------
# HookGenerator
# ---------------------------------------------------------------------------


class TestHookGenerator:
    def _make_git_repo(self, tmp_path: Path) -> Path:
        """Create a minimal git repo structure."""
        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        return tmp_path

    def test_generate_creates_both_hooks(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        gen = HookGenerator()
        results = gen.generate(project_root=root)
        assert "pre-commit" in results
        assert "pre-push" in results
        assert (root / ".git" / "hooks" / "pre-commit").exists()
        assert (root / ".git" / "hooks" / "pre-push").exists()

    def test_pre_commit_calls_enforce_commit(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        HookGenerator().generate(project_root=root)
        content = (root / ".git" / "hooks" / "pre-commit").read_text()
        assert "adr-kit enforce commit" in content

    def test_pre_push_calls_enforce_push(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        HookGenerator().generate(project_root=root)
        content = (root / ".git" / "hooks" / "pre-push").read_text()
        assert "adr-kit enforce push" in content

    def test_generate_is_idempotent(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        gen = HookGenerator()
        gen.generate(project_root=root)
        gen.generate(project_root=root)
        content = (root / ".git" / "hooks" / "pre-commit").read_text()
        assert content.count(MANAGED_START) == 1

    def test_generate_skips_when_no_git_dir(self, tmp_path):
        gen = HookGenerator()
        results = gen.generate(project_root=tmp_path)
        assert all("skipped" in v for v in results.values())

    def test_status_false_before_generate(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        status = HookGenerator().status(project_root=root)
        assert status["pre-commit"] is False
        assert status["pre-push"] is False

    def test_status_true_after_generate(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        HookGenerator().generate(project_root=root)
        status = HookGenerator().status(project_root=root)
        assert status["pre-commit"] is True
        assert status["pre-push"] is True

    def test_remove_cleans_managed_section(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        HookGenerator().generate(project_root=root)
        HookGenerator().remove(project_root=root)
        hook = root / ".git" / "hooks" / "pre-commit"
        assert not hook.exists() or MANAGED_START not in hook.read_text()

    def test_remove_preserves_user_content(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        hook = root / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nnpm test\n")
        HookGenerator().generate(project_root=root)
        HookGenerator().remove(project_root=root)
        assert "npm test" in hook.read_text()

    def test_remove_returns_not_found_when_no_section(self, tmp_path):
        root = self._make_git_repo(tmp_path)
        results = HookGenerator().remove(project_root=root)
        assert results["pre-commit"] == "not_found"
        assert results["pre-push"] == "not_found"
