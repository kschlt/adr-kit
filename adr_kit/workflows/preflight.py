"""Preflight Workflow - Check if technical choice requires ADR before proceeding."""

from dataclasses import dataclass
from typing import Any

from ..contract.builder import ConstraintsContractBuilder
from ..contract.models import ConstraintsContract
from .base import BaseWorkflow, WorkflowResult


@dataclass
class PreflightInput:
    """Input for preflight workflow."""

    choice: str  # Technical choice being evaluated (e.g., "postgresql", "react", "microservices")
    context: dict[str, Any] | None = None  # Additional context about the choice
    category: str | None = (
        None  # Category hint (database, frontend, architecture, etc.)
    )


@dataclass
class PreflightDecision:
    """Result of preflight evaluation."""

    status: str  # ALLOWED, REQUIRES_ADR, BLOCKED
    reasoning: str  # Human-readable explanation
    conflicting_adrs: list[str]  # ADR IDs that conflict with this choice
    related_adrs: list[str]  # ADR IDs that are related but don't conflict
    required_policies: list[str]  # Policies that would need to be addressed in ADR
    next_steps: str  # What the agent should do next
    urgency: str  # LOW, MEDIUM, HIGH - how important it is to create ADR


class PreflightWorkflow(BaseWorkflow):
    """
    Preflight Workflow evaluates technical choices against existing ADRs.

    This is one of the most important entry points for agents - it prevents
    architectural violations before they happen and guides agents toward
    compliant technical choices.

    Workflow Steps:
    1. Load current constraints contract
    2. Categorize the technical choice
    3. Check against existing policy gates
    4. Identify conflicting and related ADRs
    5. Evaluate if choice requires new ADR
    6. Generate actionable guidance for agent
    """

    def execute(self, **kwargs: Any) -> WorkflowResult:
        """Execute preflight evaluation workflow."""
        # Extract input_data from kwargs
        input_data = kwargs.get("input_data")
        if not input_data or not isinstance(input_data, PreflightInput):
            raise ValueError("input_data must be provided as PreflightInput instance")

        self._start_workflow("Preflight Check")

        try:
            # Step 1: Load constraints contract
            contract = self._execute_step(
                "load_constraints_contract", self._load_constraints_contract
            )

            # Step 2: Categorize and normalize choice
            categorized_choice = self._execute_step(
                "categorize_choice", self._categorize_choice, input_data
            )

            # Step 3: Check against policy gates
            gate_result = self._execute_step(
                "check_policy_gates",
                self._check_policy_gates,
                categorized_choice,
                contract,
            )

            # Step 4: Find related and conflicting ADRs
            related_adrs = self._execute_step(
                "find_related_adrs",
                self._find_related_adrs,
                categorized_choice,
                contract,
            )
            conflicting_adrs = self._execute_step(
                "find_conflicting_adrs",
                self._find_conflicting_adrs,
                categorized_choice,
                contract,
            )

            # Step 5: Evaluate decision
            decision = self._execute_step(
                "make_preflight_decision",
                self._make_preflight_decision,
                categorized_choice,
                gate_result,
                related_adrs,
                conflicting_adrs,
                contract,
            )

            # Step 6: Generate guidance
            guidance = self._execute_step(
                "generate_agent_guidance",
                self._generate_agent_guidance,
                decision,
                input_data,
            )

            result_data = {
                "decision": decision,
                "guidance": guidance,
                "technical_choice": categorized_choice,
                "evaluated_against": {
                    "total_adrs": len(contract.approved_adrs),
                    "constraints_exist": not contract.constraints.is_empty(),
                    "constraints": 1 if not contract.constraints.is_empty() else 0,
                },
            }

            self._complete_workflow(
                success=True,
                message=f"Preflight check completed: {decision.status}",
            )
            self.result.data = result_data
            self.result.guidance = guidance
            self.result.next_steps = (
                decision.next_steps.split(". ")
                if hasattr(decision, "next_steps") and decision.next_steps
                else [
                    f"Technical choice {input_data.choice} evaluated: {decision.status}",
                    "Review preflight decision and proceed accordingly",
                ]
            )

        except Exception as e:
            self._complete_workflow(
                success=False,
                message=f"Preflight workflow failed: {str(e)}",
            )
            self.result.add_error(f"PreflightError: {str(e)}")

        return self.result

    def _load_constraints_contract(self) -> ConstraintsContract:
        """Load current constraints contract from approved ADRs."""
        try:
            builder = ConstraintsContractBuilder(adr_dir=self.adr_dir)
            return builder.build()
        except Exception:
            # If no contract exists, return empty contract
            from pathlib import Path

            from ..contract.models import ConstraintsContract

            # Use the proper create_empty method instead of incorrect constructor
            return ConstraintsContract.create_empty(Path("."))

    def _categorize_choice(self, input_data: PreflightInput) -> dict[str, Any]:
        """Categorize and normalize the technical choice."""
        choice = input_data.choice.lower().strip()

        # Common technology categories
        database_terms = {
            "postgresql",
            "postgres",
            "mysql",
            "mongodb",
            "redis",
            "sqlite",
            "cassandra",
            "dynamodb",
            "elasticsearch",
        }
        frontend_terms = {
            "react",
            "vue",
            "angular",
            "svelte",
            "next.js",
            "nuxt",
            "gatsby",
            "typescript",
            "javascript",
            "tailwind",
            "bootstrap",
        }
        backend_terms = {
            "express",
            "fastapi",
            "django",
            "flask",
            "spring",
            "rails",
            "node.js",
            "python",
            "java",
            "go",
            "rust",
        }
        architecture_terms = {
            "microservices",
            "monolith",
            "serverless",
            "event-driven",
            "rest",
            "graphql",
            "grpc",
            "kubernetes",
            "docker",
        }

        # Determine category
        category = input_data.category
        if not category:
            if choice in database_terms:
                category = "database"
            elif choice in frontend_terms:
                category = "frontend"
            elif choice in backend_terms:
                category = "backend"
            elif choice in architecture_terms:
                category = "architecture"
            else:
                category = "technology"

        return {
            "original": input_data.choice,
            "normalized": choice,
            "category": category,
            "context": input_data.context or {},
            "aliases": self._get_technology_aliases(choice),
        }

    def _get_technology_aliases(self, choice: str) -> list[str]:
        """Get common aliases for a technology choice."""
        alias_map = {
            "postgres": ["postgresql", "pg"],
            "postgresql": ["postgres", "pg"],
            "javascript": ["js", "node", "node.js"],
            "typescript": ["ts"],
            "react": ["reactjs", "react.js"],
            "vue": ["vuejs", "vue.js"],
            "next.js": ["nextjs", "next"],
            "nuxt": ["nuxtjs", "nuxt.js"],
        }
        return alias_map.get(choice, [choice])

    def _check_policy_gates(
        self, choice: dict[str, Any], contract: ConstraintsContract
    ) -> dict[str, Any]:
        """Check choice against existing policy gates."""
        # Simplified gate checking - will be enhanced later
        # This would integrate with the actual PolicyGate system when fully implemented

        blocked = False
        pre_approved = False
        requirements: list[str] = []

        # Basic implementation - check against contract constraints
        if not contract.constraints.is_empty():
            # Simple check for blocked technologies in constraints
            constraint_text = str(contract.constraints.model_dump()).lower()
            if choice["normalized"] in constraint_text:
                # This is a very basic check - real implementation would be more sophisticated
                pass

        return {
            "blocked": blocked,
            "pre_approved": pre_approved,
            "requirements": requirements,
            "applicable_gates": [],
        }

    def _find_related_adrs(
        self, choice: dict[str, Any], contract: ConstraintsContract
    ) -> list[dict[str, Any]]:
        """Find ADRs related to this technical choice."""
        related = []

        for adr in contract.approved_adrs:
            # Check title and tags
            tags_text = " ".join(adr.tags) if adr.tags else ""
            adr_text = f"{adr.title.lower()} {tags_text.lower()}"

            # Check if choice or aliases appear in ADR
            if choice["normalized"] in adr_text:
                related.append(
                    {
                        "adr_id": adr.id,
                        "title": adr.title,
                        "relevance": "direct_mention",
                        "category_match": choice["category"] in (adr.tags or []),
                    }
                )
                continue

            # Check aliases
            for alias in choice["aliases"]:
                if alias in adr_text:
                    related.append(
                        {
                            "adr_id": adr.id,
                            "title": adr.title,
                            "relevance": "alias_match",
                            "category_match": choice["category"] in (adr.tags or []),
                        }
                    )
                    break

        return related

    def _find_conflicting_adrs(
        self, choice: dict[str, Any], contract: ConstraintsContract
    ) -> list[dict[str, Any]]:
        """Find ADRs that conflict with this technical choice."""
        conflicts = []

        for adr in contract.approved_adrs:
            # Check policy blocks
            if adr.policy:
                policy = adr.policy

                # Check disallowed imports/technologies
                disallowed = []
                if policy.imports and policy.imports.disallow:
                    disallowed.extend(policy.imports.disallow)
                if policy.python and policy.python.disallow_imports:
                    disallowed.extend(policy.python.disallow_imports)

                # Check if choice conflicts
                choice_terms = [choice["normalized"]] + choice["aliases"]
                for term in choice_terms:
                    if term in [d.lower() for d in disallowed]:
                        conflicts.append(
                            {
                                "adr_id": adr.id,
                                "title": adr.title,
                                "conflict_type": "policy_disallow",
                                "conflict_detail": f"ADR disallows '{term}'",
                            }
                        )

        return conflicts

    def _make_preflight_decision(
        self,
        choice: dict[str, Any],
        gate_result: dict[str, Any],
        related_adrs: list[dict[str, Any]],
        conflicting_adrs: list[dict[str, Any]],
        contract: ConstraintsContract,
    ) -> PreflightDecision:
        """Make the final preflight decision."""

        # BLOCKED - explicit conflicts found
        if conflicting_adrs:
            return PreflightDecision(
                status="BLOCKED",
                reasoning=f"Choice '{choice['original']}' conflicts with existing ADRs",
                conflicting_adrs=[c["adr_id"] for c in conflicting_adrs],
                related_adrs=[r["adr_id"] for r in related_adrs],
                required_policies=[],
                next_steps="Review conflicting ADRs and consider superseding them if this choice is necessary",
                urgency="HIGH",
            )

        # BLOCKED - policy gate blocks
        if gate_result["blocked"]:
            return PreflightDecision(
                status="BLOCKED",
                reasoning=f"Choice '{choice['original']}' is blocked by policy gates",
                conflicting_adrs=[],
                related_adrs=[r["adr_id"] for r in related_adrs],
                required_policies=gate_result["requirements"],
                next_steps="Review policy gates and consider updating them if this choice is necessary",
                urgency="HIGH",
            )

        # ALLOWED - pre-approved choice
        if gate_result["pre_approved"]:
            return PreflightDecision(
                status="ALLOWED",
                reasoning=f"Choice '{choice['original']}' is pre-approved by existing ADRs",
                conflicting_adrs=[],
                related_adrs=[r["adr_id"] for r in related_adrs],
                required_policies=[],
                next_steps="Proceed with implementation",
                urgency="LOW",
            )

        # REQUIRES_ADR - significant choice not covered
        if self._is_significant_choice(choice, related_adrs, contract):
            return PreflightDecision(
                status="REQUIRES_ADR",
                reasoning=f"Choice '{choice['original']}' is architecturally significant and requires ADR",
                conflicting_adrs=[],
                related_adrs=[r["adr_id"] for r in related_adrs],
                required_policies=self._suggest_required_policies(choice),
                next_steps="Create ADR proposal documenting this architectural decision",
                urgency="MEDIUM",
            )

        # ALLOWED - minor choice, proceed
        return PreflightDecision(
            status="ALLOWED",
            reasoning=f"Choice '{choice['original']}' is minor and doesn't require ADR",
            conflicting_adrs=[],
            related_adrs=[r["adr_id"] for r in related_adrs],
            required_policies=[],
            next_steps="Proceed with implementation",
            urgency="LOW",
        )

    def _is_significant_choice(
        self,
        choice: dict[str, Any],
        related_adrs: list[dict[str, Any]],
        contract: ConstraintsContract,
    ) -> bool:
        """Determine if a technical choice is significant enough to require ADR."""

        # Always significant categories
        significant_categories = {"database", "architecture", "framework"}
        if choice["category"] in significant_categories:
            return True

        # Frontend frameworks are significant
        frontend_frameworks = {"react", "vue", "angular", "svelte"}
        if choice["normalized"] in frontend_frameworks:
            return True

        # Backend frameworks are significant
        backend_frameworks = {"express", "fastapi", "django", "flask", "spring"}
        if choice["normalized"] in backend_frameworks:
            return True

        # If no existing ADRs, even minor choices might be worth documenting
        if len(contract.approved_adrs) == 0:
            return True

        return False

    def _suggest_required_policies(self, choice: dict[str, Any]) -> list[str]:
        """Suggest policies that should be included in ADR for this choice."""
        policies = []

        category = choice["category"]
        choice["normalized"]

        if category == "database":
            policies.extend(
                [
                    "Database access patterns",
                    "Migration strategy",
                    "Backup and recovery approach",
                    "Connection pooling configuration",
                ]
            )
        elif category == "frontend":
            policies.extend(
                [
                    "Component structure guidelines",
                    "State management approach",
                    "Styling methodology",
                    "Bundle size constraints",
                ]
            )
        elif category == "backend":
            policies.extend(
                [
                    "API design principles",
                    "Error handling patterns",
                    "Logging and monitoring",
                    "Security considerations",
                ]
            )
        elif category == "architecture":
            policies.extend(
                [
                    "Service boundaries",
                    "Communication patterns",
                    "Data consistency approach",
                    "Deployment strategy",
                ]
            )

        return policies

    def _generate_agent_guidance(
        self, decision: PreflightDecision, input_data: PreflightInput
    ) -> str:
        """Generate actionable guidance for the agent."""

        if decision.status == "ALLOWED":
            return (
                f"✅ You can proceed with '{input_data.choice}'. "
                f"{decision.reasoning}. {decision.next_steps}."
            )

        elif decision.status == "BLOCKED":
            conflicts_text = ""
            if decision.conflicting_adrs:
                conflicts_text = (
                    f" (conflicts with {', '.join(decision.conflicting_adrs)})"
                )

            return (
                f"🚫 Cannot use '{input_data.choice}'{conflicts_text}. "
                f"{decision.reasoning}. "
                f"Next step: {decision.next_steps}"
            )

        elif decision.status == "REQUIRES_ADR":
            related_text = ""
            if decision.related_adrs:
                related_text = f" (related: {', '.join(decision.related_adrs)})"

            return (
                f"📝 '{input_data.choice}' requires ADR{related_text}. "
                f"{decision.reasoning}. "
                f"Use adr_create() to document this decision before proceeding."
            )

        return f"Evaluation complete: {decision.reasoning}"
