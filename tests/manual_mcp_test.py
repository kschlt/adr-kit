#!/usr/bin/env python3
"""Manual test script for ADR Kit MCP server with middleware fix.

This script tests that the middleware correctly fixes stringified JSON parameters
from buggy MCP clients (Claude Code, Cursor) while remaining compatible with
clients that send parameters correctly.

Run this script after making changes to verify the middleware works.
"""

import asyncio
import json
import sys

# Import from installed package (no path manipulation needed)
from adr_kit.mcp.server import mcp


async def test_tool(tool_name: str, test_cases: list[dict]) -> None:
    """Test a tool with multiple parameter formats.

    Args:
        tool_name: Name of the tool to test
        test_cases: List of test case dicts with 'name', 'args', 'should_work'
    """
    print(f"\n{'=' * 80}")
    print(f"Testing: {tool_name}")
    print(f"{'=' * 80}")

    tools = await mcp.get_tools()
    tool = tools.get(tool_name)

    if not tool:
        print(f"❌ Tool '{tool_name}' not found!")
        return

    for i, test_case in enumerate(test_cases, 1):
        name = test_case["name"]
        args = test_case["args"]
        should_work = test_case.get("should_work", True)

        print(f"\n--- Test Case {i}: {name} ---")
        print(f"Arguments: {json.dumps(args, indent=2)}")

        try:
            result = await tool.run(args)
            if should_work:
                print(f"✅ SUCCESS: Tool executed correctly")
                print(f"   Result type: {type(result).__name__}")
            else:
                print(f"⚠️  UNEXPECTED: Tool succeeded but was expected to fail")
        except Exception as e:
            if not should_work:
                print(f"✅ EXPECTED FAILURE: {type(e).__name__}: {e}")
            else:
                print(f"❌ FAILED: {type(e).__name__}: {e}")


async def main() -> None:
    """Run all MCP tool tests."""
    print("=" * 80)
    print("ADR Kit MCP Server - Middleware Fix Test")
    print("=" * 80)
    print("\nThis tests that the middleware fixes stringified JSON parameters")
    print("from buggy MCP clients (Claude Code, Cursor).")
    print("")

    # Test 1: adr_preflight - simplest tool with basic parameters
    await test_tool(
        "adr_preflight",
        [
            {
                "name": "Normal (object) - Should work",
                "args": {
                    "request": {
                        "choice": "postgresql",
                        "category": "database",
                        "adr_dir": "docs/adr",
                    }
                },
                "should_work": True,
            },
            {
                "name": "Stringified (buggy client) - Middleware should fix",
                "args": {
                    "request": '{"choice": "postgresql", "category": "database", "adr_dir": "docs/adr"}'
                },
                "should_work": True,
            },
            {
                "name": "Stringified with context dict - Complex case",
                "args": {
                    "request": '{"choice": "react", "context": {"frontend": true, "spa": true}}'
                },
                "should_work": True,
            },
        ],
    )

    # Test 2: adr_create - more complex with nested data
    await test_tool(
        "adr_create",
        [
            {
                "name": "Normal (object) - Should work",
                "args": {
                    "request": {
                        "title": "Use PostgreSQL for Database",
                        "context": "We need a reliable database",
                        "decision": "We will use PostgreSQL",
                        "consequences": "Better reliability",
                        "deciders": ["team"],
                        "tags": ["database"],
                        "adr_dir": "docs/adr",
                    }
                },
                "should_work": True,
            },
            {
                "name": "Stringified (buggy client) - Middleware should fix",
                "args": {
                    "request": '{"title": "Use PostgreSQL", "context": "Need database", "decision": "Use PostgreSQL", "consequences": "Reliable", "deciders": ["team"], "tags": ["database"], "adr_dir": "docs/adr"}'
                },
                "should_work": True,
            },
        ],
    )

    # Test 3: adr_planning_context - moderate complexity
    await test_tool(
        "adr_planning_context",
        [
            {
                "name": "Normal (object) - Should work",
                "args": {
                    "request": {
                        "task_description": "Build a REST API",
                        "context_type": "implementation",
                        "domain_hints": ["backend", "api"],
                        "adr_dir": "docs/adr",
                    }
                },
                "should_work": True,
            },
            {
                "name": "Stringified (buggy client) - Middleware should fix",
                "args": {
                    "request": '{"task_description": "Build a REST API", "context_type": "implementation", "domain_hints": ["backend", "api"], "adr_dir": "docs/adr"}'
                },
                "should_work": True,
            },
        ],
    )

    # Test 4: adr_approve - simple parameters
    await test_tool(
        "adr_approve",
        [
            {
                "name": "Normal (object) - Should work",
                "args": {
                    "request": {
                        "adr_id": "ADR-0001",
                        "approval_notes": "Looks good",
                        "adr_dir": "docs/adr",
                    }
                },
                "should_work": True,
            },
            {
                "name": "Stringified (buggy client) - Middleware should fix",
                "args": {
                    "request": '{"adr_id": "ADR-0001", "approval_notes": "Approved", "adr_dir": "docs/adr"}'
                },
                "should_work": True,
            },
        ],
    )

    # Test 5: adr_analyze_project - with optional parameters
    await test_tool(
        "adr_analyze_project",
        [
            {
                "name": "Normal (object) - Should work",
                "args": {"request": {"focus_areas": ["backend"], "adr_dir": "docs/adr"}},
                "should_work": True,
            },
            {
                "name": "Stringified (buggy client) - Middleware should fix",
                "args": {
                    "request": '{"focus_areas": ["backend"], "adr_dir": "docs/adr"}'
                },
                "should_work": True,
            },
        ],
    )

    # Test 6: adr_supersede - most complex tool with many parameters
    await test_tool(
        "adr_supersede",
        [
            {
                "name": "Normal (object) - Should work",
                "args": {
                    "request": {
                        "old_adr_id": "ADR-0001",
                        "new_title": "Updated Decision",
                        "new_context": "Requirements changed",
                        "new_decision": "Use MySQL instead",
                        "new_consequences": "Different tradeoffs",
                        "supersede_reason": "Business requirements changed",
                        "new_deciders": ["team"],
                        "new_tags": ["database"],
                        "adr_dir": "docs/adr",
                    }
                },
                "should_work": True,
            },
            {
                "name": "Stringified (buggy client) - Middleware should fix",
                "args": {
                    "request": '{"old_adr_id": "ADR-0001", "new_title": "Updated", "new_context": "Changed", "new_decision": "Use MySQL", "new_consequences": "Different", "supersede_reason": "Changed", "new_deciders": ["team"], "new_tags": ["db"], "adr_dir": "docs/adr"}'
                },
                "should_work": True,
            },
        ],
    )

    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print("\n✅ If all tests passed, the middleware is working correctly!")
    print("   - Normal object parameters work")
    print("   - Stringified parameters are fixed by middleware")
    print("   - All 6 tools are compatible with buggy MCP clients")
    print("")
    print("🔧 The middleware makes ADR Kit work with:")
    print("   - Claude Code (has stringification bug)")
    print("   - Cursor (has stringification bug)")
    print("   - Any other MCP client (forwards compatibility)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
