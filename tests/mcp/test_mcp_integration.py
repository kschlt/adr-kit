"""Integration tests for MCP server functionality."""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Import FastMCP client for proper testing
from fastmcp import Client

from adr_kit.mcp.models import (
    AnalyzeProjectRequest,
    ApproveADRRequest,
    CreateADRRequest,
    PlanningContextRequest,
    PreflightCheckRequest,
    SupersedeADRRequest,
)

# Import the MCP server instance for testing
from adr_kit.mcp.server import mcp


@pytest.fixture
def temp_adr_dir():
    """Create a temporary ADR directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        adr_dir = Path(tmpdir) / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        yield str(adr_dir)


@pytest.fixture
def sample_project_dir():
    """Create a temporary project directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create a sample package.json
        package_json = {
            "name": "test-project",
            "dependencies": {"react": "^18.0.0", "express": "^4.18.0"},
        }
        with open(project_dir / "package.json", "w") as f:
            json.dump(package_json, f)

        yield str(project_dir)


def assert_success_response(response: dict[str, Any]) -> None:
    """Assert that response follows success format."""
    assert response["status"] == "success"
    assert "message" in response
    assert "data" in response
    assert "next_steps" in response
    assert "metadata" in response


def assert_error_response(response: dict[str, Any]) -> None:
    """Assert that response follows error format."""
    assert response["status"] == "error"
    assert "error" in response
    assert "details" in response
    assert "suggested_action" in response


class TestAnalyzeProject:
    """Test adr_analyze_project tool."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_analyze_existing_project(self, sample_project_dir, temp_adr_dir):
        """Test analyzing a project with existing files."""
        request = AnalyzeProjectRequest(
            project_path=sample_project_dir,
            focus_areas=["frontend"],
            adr_dir=temp_adr_dir,
        )

        async with Client(mcp) as client:
            # Use the Client to call the tool with correct parameter structure
            result = await client.call_tool(
                "adr_analyze_project", {"request": request.model_dump()}
            )

            # FastMCP returns CallToolResult with content list
            assert result is not None
            assert hasattr(result, "content")
            assert len(result.content) > 0

            # Extract JSON from the first content block
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_success_response(response)

            data = response["data"]
            assert "analysis_prompt" in data
            assert "project_context" in data
            assert "existing_adr_count" in data
            assert "detected_technologies" in data

        # Should detect React and Express
        assert "React" in str(data["project_context"])

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_analyze_nonexistent_project(self, temp_adr_dir):
        """Test analyzing a project that doesn't exist."""
        request = AnalyzeProjectRequest(
            project_path="/nonexistent/path", adr_dir=temp_adr_dir
        )

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_analyze_project", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_error_response(response)
            # Check that error indicates analysis failure and details mention path issue
            assert response["error"].lower() in [
                "project analysis failed",
                "analysis failed",
            ]
            assert (
                "not found" in response["details"].lower()
                or "nonexistent" in response["details"].lower()
                or "does not exist" in response["details"].lower()
            )


