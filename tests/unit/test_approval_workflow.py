"""Tests for frontmatter writing in the ADR approval workflow."""

import re
from pathlib import Path
from typing import Any

import yaml

from adr_kit.core.parse import parse_adr_file
from adr_kit.decision.workflows.approval import ApprovalInput, ApprovalWorkflow

# Last frontmatter field is followed directly by the closing fence. This is the
# shape adr-kit itself writes, and the one that used to corrupt.
NORMAL_SHAPE = """---
id: ADR-0001
title: Use PostgreSQL for primary storage
date: 2026-07-15
status: proposed
---

## Context

Testing frontmatter integrity.
"""

# A blank line before the closing fence used to mask the bug, because the slice
# then ended on a newline by accident.
BLANK_LINE_SHAPE = NORMAL_SHAPE.replace(
    "status: proposed\n---", "status: proposed\n\n---"
)


def _write_adr(adr_dir: Path, content: str) -> Path:
    file_path = adr_dir / "ADR-0001-use-postgresql.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def _frontmatter_of(file_path: Path) -> Any:
    """Parse the frontmatter block as YAML, raising if it is not valid."""
    raw = file_path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", raw, re.DOTALL)
    assert match is not None, "closing frontmatter fence not found"
    return yaml.safe_load(match.group(1))


def _approve(adr_dir: Path, file_path: Path, notes: str | None) -> None:
    adr = parse_adr_file(file_path)
    workflow = ApprovalWorkflow(adr_dir=adr_dir)
    workflow._update_adr_status(
        adr=adr,
        file_path=str(file_path),
        input_data=ApprovalInput(adr_id=adr.id, approval_notes=notes),
    )


def test_approve_with_notes_normal_shape_produces_valid_yaml(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, NORMAL_SHAPE)

    _approve(tmp_path, file_path, "Approved for testing")

    # Against the unfixed writer this raises: the metadata was welded onto the
    # status value, producing "status: acceptedapproval_date: ...".
    parsed = _frontmatter_of(file_path)
    assert parsed["status"] == "accepted"
    assert parsed["approval_notes"] == "Approved for testing"
    assert "approval_date" in parsed
    assert parsed["title"] == "Use PostgreSQL for primary storage"


def test_approve_with_notes_reparses_through_normal_parse_path(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, NORMAL_SHAPE)

    _approve(tmp_path, file_path, "Approved for testing")

    reparsed = parse_adr_file(file_path)
    assert reparsed.front_matter.status == "accepted"
    assert reparsed.id == "ADR-0001"


def test_approve_with_notes_blank_line_shape_produces_valid_yaml(
    tmp_path: Path,
) -> None:
    file_path = _write_adr(tmp_path, BLANK_LINE_SHAPE)

    _approve(tmp_path, file_path, "Approved for testing")

    parsed = _frontmatter_of(file_path)
    assert parsed["status"] == "accepted"
    assert parsed["approval_notes"] == "Approved for testing"
    assert "approval_date" in parsed


def test_approve_without_notes_only_rewrites_the_status_line(tmp_path: Path) -> None:
    file_path = _write_adr(tmp_path, NORMAL_SHAPE)

    _approve(tmp_path, file_path, None)

    raw = file_path.read_text(encoding="utf-8")
    assert raw == NORMAL_SHAPE.replace("status: proposed", "status: accepted")
