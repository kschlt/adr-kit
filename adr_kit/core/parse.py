"""Parser for ADR Markdown files with YAML front-matter.

Design decisions:
- Use PyYAML for robust YAML parsing of front-matter
- Support both strict and lenient parsing modes
- Provide clear error messages for malformed files
- Extract both front-matter and content cleanly
"""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .model import ADR, ADRFrontMatter


class ParseError(Exception):
    """Exception raised when ADR parsing fails."""

    def __init__(self, message: str, file_path: Path | str | None = None):
        self.file_path = file_path
        super().__init__(message)

    def __str__(self) -> str:
        if self.file_path:
            return f"Parse error in {self.file_path}: {super().__str__()}"
        return super().__str__()


def parse_front_matter(
    content: str, file_path: Path | str | None = None
) -> tuple[dict[str, Any], str]:
    """Parse YAML front-matter from markdown content.

    Args:
        content: The full markdown content including front-matter
        file_path: Optional file path for error reporting

    Returns:
        Tuple of (front_matter_dict, remaining_content)

    Raises:
        ParseError: If front-matter is malformed or missing
    """
    # Pattern to match YAML front-matter between --- delimiters
    front_matter_pattern = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL | re.MULTILINE
    )

    match = front_matter_pattern.match(content)
    if not match:
        raise ParseError(
            "No YAML front-matter found. ADR files must start with ---", file_path
        )

    yaml_content, markdown_content = match.groups()

    try:
        front_matter = yaml.safe_load(yaml_content)
        if front_matter is None:
            raise ParseError("Empty front-matter section", file_path)
        if not isinstance(front_matter, dict):
            raise ParseError("Front-matter must be a YAML object", file_path)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML in front-matter: {e}", file_path) from e

    return front_matter, markdown_content.strip()


def parse_adr_file(file_path: Path | str, strict: bool = True) -> ADR:
    """Parse an ADR markdown file into an ADR object.

    Args:
        file_path: Path to the ADR markdown file
        strict: If True, perform full validation. If False, allow some validation errors

    Returns:
        ADR object with parsed data

    Raises:
        ParseError: If file cannot be read or parsed
        ValidationError: If ADR data doesn't match schema (when strict=True)
    """
    path_obj = Path(file_path)

    if not path_obj.exists():
        raise ParseError(f"File not found: {path_obj}", file_path)

    if not path_obj.is_file():
        raise ParseError(f"Not a file: {path_obj}", file_path)

    try:
        content = path_obj.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ParseError(f"File encoding error: {e}", file_path) from e
    except OSError as e:
        raise ParseError(f"Cannot read file: {e}", file_path) from e

    try:
        front_matter_dict, markdown_content = parse_front_matter(content, file_path)

        # Create front-matter object
        if strict:
            front_matter = ADRFrontMatter(**front_matter_dict)
        else:
            try:
                front_matter = ADRFrontMatter(**front_matter_dict)
            except ValidationError as e:
                # In non-strict mode, log the validation error but continue
                # This allows for partial ADR processing during development
                print(f"Warning: Validation error in {file_path}: {e}")
                front_matter = ADRFrontMatter(**front_matter_dict)

        return ADR(
            front_matter=front_matter, content=markdown_content, file_path=path_obj
        )

    except ValidationError as e:
        if strict:
            raise ParseError(f"ADR validation failed: {e}", file_path) from e
        else:
            # Re-raise validation errors in strict mode
            raise


def parse_adr_content(
    content: str, file_path: Path | str | None = None, strict: bool = True
) -> ADR:
    """Parse ADR content from a string.

    Args:
        content: The full markdown content including front-matter
        file_path: Optional file path for error reporting
        strict: If True, perform full validation

    Returns:
        ADR object with parsed data

    Raises:
        ParseError: If content cannot be parsed
        ValidationError: If ADR data doesn't match schema (when strict=True)
    """
    try:
        front_matter_dict, markdown_content = parse_front_matter(content, file_path)

        if strict:
            front_matter = ADRFrontMatter(**front_matter_dict)
        else:
            try:
                front_matter = ADRFrontMatter(**front_matter_dict)
            except ValidationError as e:
                print(f"Warning: Validation error: {e}")
                front_matter = ADRFrontMatter(**front_matter_dict)

        return ADR(
            front_matter=front_matter,
            content=markdown_content,
            file_path=Path(file_path) if file_path else None,
        )

    except ValidationError as e:
        if strict:
            raise ParseError(f"ADR validation failed: {e}", file_path) from e
        else:
            raise


def find_adr_files(
    directory: Path | str = "docs/adr", pattern: str = "ADR-*.md"
) -> list[Path]:
    """Find ADR files in a directory.

    Args:
        directory: Directory to search for ADR files
        pattern: Glob pattern to match ADR files

    Returns:
        List of Path objects for found ADR files
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    return sorted(dir_path.glob(pattern))
