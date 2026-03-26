"""Technology stack detection for the enforcement router.

Scans a project directory for file extensions to determine which languages
and ecosystems are present. The router uses this to filter adapters by stack.
"""

from collections.abc import Generator
from pathlib import Path

# Extension → language identifier (lower-case)
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# Directories to always skip during scanning
_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".testenv",
}


class StackDetector:
    """Detect which technology stacks are present in a project directory.

    Scans file extensions (skipping common build/cache dirs) and returns
    a deduplicated, sorted list of language identifiers.

    Example::

        detector = StackDetector(project_root=Path("/my/project"))
        stack = detector.detect()
        # e.g. ["python", "typescript"]
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def detect(self) -> list[str]:
        """Return detected language identifiers for this project.

        Scans all files under project_root (excluding common ignored dirs)
        and maps file extensions to language names.

        Returns:
            Sorted, deduplicated list of language identifiers, e.g. ['python', 'typescript'].
        """
        found: set[str] = set()

        for path in self._iter_files():
            lang = _EXT_TO_LANGUAGE.get(path.suffix.lower())
            if lang:
                found.add(lang)

        return sorted(found)

    def _iter_files(self) -> "Generator[Path, None, None]":
        """Iterate over project files, skipping ignored directories."""
        try:
            for item in self.project_root.rglob("*"):
                # Skip if any parent component is in the skip list
                if any(part in _SKIP_DIRS for part in item.parts):
                    continue
                if item.is_file():
                    yield item
        except PermissionError:
            pass
