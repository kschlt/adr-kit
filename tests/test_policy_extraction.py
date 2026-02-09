"""Tests for policy extraction from structured blocks and pattern matching.

This test file specifically addresses Issue #2 from the feedback tracking:
Testing whether adr_preflight correctly extracts policies from structured
policy blocks in ADR frontmatter.
"""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from adr_kit.contract.builder import ConstraintsContractBuilder
from adr_kit.core.model import (
    ADR,
    ADRFrontMatter,
    ADRStatus,
    ImportPolicy,
    PolicyModel,
    PythonPolicy,
)
from adr_kit.core.policy_extractor import PolicyExtractor
from adr_kit.workflows.preflight import PreflightInput, PreflightWorkflow


class TestPolicyExtraction:
    """Test suite for verifying policy extraction from structured blocks."""

    def test_correct_policy_format_extraction(self, tmp_path: Path) -> None:
        """Test that policies are extracted correctly from proper format.

        This tests the CORRECT format that ADR Kit expects.
        """
        # Create ADR with CORRECT policy format
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI for Backend",
            status=ADRStatus.ACCEPTED,
            date=date(2025, 1, 1),
            deciders=["team"],
            policy=PolicyModel(
                imports=ImportPolicy(
                    disallow=["flask", "django"],  # ✅ Correct location
                    prefer=["fastapi"],  # ✅ Correct field name
                ),
                python=PythonPolicy(
                    disallow_imports=["bottle"]  # ✅ Correct field name
                ),
                rationales=["FastAPI provides async support", "Automatic OpenAPI"],
            ),
        )

        content = """## Context

We need a modern async Python framework.

## Decision

Use FastAPI as the backend framework.

## Consequences

Better async support, automatic OpenAPI docs.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        # Test policy extractor
        extractor = PolicyExtractor()
        policy = extractor.extract_policy(adr)

        # Verify extraction
        assert policy.imports is not None
        assert policy.imports.disallow == ["flask", "django"]
        assert policy.imports.prefer == ["fastapi"]
        assert policy.python is not None
        assert policy.python.disallow_imports == ["bottle"]
        assert policy.rationales == [
            "FastAPI provides async support",
            "Automatic OpenAPI",
        ]

    def test_incorrect_user_policy_format(self, tmp_path: Path) -> None:
        """Test the INCORRECT format that the user in Issue #2 used.

        This format has issues:
        1. Uses 'prefer_imports' instead of putting preferences in 'imports' block
        2. Has extra fields like 'patterns', 'typescript', 'files' that aren't in schema
        """
        # This is what the user tried (won't work correctly)
        # Note: We can't actually create this with Pydantic because it validates
        # So this test documents what the issue was

        # The user's frontmatter looked like this (pseudo-code):
        # policy:
        #   python:
        #     disallow_imports: [flask, django]
        #     prefer_imports: [fastapi]  # ❌ Wrong field
        #     patterns: {...}  # ❌ Not in schema
        #   typescript: {...}  # ❌ Not in schema
        #   files: {...}  # ❌ Not in schema

        # The correct approach is to use separate policy blocks:
        correct_policy = PolicyModel(
            imports=ImportPolicy(disallow=["flask", "django"], prefer=["fastapi"]),
            python=PythonPolicy(disallow_imports=["flask", "django"]),
        )

        # Verify the correct structure
        assert correct_policy.imports is not None
        assert correct_policy.imports.prefer == ["fastapi"]
        assert correct_policy.python is not None
        assert correct_policy.python.disallow_imports == ["flask", "django"]

    def test_preflight_with_correct_policy_format(self, tmp_path: Path) -> None:
        """Test that preflight correctly uses policies from ADRs."""
        # Setup: Create ADR directory with approved ADR
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with correct policy
        front_matter = ADRFrontMatter(
            id="ADR-0001",
            title="Use FastAPI for Backend",
            status=ADRStatus.ACCEPTED,
            date=date(2025, 1, 1),
            deciders=["team"],
            policy=PolicyModel(
                imports=ImportPolicy(disallow=["flask", "django"], prefer=["fastapi"]),
            ),
        )

        content = """## Context

We need a modern async Python framework.

## Decision

Use FastAPI as the backend framework. Don't use Flask or Django.

## Consequences

Better async support.
"""

        adr = ADR(
            front_matter=front_matter,
            content=content,
        )

        adr_file = adr_dir / "ADR-0001-use-fastapi.md"
        with open(adr_file, "w") as f:
            f.write(adr.to_markdown())

        # Build constraints contract
        builder = ConstraintsContractBuilder(adr_dir=adr_dir)
        contract = builder.build()

        # Verify contract has the policies
        assert contract.constraints.imports is not None
        assert "flask" in contract.constraints.imports.disallow
        assert "django" in contract.constraints.imports.disallow
        assert "fastapi" in contract.constraints.imports.prefer

        # Test preflight with BLOCKED choice (flask)
        workflow = PreflightWorkflow(adr_dir=adr_dir)
        preflight_input = PreflightInput(choice="flask", category="backend")

        result = workflow.execute(input_data=preflight_input)

        # Verify result
        assert result.success
        decision = result.data["decision"]

        # This should be BLOCKED because flask is disallowed
        assert decision.status == "BLOCKED"
        assert len(decision.conflicting_adrs) > 0
        assert "ADR-0001" in decision.conflicting_adrs

    def test_preflight_with_allowed_choice(self, tmp_path: Path) -> None:
        """Test that preflight allows choices that match preferred imports."""
        # Setup
        adr_dir = tmp_path / "docs/adr"
        adr_dir.mkdir(parents=True)

        # Create ADR with FastAPI as preferred
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI for Backend",
                status=ADRStatus.ACCEPTED,
                date=date(2025, 1, 1),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(disallow=["flask"], prefer=["fastapi"]),
                ),
            ),
            content="""## Context
