"""Unit tests for decision quality guidance."""

from adr_kit.workflows.decision_guidance import _build_examples, build_decision_guidance


class TestDecisionGuidance:
    """Test decision quality guidance generation."""

    def test_build_decision_guidance_basic(self):
        """Test basic decision guidance structure."""
        guidance = build_decision_guidance(include_examples=False)

        # Check top-level structure
        assert "agent_task" in guidance
        assert "adr_structure" in guidance
        assert "quality_criteria" in guidance
        assert "anti_patterns" in guidance
        assert "example_workflow" in guidance
        assert "connection_to_task_2" in guidance
        assert "dos_and_donts" in guidance
        assert "next_steps" in guidance

    def test_agent_task_structure(self):
        """Test agent task definition."""
        guidance = build_decision_guidance(include_examples=False)
        agent_task = guidance["agent_task"]

        assert agent_task["role"] == "Architectural Decision Documenter"
        assert "objective" in agent_task
        assert "reasoning_steps" in agent_task
        assert len(agent_task["reasoning_steps"]) == 6
        assert "focus" in agent_task

    def test_adr_structure_sections(self):
        """Test ADR structure guidance covers all sections."""
        guidance = build_decision_guidance(include_examples=False)
        sections = guidance["adr_structure"]["sections"]

        # Check all required sections present
        assert "context" in sections
        assert "decision" in sections
        assert "consequences" in sections
        assert "alternatives" in sections

        # Check context section details
        context = sections["context"]
        assert (
            context["purpose"]
            == "WHY this decision is needed - the problem or opportunity"
        )
        assert context["required"] is True
        assert "what_to_include" in context
        assert "what_to_avoid" in context
        assert "quality_bar" in context

    def test_quality_criteria_complete(self):
        """Test quality criteria are comprehensive."""
        guidance = build_decision_guidance(include_examples=False)
        criteria = guidance["quality_criteria"]

        # Check all quality dimensions
        assert "specific" in criteria
        assert "actionable" in criteria
        assert "complete" in criteria
        assert "policy_ready" in criteria
        assert "balanced" in criteria

        # Each criterion should have structure
        for criterion in criteria.values():
            assert "description" in criterion
            assert "good" in criterion
            assert "bad" in criterion
            assert "why_it_matters" in criterion

    def test_anti_patterns_with_fixes(self):
        """Test anti-patterns include fixes."""
        guidance = build_decision_guidance(include_examples=False)
        anti_patterns = guidance["anti_patterns"]

        # Check key anti-patterns
        assert "too_vague" in anti_patterns
        assert "no_trade_offs" in anti_patterns
        assert "missing_context" in anti_patterns
        assert "no_alternatives" in anti_patterns
        assert "weak_constraints" in anti_patterns

        # Each pattern should show bad → good → fix
        for pattern in anti_patterns.values():
            assert "bad" in pattern
            assert "good" in pattern
            assert "fix" in pattern

    def test_example_workflow_shows_good_vs_bad(self):
        """Test example workflow demonstrates quality difference."""
        guidance = build_decision_guidance(include_examples=False)
        workflow = guidance["example_workflow"]

        assert "scenario" in workflow
        assert "bad_adr" in workflow
        assert "good_adr" in workflow
        assert "key_insight" in workflow

        # Bad example should show problems
        bad = workflow["bad_adr"]
        assert "why_bad" in bad
        assert "task_2_result" in bad
        assert len(bad["why_bad"]) > 0

        # Good example should show strengths
        good = workflow["good_adr"]
        assert "why_good" in good
        assert "task_2_result" in good
        assert len(good["why_good"]) > 0

    def test_connection_to_task_2(self):
        """Test guidance explains Task 1 → Task 2 connection."""
        guidance = build_decision_guidance(include_examples=False)
        connection = guidance["connection_to_task_2"]

        assert "overview" in connection
        assert "how_task_1_enables_task_2" in connection
        assert "best_practices" in connection

        # Check policy mapping examples
        examples = connection["how_task_1_enables_task_2"]
        assert len(examples) >= 4  # imports, patterns, architecture, config

        for example in examples:
            assert "decision_pattern" in example
            assert "extracted_policy" in example
            assert "principle" in example

    def test_dos_and_donts_lists(self):
        """Test dos and don'ts are actionable."""
        guidance = build_decision_guidance(include_examples=False)
        dos_donts = guidance["dos_and_donts"]

        assert "dos" in dos_donts
        assert "donts" in dos_donts

        # Should have multiple items
        assert len(dos_donts["dos"]) >= 6
        assert len(dos_donts["donts"]) >= 6

        # Dos should start with ✅
        for item in dos_donts["dos"]:
            assert item.startswith("✅")

        # Don'ts should start with ❌
        for item in dos_donts["donts"]:
            assert item.startswith("❌")

    def test_examples_included_by_default(self):
        """Test examples are included by default."""
        guidance = build_decision_guidance(include_examples=True)
        assert "examples" in guidance

    def test_examples_excluded_when_disabled(self):
        """Test examples can be excluded."""
        guidance = build_decision_guidance(include_examples=False)
        assert "examples" not in guidance

    def test_examples_have_categories(self):
        """Test examples cover different focus areas."""
        examples = _build_examples(focus_area=None)

        assert "by_category" in examples
        assert "database" in examples["by_category"]
        assert "frontend" in examples["by_category"]
        assert "generic" in examples["by_category"]

        # Each category should have good and bad
        for category in examples["by_category"].values():
            assert "good" in category
            assert "bad" in category

    def test_focused_examples_database(self):
        """Test focused examples for database."""
        examples = _build_examples(focus_area="database")

        assert "focus" in examples
        assert examples["focus"] == "database"
        assert "good_example" in examples
        assert "bad_example" in examples
        assert "comparison" in examples

        # Good example should be comprehensive
        good = examples["good_example"]
        assert "title" in good
        assert "context" in good
        assert "decision" in good
        assert "consequences" in good
        assert "alternatives" in good

        # Should be database-related
        assert (
            "database" in good["title"].lower() or "postgresql" in good["title"].lower()
        )

    def test_focused_examples_frontend(self):
        """Test focused examples for frontend."""
        examples = _build_examples(focus_area="frontend")

        assert examples["focus"] == "frontend"
        good = examples["good_example"]

        # Should be frontend-related
        assert (
            "frontend" in good["title"].lower()
            or "react" in good["title"].lower()
            or "vue" in good["title"].lower()
        )

    def test_next_steps_provided(self):
        """Test guidance includes clear next steps."""
        guidance = build_decision_guidance(include_examples=False)

        assert "next_steps" in guidance
        steps = guidance["next_steps"]

        # Should have multiple steps
        assert len(steps) >= 3

        # Steps should be numbered
        assert any("1." in step for step in steps)
        assert any("2." in step for step in steps)
