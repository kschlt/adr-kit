"""JSON index generation for ADRs.

Design decisions:
- Generate machine-readable JSON index for ADR queries and MCP consumption
- Include summary data with relationships between ADRs
- Support filtering and searching via the index
- Maintain compatibility with Log4brains and other tools
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..core.model import ADR, ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from ..core.validate import validate_adr_file


class IndexEntry:
    """Represents a single ADR in the JSON index."""

    def __init__(self, adr: ADR):
        self.adr = adr

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        fm = self.adr.front_matter

        # Convert date to ISO string
        date_str = fm.date.isoformat() if isinstance(fm.date, date) else str(fm.date)

        return {
            "id": fm.id,
            "title": fm.title,
            "status": (
                fm.status.value if isinstance(fm.status, ADRStatus) else str(fm.status)
            ),
            "date": date_str,
            "deciders": fm.deciders or [],
            "tags": fm.tags or [],
            "supersedes": fm.supersedes or [],
            "superseded_by": fm.superseded_by or [],
            "file_path": str(self.adr.file_path) if self.adr.file_path else None,
            "content_preview": self._get_content_preview(),
        }

    def _get_content_preview(self, max_length: int = 200) -> str:
        """Extract a preview of the ADR content."""
        # Remove markdown headers and get first paragraph
        lines = self.adr.content.split("\n")
        content_lines = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                content_lines.append(line)
                if len(" ".join(content_lines)) > max_length:
                    break

        preview = " ".join(content_lines)
        if len(preview) > max_length:
            preview = preview[:max_length].rsplit(" ", 1)[0] + "..."

        return preview


class ADRIndex:
    """JSON index generator for ADRs."""

    def __init__(self, adr_directory: Path | str = "docs/adr"):
        self.adr_directory = Path(adr_directory)
        self.entries: list[IndexEntry] = []
        self.metadata: dict[str, Any] = {}

    def build_index(self, validate: bool = True) -> None:
        """Build the ADR index from files in the directory.

        Args:
            validate: If True, only include valid ADRs in the index
        """
        self.entries = []
        errors = []

        adr_files = find_adr_files(self.adr_directory)

        for file_path in adr_files:
            try:
                if validate:
                    # Validate the ADR first
                    result = validate_adr_file(file_path)
                    if not result.is_valid:
                        errors.append(
                            {
                                "file": str(file_path),
                                "errors": [str(issue) for issue in result.errors],
                            }
                        )
                        continue
                    adr = result.adr
                else:
                    # Just parse without validation
                    adr = parse_adr_file(file_path, strict=False)

                if adr:
                    self.entries.append(IndexEntry(adr))

            except ParseError as e:
                errors.append({"file": str(file_path), "errors": [str(e)]})

        # Sort entries by ID
        self.entries.sort(key=lambda entry: entry.adr.front_matter.id)

        # Build metadata
        self.metadata = {
            "generated_at": datetime.now().isoformat(),
            "total_adrs": len(self.entries),
            "adr_directory": str(self.adr_directory),
            "validation_errors": errors if errors else None,
            "status_counts": self._calculate_status_counts(),
            "tag_counts": self._calculate_tag_counts(),
        }

    def _calculate_status_counts(self) -> dict[str, int]:
        """Calculate count of ADRs by status."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            status = entry.adr.front_matter.status
            status_str = status.value if isinstance(status, ADRStatus) else str(status)
            counts[status_str] = counts.get(status_str, 0) + 1
        return counts

    def _calculate_tag_counts(self) -> dict[str, int]:
        """Calculate count of ADRs by tag."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            tags = entry.adr.front_matter.tags or []
            for tag in tags:
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Convert index to dictionary for JSON serialization."""
        return {
            "metadata": self.metadata,
            "adrs": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert index to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save_to_file(self, output_path: Path | str, indent: int = 2) -> None:
        """Save index to JSON file.

        Args:
            output_path: Path where to save the JSON index
            indent: JSON indentation for pretty printing
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent, ensure_ascii=False)

    def filter_by_status(
        self, status: ADRStatus | str | list[ADRStatus | str]
    ) -> list[IndexEntry]:
        """Filter index entries by status.

        Args:
            status: Single status or list of statuses to filter by

        Returns:
            Filtered list of index entries
        """
        if isinstance(status, str | ADRStatus):
            status = [status]

        status_strings = []
        for s in status:
            if isinstance(s, ADRStatus):
                status_strings.append(s.value)
            else:
                status_strings.append(str(s))

        return [
            entry
            for entry in self.entries
            if str(entry.adr.front_matter.status) in status_strings
        ]

    def filter_by_tags(
        self, tags: str | list[str], match_all: bool = False
    ) -> list[IndexEntry]:
        """Filter index entries by tags.

        Args:
            tags: Single tag or list of tags to filter by
            match_all: If True, ADR must have all tags. If False, any tag matches.

        Returns:
            Filtered list of index entries
        """
        if isinstance(tags, str):
            tags = [tags]

        filtered = []
        for entry in self.entries:
            adr_tags = entry.adr.front_matter.tags or []

            if match_all:
                if all(tag in adr_tags for tag in tags):
                    filtered.append(entry)
            else:
                if any(tag in adr_tags for tag in tags):
                    filtered.append(entry)

        return filtered

    def find_by_id(self, adr_id: str) -> IndexEntry | None:
        """Find an ADR entry by ID.

        Args:
            adr_id: The ADR ID to search for

        Returns:
            IndexEntry if found, None otherwise
        """
        for entry in self.entries:
            if entry.adr.front_matter.id == adr_id:
                return entry
        return None


def generate_adr_index(
    adr_directory: Path | str = "docs/adr",
    output_path: Path | str = "docs/adr/adr-index.json",
    validate: bool = True,
    indent: int = 2,
) -> ADRIndex:
    """Generate and save ADR JSON index.

    Args:
        adr_directory: Directory containing ADR files
        output_path: Path where to save the JSON index
        validate: If True, validate ADRs before indexing
        indent: JSON indentation for pretty printing

    Returns:
        ADRIndex object with generated index
    """
    index = ADRIndex(adr_directory)
    index.build_index(validate=validate)
    index.save_to_file(output_path, indent=indent)
    return index
