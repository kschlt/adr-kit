"""Tests for frontmatter writing in the ADR supersede workflow.

Covers both insertion sites (`_update_old_adr_status` writes `superseded_by`,
`_update_new_adr_relationships` writes `supersedes`) and both branches at each
site: field already present (the `re.sub` path) and field absent (the
previously corrupting `else` path).
"""

import re
from pathlib import Path
from typing import Any

import yaml

from adr_kit.core.parse import parse_adr_file
from adr_kit.decision.workflows.supersede import SupersedeWorkflow

# Last frontmatter field is followed directly by the closing fence. This is the
# shape adr-kit itself writes, and the one that used to corrupt.
OLD_NORMAL_SHAPE = """---
id: ADR-0001
title: Use MySQL for primary storage
date: 2026-07-15
status: accepted
---

## Context

Testing frontmatter integrity.
"""

NEW_NORMAL_SHAPE = """---
id: ADR-0002
title: Use PostgreSQL for primary storage
date: 2026-07-16
status: proposed
---

## Context

Testing frontmatter integrity.
"""

# A blank line before the closing fence used to mask the bug, because the slice
# then ended on a newline by accident. These shapes pass even against unfixed
# code — they document the masking condition.
OLD_BLANK_LINE_SHAPE = OLD_NORMAL_SHAPE.replace(
    "status: accepted\n---", "status: accepted\n\n---"
)
NEW_BLANK_LINE_SHAPE = NEW_NORMAL_SHAPE.replace(
    "status: proposed\n---", "status: proposed\n\n---"
)

# Field already present: exercises the re.sub replacement branch instead of the
# insertion branch.
OLD_WITH_FIELD_SHAPE = OLD_NORMAL_SHAPE.replace(
    "status: accepted\n---", 'status: accepted\nsuperseded_by: ["ADR-0009"]\n---'
)
NEW_WITH_FIELD_SHAPE = NEW_NORMAL_SHAPE.replace(
    "status: proposed\n---", "status: proposed\nsupersedes: []\n---"
)

# A trailing space after the closing fence dashes still parses (the parser's
# fence regex is `---\s*\n`) but makes `content.find("\n---\n")` return -1 —
# the not-found sentinel path, where the guard must skip insertion entirely.
OLD_TRAILING_SPACE_FENCE = OLD_NORMAL_SHAPE.replace(
    "status: accepted\n---\n", "status: accepted\n--- \n"
)
NEW_TRAILING_SPACE_FENCE = NEW_NORMAL_SHAPE.replace(
    "status: proposed\n---\n", "status: proposed\n--- \n"
)


def _write_adr(adr_dir: Path, name: str, content: str) -> Path:
    file_path = adr_dir / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


def _frontmatter_of(file_path: Path) -> Any:
    """Parse the frontmatter block as YAML, raising if it is not valid."""
    raw = file_path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", raw, re.DOTALL)
    assert match is not None, "closing frontmatter fence not found"
    return yaml.safe_load(match.group(1))


def _supersede_old(adr_dir: Path, file_path: Path) -> None:
    """Run insertion site 1: mark the old ADR superseded by ADR-0002."""
    adr = parse_adr_file(file_path)
    workflow = SupersedeWorkflow(adr_dir=adr_dir)
    workflow._update_old_adr_status(
        old_adr=adr,
        old_adr_file=file_path,
        new_adr_id="ADR-0002",
        reason="MySQL licensing limitations",
    )


def _supersede_new(adr_dir: Path) -> None:
    """Run insertion site 2: record that ADR-0002 supersedes ADR-0001."""
    workflow = SupersedeWorkflow(adr_dir=adr_dir)
    workflow._update_new_adr_relationships(new_adr_id="ADR-0002", old_adr_id="ADR-0001")


# --- Site 1: _update_old_adr_status writes superseded_by -----------------


def test_old_adr_field_absent_normal_shape_produces_valid_yaml(
    tmp_path: Path,
) -> None:
    file_path = _write_adr(tmp_path, "ADR-0001-use-mysql.md", OLD_NORMAL_SHAPE)

    _supersede_old(tmp_path, file_path)

    # Against the unfixed writer this raises: the metadata was welded onto the
    # status value, producing "status: acceptedsuperseded_by: ...".
    parsed = _frontmatter_of(file_path)
    assert parsed["status"] == "superseded"
    assert parsed["superseded_by"] == ["ADR-0002"]
    assert parsed["supersede_reason"] == "MySQL licensing limitations"
    assert "supersede_date" in parsed
    assert parsed["title"] == "Use MySQL for primary storage"


