"""Verification script for policy extraction issue.

This script reproduces the issue reported in .agent/issues/adr-kit-mcp-issue.md:
- ADRs created without policy structure
- Constraint extraction returns empty results
- No warnings or feedback provided
"""

import tempfile
from pathlib import Path

from adr_kit.core.model import ADR, ADRFrontMatter, ADRStatus, PolicyModel
from adr_kit.core.policy_extractor import PolicyExtractor
from adr_kit.workflows.creation import CreationInput, CreationWorkflow


def test_adr_without_policy():
    """Test Case 1: ADR without policy (mimics agent behavior from issue report)."""
    print("\n" + "=" * 70)
    print("TEST 1: ADR without policy (BAD - like the issue report)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = CreationWorkflow(adr_dir=tmpdir)

        # Create ADR exactly as the agent did in the issue report
        input_data = CreationInput(
            title="Use FastAPI as Web Framework",
            context="This project's backend needs a Python web framework with async support.",
            decision="Use FastAPI as the backend web framework. Leverage FastAPI's built-in Pydantic integration.",
            consequences="""### Positive
- Native async/await support
- Automatic OpenAPI/Swagger documentation
- Excellent documentation and large community

### Negative
- Smaller ecosystem compared to Django/Flask
- Team needs understanding of async Python patterns""",
            alternatives="""### Django + Django REST Framework
- Rejected: More opinionated and heavier for API-only use case

### Flask
- Rejected: Less integrated type safety and validation
- Async support is a bolt-on rather than native

### Litestar
- Rejected: Smaller community despite similar features""",
            tags=["backend", "framework", "python", "fastapi"],
            deciders=["architect"],
            # NOTE: NO POLICY PROVIDED - this is the problem!
        )

        result = workflow.execute(input_data=input_data)

        if result.success:
            print(f"✅ ADR created: {result.data['creation_result'].adr_id}")
            print(
                f"📄 File: {result.data['creation_result'].file_path}"
            )

            # Check validation warnings
            warnings = result.data["creation_result"].validation_warnings
            print(f"\n⚠️  Validation Warnings: {len(warnings)}")
            for warning in warnings:
                print(f"    - {warning}")

            # Try to extract policy
            adr_file = Path(result.data["creation_result"].file_path)
            from adr_kit.core.parse import parse_adr_file

            adr = parse_adr_file(adr_file)
            extractor = PolicyExtractor()
            policy = extractor.extract_policy(adr)

            print(f"\n🔍 Policy Extraction Results:")
            print(f"    - Disallowed imports: {policy.get_disallowed_imports()}")
            print(f"    - Preferred imports: {policy.get_preferred_imports()}")
            print(f"    - Has extractable policy: {extractor.has_extractable_policy(adr)}")

            if not extractor.has_extractable_policy(adr):
                print(
                    "\n❌ PROBLEM CONFIRMED: No constraints extracted! "
                    "adr_planning_context would return constraints: []"
                )
                if not warnings:
                    print(
                        "❌ WORSE: No warnings provided! Silent failure."
                    )
        else:
            print(f"❌ Creation failed: {result.errors}")


def test_adr_with_structured_policy():
    """Test Case 2: ADR with structured policy (GOOD - should work)."""
    print("\n" + "=" * 70)
    print("TEST 2: ADR with structured policy (GOOD - should extract constraints)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = CreationWorkflow(adr_dir=tmpdir)

        input_data = CreationInput(
            title="Use FastAPI as Web Framework",
            context="This project's backend needs a Python web framework with async support.",
            decision="Use FastAPI as the backend web framework.",
            consequences="Native async support and automatic OpenAPI documentation.",
            alternatives="Django/Flask rejected due to lack of native async support.",
            tags=["backend", "framework"],
            deciders=["architect"],
            # STRUCTURED POLICY PROVIDED - this should work!
            policy={
                "imports": {
                    "disallow": ["flask", "django", "litestar"],
                    "prefer": ["fastapi"],
                },
                "python": {"disallow_imports": ["flask", "django"]},
                "rationales": [
                    "FastAPI provides native async support required for I/O operations",
                    "Automatic OpenAPI documentation reduces maintenance burden",
                ],
            },
        )

        result = workflow.execute(input_data=input_data)

        if result.success:
            print(f"✅ ADR created: {result.data['creation_result'].adr_id}")

            # Try to extract policy
            adr_file = Path(result.data["creation_result"].file_path)
            from adr_kit.core.parse import parse_adr_file

            adr = parse_adr_file(adr_file)
            extractor = PolicyExtractor()
            policy = extractor.extract_policy(adr)

            print(f"\n🔍 Policy Extraction Results:")
            print(f"    - Disallowed imports: {policy.get_disallowed_imports()}")
            print(f"    - Preferred imports: {policy.get_preferred_imports()}")
            print(f"    - Has extractable policy: {extractor.has_extractable_policy(adr)}")

            if extractor.has_extractable_policy(adr):
                print("\n✅ SUCCESS: Constraints extracted! adr_planning_context would work.")
            else:
                print(
                    "\n❌ UNEXPECTED: Policy provided but extraction failed!"
                )
        else:
            print(f"❌ Creation failed: {result.errors}")


def test_adr_with_pattern_language():
    """Test Case 3: ADR with pattern-matching language (SHOULD work)."""
    print("\n" + "=" * 70)
    print("TEST 3: ADR with pattern-matching language (should extract via patterns)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = CreationWorkflow(adr_dir=tmpdir)

        input_data = CreationInput(
            title="Use FastAPI as Web Framework",
            context="This project's backend needs a Python web framework with async support.",
            decision="""Use FastAPI as the backend web framework. **Don't use Flask**
or Django as they lack native async support. **Prefer FastAPI over Flask** for this use case.""",
            consequences="""**Avoid** synchronous frameworks like Flask.
Backend **should not use** Django REST Framework.""",
            alternatives="Rejected Flask and Django.",
            tags=["backend"],
            deciders=["architect"],
            # NO STRUCTURED POLICY - but using pattern-friendly language
        )

        result = workflow.execute(input_data=input_data)

        if result.success:
            print(f"✅ ADR created: {result.data['creation_result'].adr_id}")

            # Try to extract policy
            adr_file = Path(result.data["creation_result"].file_path)
            from adr_kit.core.parse import parse_adr_file

            adr = parse_adr_file(adr_file)
            extractor = PolicyExtractor()
            policy = extractor.extract_policy(adr)

            print(f"\n🔍 Policy Extraction Results:")
            print(f"    - Disallowed imports: {policy.get_disallowed_imports()}")
            print(f"    - Preferred imports: {policy.get_preferred_imports()}")
            print(f"    - Has extractable policy: {extractor.has_extractable_policy(adr)}")

            if extractor.has_extractable_policy(adr):
                print("\n✅ SUCCESS: Patterns detected! Constraint extraction works.")
            else:
                print(
                    "\n⚠️  PARTIAL: Pattern-matching failed. May need better patterns."
                )
        else:
            print(f"❌ Creation failed: {result.errors}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("VERIFICATION: ADR Kit Policy Extraction Issue")
    print("Reproducing the issue from: .agent/issues/adr-kit-mcp-issue.md")
    print("=" * 70)

    test_adr_without_policy()
    test_adr_with_structured_policy()
    test_adr_with_pattern_language()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)
    print(
        """
Expected Results:
- Test 1: Should show NO constraints extracted + NO warnings (❌ PROBLEM)
- Test 2: Should show constraints extracted (✅ WORKS)
- Test 3: Should show constraints extracted via patterns (✅ WORKS if patterns match)

Next Steps:
1. Confirm Test 1 demonstrates the problem
2. Implement validation warnings
3. Update MCP documentation
"""
    )