We need an async framework.

## Decision
Use FastAPI.

## Consequences
Better performance.
""",
        )

        with open(adr_dir / "ADR-0001-fastapi.md", "w") as f:
            f.write(adr.to_markdown())

        # Test preflight with FastAPI (should be allowed or requires_adr)
        workflow = PreflightWorkflow(adr_dir=adr_dir)
        preflight_input = PreflightInput(choice="fastapi", category="backend")

        result = workflow.execute(input_data=preflight_input)

        # FastAPI shouldn't be BLOCKED since it's preferred
        assert result.success
        decision = result.data["decision"]
        assert decision.status != "BLOCKED"

    def test_pattern_matching_fallback(self, tmp_path: Path) -> None:
        """Test that pattern matching works when no structured policy exists."""
        # Create ADR with NO structured policy, only text patterns
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use React for Frontend",
                status=ADRStatus.ACCEPTED,
                date=date(2025, 1, 1),
                deciders=["team"],
                # No policy block!
            ),
            content="""## Context
Need frontend framework.

## Decision
Use React for the frontend. Don't use Vue or Angular as they don't fit our needs.

## Consequences
Large ecosystem, good developer experience.
""",
        )

        # Test pattern extraction
        extractor = PolicyExtractor()
        policy = extractor.extract_policy(adr)

        # Pattern matching should extract "vue" and "angular" as disallowed
        assert policy.imports is not None
        # Note: Pattern matching extracts from "Don't use X" patterns
        # Check case-insensitively since extraction preserves original case
        disallow_lower = [d.lower() for d in (policy.imports.disallow or [])]
        assert "vue" in disallow_lower or "angular" in disallow_lower

    def test_policy_extraction_priority(self, tmp_path: Path) -> None:
        """Test that structured policy takes priority over pattern matching."""
        # Create ADR with BOTH structured policy AND text patterns
        adr = ADR(
            front_matter=ADRFrontMatter(
                id="ADR-0001",
                title="Use FastAPI",
                status=ADRStatus.ACCEPTED,
                date=date(2025, 1, 1),
                deciders=["team"],
                policy=PolicyModel(
                    imports=ImportPolicy(
                        disallow=["flask"], prefer=["fastapi"]  # Structured
                    ),
                ),
            ),
            content="""## Context
Need framework.

## Decision
Use FastAPI. Don't use Django.

## Consequences
Good choice.
""",
        )

        extractor = PolicyExtractor()
        policy = extractor.extract_policy(adr)

        # Structured policy should be used
        assert policy.imports is not None
        assert policy.imports.disallow == ["flask"]  # From structured, not "django"
        assert policy.imports.prefer == ["fastapi"]


class TestPolicyFormatDocumentation:
    """Tests documenting the correct vs incorrect policy formats."""

    def test_correct_import_policy_format(self) -> None:
        """Document the CORRECT format for import policies."""
        # ✅ CORRECT - imports block at top level
        correct = PolicyModel(
            imports=ImportPolicy(disallow=["axios", "jquery"], prefer=["fetch"]),
            rationales=["Better native support", "Smaller bundle size"],
        )

        assert correct.imports.disallow == ["axios", "jquery"]
        assert correct.imports.prefer == ["fetch"]

    def test_correct_python_policy_format(self) -> None:
        """Document the CORRECT format for Python-specific policies."""
        # ✅ CORRECT - python block for Python-specific imports
        correct = PolicyModel(
            python=PythonPolicy(disallow_imports=["flask", "django"]),
            imports=ImportPolicy(prefer=["fastapi"]),  # General preferences go here
            rationales=["FastAPI has better async support"],
        )

        assert correct.python.disallow_imports == ["flask", "django"]
        assert correct.imports.prefer == ["fastapi"]

    def test_complete_policy_example(self) -> None:
        """Full example of correct policy format."""
        # ✅ COMPLETE CORRECT EXAMPLE
        policy = PolicyModel(
            imports=ImportPolicy(
                disallow=[
                    "axios",  # Don't use axios
                    "moment",  # Don't use moment.js
                ],
                prefer=[
                    "fetch",  # Use native fetch
                    "date-fns",  # Use date-fns instead of moment
                ],
            ),
            python=PythonPolicy(
                disallow_imports=[
                    "flask",  # Don't use Flask
                    "bottle",  # Don't use Bottle
                ]
            ),
            rationales=[
                "Reduce bundle size by using native APIs",
                "FastAPI provides better async support than Flask",
            ],
        )

        # Verify structure
        assert len(policy.imports.disallow) == 2
        assert len(policy.imports.prefer) == 2
        assert len(policy.python.disallow_imports) == 2
        assert len(policy.rationales) == 2