def test_old_adr_reparses_through_normal_parse_path(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, "ADR-0001-use-mysql.md", OLD_NORMAL_SHAPE)

    _supersede_old(tmp_path, file_path)

    reparsed = parse_adr_file(file_path)
    assert reparsed.front_matter.status == "superseded"
    assert reparsed.id == "ADR-0001"


def test_old_adr_field_present_replaces_in_place(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, "ADR-0001-use-mysql.md", OLD_WITH_FIELD_SHAPE)

    _supersede_old(tmp_path, file_path)

    parsed = _frontmatter_of(file_path)
    assert parsed["status"] == "superseded"
    assert parsed["superseded_by"] == ["ADR-0002"]
    # The replacement branch only rewrites the existing line — it does not add
    # the supersede_date/supersede_reason metadata.
    assert "supersede_date" not in parsed


def test_old_adr_blank_line_shape_produces_valid_yaml(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, "ADR-0001-use-mysql.md", OLD_BLANK_LINE_SHAPE)

    _supersede_old(tmp_path, file_path)

    parsed = _frontmatter_of(file_path)
    assert parsed["status"] == "superseded"
    assert parsed["superseded_by"] == ["ADR-0002"]


def test_old_adr_without_closing_fence_match_skips_insertion(
    tmp_path: Path,
) -> None:
    file_path = _write_adr(tmp_path, "ADR-0001-use-mysql.md", OLD_TRAILING_SPACE_FENCE)

    _supersede_old(tmp_path, file_path)

    # Only the status line is rewritten; the guard must skip the insertion.
    raw = file_path.read_text(encoding="utf-8")
    assert raw == OLD_TRAILING_SPACE_FENCE.replace(
        "status: accepted", "status: superseded"
    )


# --- Site 2: _update_new_adr_relationships writes supersedes -------------


def test_new_adr_field_absent_normal_shape_produces_valid_yaml(
    tmp_path: Path,
) -> None:
    file_path = _write_adr(tmp_path, "ADR-0002-use-postgresql.md", NEW_NORMAL_SHAPE)

    _supersede_new(tmp_path)

    # Against the unfixed writer this raises: the supersedes line was welded
    # onto the status value, producing "status: proposedsupersedes: ...".
    parsed = _frontmatter_of(file_path)
    assert parsed["supersedes"] == ["ADR-0001"]
    assert parsed["status"] == "proposed"
    assert parsed["title"] == "Use PostgreSQL for primary storage"


def test_new_adr_reparses_through_normal_parse_path(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, "ADR-0002-use-postgresql.md", NEW_NORMAL_SHAPE)

    _supersede_new(tmp_path)

    reparsed = parse_adr_file(file_path)
    assert reparsed.front_matter.supersedes == ["ADR-0001"]
    assert reparsed.id == "ADR-0002"


def test_new_adr_field_present_replaces_in_place(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, "ADR-0002-use-postgresql.md", NEW_WITH_FIELD_SHAPE)

    _supersede_new(tmp_path)

    parsed = _frontmatter_of(file_path)
    assert parsed["supersedes"] == ["ADR-0001"]
    assert parsed["status"] == "proposed"


def test_new_adr_blank_line_shape_produces_valid_yaml(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, "ADR-0002-use-postgresql.md", NEW_BLANK_LINE_SHAPE)

    _supersede_new(tmp_path)

    parsed = _frontmatter_of(file_path)
    assert parsed["supersedes"] == ["ADR-0001"]
    assert parsed["status"] == "proposed"


def test_new_adr_without_closing_fence_match_skips_insertion(
    tmp_path: Path,
) -> None:
    file_path = _write_adr(
        tmp_path, "ADR-0002-use-postgresql.md", NEW_TRAILING_SPACE_FENCE
    )

    _supersede_new(tmp_path)

    # The guard must skip the insertion and leave the file byte-identical.
    raw = file_path.read_text(encoding="utf-8")
    assert raw == NEW_TRAILING_SPACE_FENCE
