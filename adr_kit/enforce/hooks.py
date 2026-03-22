"""Git hook generator for staged ADR enforcement.

Writes a managed section into .git/hooks/pre-commit and .git/hooks/pre-push
so that ADR policy checks run automatically at the right workflow stage.

Design:
- Non-interfering: appends a managed section to existing hooks, never overwrites.
- Idempotent: re-running updates the managed section in-place.
- Clearly marked: ADR-KIT markers make ownership obvious.
- First-run bootstraps: creates hook file if it doesn't exist.
"""

import stat
from pathlib import Path

# Sentinel markers — must be unique and stable across versions
MANAGED_START = "# >>> ADR-KIT MANAGED - DO NOT EDIT >>>"
MANAGED_END = "# <<< ADR-KIT MANAGED <<<"

_HOOK_HEADER = "#!/bin/sh"

# Per-hook managed content
_COMMIT_SECTION = f"""\
{MANAGED_START}
adr-kit enforce commit
{MANAGED_END}"""

_PUSH_SECTION = f"""\
{MANAGED_START}
adr-kit enforce push
{MANAGED_END}"""


def _make_executable(path: Path) -> None:
    """Ensure the hook file has executable permission."""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _apply_managed_section(hook_path: Path, managed_content: str) -> str:
    """Insert or replace the ADR-Kit managed section in a hook file.

    If the hook doesn't exist, creates it with a shebang + managed section.
    Returns a string describing what changed: "created" | "updated" | "unchanged".
    """
    if not hook_path.exists():
        hook_path.write_text(f"{_HOOK_HEADER}\n\n{managed_content}\n")
        _make_executable(hook_path)
        return "created"

    existing = hook_path.read_text()

    # Replace existing managed section
    if MANAGED_START in existing and MANAGED_END in existing:
        start_idx = existing.index(MANAGED_START)
        end_idx = existing.index(MANAGED_END) + len(MANAGED_END)
        new_section = (
            existing[:start_idx].rstrip("\n")
            + "\n\n"
            + managed_content
            + "\n"
            + existing[end_idx:].lstrip("\n")
        )
        if new_section == existing:
            return "unchanged"
        hook_path.write_text(new_section)
        _make_executable(hook_path)
        return "updated"

    # No managed section yet — append
    separator = "\n\n" if existing.rstrip() else ""
    hook_path.write_text(existing.rstrip() + separator + managed_content + "\n")
    _make_executable(hook_path)
    return "appended"


class HookGenerator:
    """Generates and updates git hooks for staged ADR enforcement.

    Writes ADR-Kit managed sections into .git/hooks/pre-commit and
    .git/hooks/pre-push. Safe to call repeatedly — idempotent.
    """

    def generate(self, project_root: Path | None = None) -> dict[str, str]:
        """Write managed sections into pre-commit and pre-push hooks.

        Args:
            project_root: Root of the git repository. Defaults to cwd.

        Returns:
            Dict mapping hook name → action taken ("created"|"updated"|"appended"|"unchanged"|"skipped").
        """
        project_root = project_root or Path.cwd()
        hooks_dir = project_root / ".git" / "hooks"

        if not hooks_dir.exists():
            # Not a git repo or hooks dir missing — skip silently
            return {
                "pre-commit": "skipped (no .git/hooks directory)",
                "pre-push": "skipped (no .git/hooks directory)",
            }

        results: dict[str, str] = {}

        results["pre-commit"] = _apply_managed_section(
            hooks_dir / "pre-commit", _COMMIT_SECTION
        )
        results["pre-push"] = _apply_managed_section(
            hooks_dir / "pre-push", _PUSH_SECTION
        )

        return results

    def remove(self, project_root: Path | None = None) -> dict[str, str]:
        """Remove ADR-Kit managed sections from git hooks.

        Useful when uninstalling or disabling enforcement.

        Returns:
            Dict mapping hook name → action taken ("removed"|"not_found"|"skipped").
        """
        project_root = project_root or Path.cwd()
        hooks_dir = project_root / ".git" / "hooks"

        if not hooks_dir.exists():
            return {
                "pre-commit": "skipped (no .git/hooks directory)",
                "pre-push": "skipped (no .git/hooks directory)",
            }

        results: dict[str, str] = {}
        for hook_name in ("pre-commit", "pre-push"):
            hook_path = hooks_dir / hook_name
            if not hook_path.exists():
                results[hook_name] = "not_found"
                continue

            content = hook_path.read_text()
            if MANAGED_START not in content:
                results[hook_name] = "not_found"
                continue

            start_idx = content.index(MANAGED_START)
            end_idx = content.index(MANAGED_END) + len(MANAGED_END)
            # Strip surrounding blank lines added when appending
            cleaned = content[:start_idx].rstrip("\n") + content[end_idx:].lstrip("\n")
            if not cleaned.strip():
                # Hook only contained our section — remove the file
                hook_path.unlink()
            else:
                hook_path.write_text(cleaned)
            results[hook_name] = "removed"

        return results

    def status(self, project_root: Path | None = None) -> dict[str, bool]:
        """Check whether ADR-Kit managed sections are present in hooks.

        Returns:
            Dict mapping hook name → True if managed section is present.
        """
        project_root = project_root or Path.cwd()
        hooks_dir = project_root / ".git" / "hooks"

        result: dict[str, bool] = {}
        for hook_name in ("pre-commit", "pre-push"):
            hook_path = hooks_dir / hook_name
            if not hook_path.exists():
                result[hook_name] = False
                continue
            result[hook_name] = MANAGED_START in hook_path.read_text()

        return result