class TestPreflight:
    """Test adr_preflight tool."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_preflight_simple_choice(self, temp_adr_dir):
        """Test preflight check for a simple technical choice."""
        request = PreflightCheckRequest(
            choice="lodash", category="library", adr_dir=temp_adr_dir
        )

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_preflight", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_success_response(response)

        data = response["data"]
        assert data["decision"] in ["ALLOWED", "REQUIRES_ADR", "BLOCKED"]
        assert "reasoning" in data
        assert "conflicting_adrs" in data
        assert "related_adrs" in data
        assert "urgency" in data

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_preflight_significant_choice(self, temp_adr_dir):
        """Test preflight check for significant architectural choice."""
        request = PreflightCheckRequest(
            choice="PostgreSQL", category="database", adr_dir=temp_adr_dir
        )

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_preflight", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_success_response(response)

            data = response["data"]
            # Database choices should typically require ADR
            assert data["decision"] in ["REQUIRES_ADR", "BLOCKED"]


class TestCreateADR:
    """Test adr_create tool."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_create_basic_adr(self, temp_adr_dir):
        """Test creating a basic ADR."""
        request = CreateADRRequest(
            title="Use PostgreSQL for primary database",
            context="We need a reliable database for user data",
            decision="Use PostgreSQL as our primary database",
            consequences="Better data integrity, more complex setup",
            adr_dir=temp_adr_dir,
        )

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_create", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_success_response(response)

            data = response["data"]
            assert data["adr_id"].startswith("ADR-")
            assert data["status"] == "proposed"
            assert Path(data["file_path"]).exists()

            # Verify file content
            with open(data["file_path"]) as f:
                content = f.read()
                assert "PostgreSQL" in content
                assert "status: proposed" in content

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_create_adr_with_policy(self, temp_adr_dir):
        """Test creating ADR with policy block."""
        request = CreateADRRequest(
            title="Use React for frontend",
            context="Need modern frontend framework",
            decision="Use React for all frontend development",
            consequences="Modern UI, learning curve",
            policy={"imports": {"prefer": ["react"], "disallow": ["vue", "angular"]}},
            adr_dir=temp_adr_dir,
        )

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_create", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_success_response(response)

            # Verify policy is in file
            data = response["data"]
            with open(data["file_path"]) as f:
                content = f.read()
                assert "policy:" in content
                assert "imports:" in content
                # Verify policy dict is present (handles both YAML and dict repr)
                assert "prefer" in content or "'prefer'" in content
                assert "react" in content.lower()


class TestApproveADR:
    """Test adr_approve tool."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_approve_proposed_adr(self, temp_adr_dir):
        """Test approving a proposed ADR."""
        # First create an ADR
        create_request = CreateADRRequest(
            title="Use Redis for caching",
            context="Need fast caching solution",
            decision="Use Redis for application caching",
            consequences="Better performance, additional infrastructure",
            adr_dir=temp_adr_dir,
        )

        async with Client(mcp) as client:
            create_result = await client.call_tool(
                "adr_create", {"request": create_request.model_dump()}
            )
            create_response = json.loads(create_result.content[0].text)
            adr_id = create_response["data"]["adr_id"]

            # Now approve it
            approve_request = ApproveADRRequest(
                adr_id=adr_id, approval_notes="Approved by team", adr_dir=temp_adr_dir
            )

            approve_result = await client.call_tool(
                "adr_approve", {"request": approve_request.model_dump()}
            )
            response = json.loads(approve_result.content[0].text)
            assert_success_response(response)

            data = response["data"]
            assert data["status"] == "approved"
            assert data["adr_id"] == adr_id

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_approve_nonexistent_adr(self, temp_adr_dir):
        """Test approving an ADR that doesn't exist."""
        request = ApproveADRRequest(adr_id="ADR-9999", adr_dir=temp_adr_dir)

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_approve", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_error_response(response)
            # Check that error indicates approval failure and details mention ADR not found
            assert response["error"].lower() in [
                "adr approval failed",
                "approval failed",
            ]
            assert (
                "not found" in response["details"].lower()
                or "does not exist" in response["details"].lower()
            )


class TestSupersede:
    """Test adr_supersede tool."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_supersede_existing_adr(self, temp_adr_dir):
        """Test superseding an existing ADR."""
        # First create and approve an ADR
        create_request = CreateADRRequest(
            title="Use MySQL for database",
            context="Need relational database",
            decision="Use MySQL for data storage",
            consequences="Good performance, licensing concerns",
            adr_dir=temp_adr_dir,
        )

        async with Client(mcp) as client:
            create_result = await client.call_tool(
                "adr_create", {"request": create_request.model_dump()}
            )
            create_response = json.loads(create_result.content[0].text)
            old_adr_id = create_response["data"]["adr_id"]

            approve_request = ApproveADRRequest(adr_id=old_adr_id, adr_dir=temp_adr_dir)
            await client.call_tool(
                "adr_approve", {"request": approve_request.model_dump()}
            )

            # Now supersede it
            supersede_request = SupersedeADRRequest(
                old_adr_id=old_adr_id,
                new_title="Use PostgreSQL for database",
                new_context="MySQL licensing issues arose",
                new_decision="Migrate to PostgreSQL",
                new_consequences="Better licensing, migration effort",
                supersede_reason="MySQL licensing concerns",
                adr_dir=temp_adr_dir,
            )

            supersede_result = await client.call_tool(
                "adr_supersede", {"request": supersede_request.model_dump()}
            )
            response = json.loads(supersede_result.content[0].text)
            assert_success_response(response)

            data = response["data"]
            assert data["old_adr_id"] == old_adr_id
            assert data["new_adr_id"].startswith("ADR-")
            # old_status shows status BEFORE superseding (should be "accepted" since we approved it)
            assert data["old_status"] in ["proposed", "accepted"]

            # Verify the old ADR file now has superseded status
            # Files are named like "ADR-0001-use-mysql-for-database.md"
            adr_dir_path = Path(temp_adr_dir)
            adr_files = list(adr_dir_path.glob(f"{old_adr_id}-*.md"))
            assert (
                len(adr_files) > 0
            ), f"Old ADR file {old_adr_id}-*.md not found in {temp_adr_dir}"
            old_adr_file = adr_files[0]
            with open(old_adr_file) as f:
                updated_content = f.read()
                assert "status: superseded" in updated_content


class TestPlanningContext:
    """Test adr_planning_context tool."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_planning_context_basic(self, temp_adr_dir):
        """Test getting planning context for a task."""
        request = PlanningContextRequest(
            task_description="Implement user authentication system",
            context_type="implementation",
            domain_hints=["backend", "security"],
            adr_dir=temp_adr_dir,
        )

        async with Client(mcp) as client:
            result = await client.call_tool(
                "adr_planning_context", {"request": request.model_dump()}
            )
            content_block = result.content[0]
            response = json.loads(content_block.text)
            assert_success_response(response)

            data = response["data"]
            assert "relevant_adrs" in data
            assert "constraints" in data
            assert "guidance" in data
            assert "use_technologies" in data
            assert "avoid_technologies" in data
            assert "patterns" in data
            assert "checklist" in data


class TestEndToEndWorkflow:
    """Test complete ADR workflow."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_complete_adr_workflow(self, temp_adr_dir, sample_project_dir):
        """Test complete workflow: analyze -> preflight -> create -> approve."""
        async with Client(mcp) as client:
            # Step 1: Analyze project
            analyze_request = AnalyzeProjectRequest(
                project_path=sample_project_dir, adr_dir=temp_adr_dir
            )
            analyze_result = await client.call_tool(
                "adr_analyze_project", {"request": analyze_request.model_dump()}
            )
            analyze_response = json.loads(analyze_result.content[0].text)
            assert_success_response(analyze_response)

            # Step 2: Preflight check
            preflight_request = PreflightCheckRequest(
                choice="React", category="frontend", adr_dir=temp_adr_dir
            )
            preflight_result = await client.call_tool(
                "adr_preflight", {"request": preflight_request.model_dump()}
            )
            preflight_response = json.loads(preflight_result.content[0].text)
            assert_success_response(preflight_response)

            # Step 3: Create ADR
            create_request = CreateADRRequest(
                title="Use React for frontend development",
                context="Modern frontend framework needed",
                decision="Use React for all frontend components",
                consequences="Better user experience, steeper learning curve",
                tags=["frontend", "javascript"],
                adr_dir=temp_adr_dir,
            )
            create_result = await client.call_tool(
                "adr_create", {"request": create_request.model_dump()}
            )
            create_response = json.loads(create_result.content[0].text)
            assert_success_response(create_response)
            adr_id = create_response["data"]["adr_id"]

            # Step 4: Approve ADR
            approve_request = ApproveADRRequest(adr_id=adr_id, adr_dir=temp_adr_dir)
            approve_result = await client.call_tool(
                "adr_approve", {"request": approve_request.model_dump()}
            )
            approve_response = json.loads(approve_result.content[0].text)
            assert_success_response(approve_response)

            # Step 5: Get planning context (should now include our ADR)
            planning_request = PlanningContextRequest(
                task_description="Build user dashboard component",
                context_type="implementation",
                domain_hints=["frontend"],
                adr_dir=temp_adr_dir,
            )
            planning_result = await client.call_tool(
                "adr_planning_context", {"request": planning_request.model_dump()}
            )
            planning_response = json.loads(planning_result.content[0].text)
            assert_success_response(planning_response)

        # Should find our React ADR as relevant
        relevant_adrs = planning_response["data"]["relevant_adrs"]
        assert len(relevant_adrs) > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
