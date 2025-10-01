"""Creation Workflow - Create new ADR proposals with conflict detection."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ..contract.builder import ConstraintsContractBuilder
from ..core.model import ADR, ADRFrontMatter, ADRStatus, PolicyModel
from ..core.parse import find_adr_files, parse_adr_file
from ..core.validate import validate_adr
from .base import BaseWorkflow, WorkflowError, WorkflowResult, WorkflowStatus


@dataclass
class CreationInput:
    """Input for ADR creation workflow."""

    title: str
    context: str  # The problem/situation that prompted this decision
    decision: str  # The architectural decision being made
    consequences: str  # Expected positive and negative consequences
    status: str = "proposed"  # Always start as proposed
    deciders: list[str] | None = None
    tags: list[str] | None = None
    policy: dict[str, Any] | None = None  # Structured policy block
    alternatives: str | None = None  # Alternative options considered


@dataclass
class CreationResult:
    """Result of ADR creation."""

    adr_id: str
    file_path: str
    conflicts_detected: list[str]  # ADR IDs that conflict with this proposal
    related_adrs: list[str]  # ADR IDs that are related but don't conflict
    validation_warnings: list[str]  # Non-blocking validation issues
    next_steps: str  # What agent should do next
    review_required: bool  # Whether human review is needed before approval


class CreationWorkflow(BaseWorkflow):
    """
    Creation Workflow creates new ADR proposals with comprehensive validation.

    This workflow ensures new ADRs are properly structured, don't conflict with
    existing decisions, and follow the project's ADR conventions.

    Workflow Steps:
    1. Generate next ADR ID and validate basic structure
    2. Query related ADRs using semantic search (if available)
    3. Detect conflicts with existing approved ADRs
    4. Validate ADR structure and policy format
    5. Generate ADR file in proposed status
    6. Return creation result with guidance for next steps
    """

    def execute(
        self, input_data: CreationInput | None = None, **kwargs: Any
    ) -> WorkflowResult:
        """Execute ADR creation workflow."""
        # Use positional input_data if provided, otherwise extract from kwargs
        if input_data is None:
            input_data = kwargs.get("input_data")
        if not input_data or not isinstance(input_data, CreationInput):
            raise ValueError("input_data must be provided as CreationInput instance")

        self._start_workflow("Create ADR")

        try:
            # Step 1: Generate ADR ID
            adr_id = self._execute_step("generate_adr_id", self._generate_adr_id)

            # Step 2: Validate input
            self._execute_step(
                "validate_input", self._validate_creation_input, input_data
            )

            # Step 3: Check conflicts
            related_adrs = self._execute_step(
                "find_related_adrs", self._find_related_adrs, input_data
            )
            conflicts = self._execute_step(
                "check_conflicts", self._detect_conflicts, input_data, related_adrs
            )

            # Step 4: Create ADR content
            adr = self._execute_step(
                "create_adr_content", self._build_adr_structure, adr_id, input_data
            )

            # Step 5: Write ADR file
            file_path = self._execute_step(
                "write_adr_file", self._generate_adr_file, adr
            )

            # Additional processing
            validation_result = self._validate_adr_structure(adr)
            review_required = self._determine_review_requirements(
                adr, conflicts, validation_result
            )
            next_steps = self._generate_next_steps_guidance(
                adr_id, conflicts, review_required
            )

            result = CreationResult(
                adr_id=adr_id,
                file_path=file_path,
                conflicts_detected=[c["adr_id"] for c in conflicts],
                related_adrs=[r["adr_id"] for r in related_adrs],
                validation_warnings=validation_result.get("warnings", []),
                next_steps=next_steps,
                review_required=review_required,
            )

            self._complete_workflow(
                success=True, message=f"ADR {adr_id} created successfully"
            )
            self.result.data = {"creation_result": result}
            self.result.guidance = next_steps
            self.result.next_steps = self._generate_next_steps_list(
                adr_id, conflicts, review_required
            )
            return self.result

        except WorkflowError as e:
            # Check if this was a validation error
            if "must be at least" in str(e) or "validation" in str(e).lower():
                self._complete_workflow(
                    success=False,
                    message=f"ADR creation failed: {str(e)}",
                    status=WorkflowStatus.VALIDATION_ERROR,
                )
            else:
                self._complete_workflow(
                    success=False, message=f"ADR creation failed: {str(e)}"
                )
            self.result.errors = [f"CreationError: {str(e)}"]
            return self.result
        except Exception as e:
            self._complete_workflow(
                success=False, message=f"ADR creation failed: {str(e)}"
            )
            self.result.errors = [f"CreationError: {str(e)}"]
            return self.result

    def _generate_adr_id(self) -> str:
        """Generate next available ADR ID."""
        # Scan directory for existing ADR files
        adr_files = find_adr_files(self.adr_dir)
        if not adr_files:
            return "ADR-0001"

        # Extract numbers from existing ADR files
        numbers = []
        for file_path in adr_files:
            filename = Path(file_path).stem
            match = re.search(r"ADR-(\d+)", filename)
            if match:
                numbers.append(int(match.group(1)))

        if not numbers:
            return "ADR-0001"

        next_num = max(numbers) + 1
        return f"ADR-{next_num:04d}"

    def _validate_creation_input(self, input_data: CreationInput) -> None:
        """Validate the input data for ADR creation."""
        if not input_data.title or len(input_data.title.strip()) < 3:
            raise ValueError("Title must be at least 3 characters")

        if not input_data.context or len(input_data.context.strip()) < 10:
            raise ValueError("Context must be at least 10 characters")

        if not input_data.decision or len(input_data.decision.strip()) < 5:
            raise ValueError("Decision must be at least 5 characters")

        if not input_data.consequences or len(input_data.consequences.strip()) < 5:
            raise ValueError("Consequences must be at least 5 characters")

        if input_data.status and input_data.status not in [
            "proposed",
            "accepted",
            "superseded",
        ]:
            raise ValueError("Status must be one of: proposed, accepted, superseded")

    def _find_related_adrs(self, input_data: CreationInput) -> list[dict[str, Any]]:
        """Find ADRs related to this proposal using various matching strategies."""
        related = []

        try:
            adr_files = find_adr_files(self.adr_dir)

            # Keywords from the proposal
            proposal_text = (
                f"{input_data.title} {input_data.context} {input_data.decision}"
            ).lower()

            # Extract key terms (simple approach - could be enhanced with NLP)
            key_terms = self._extract_key_terms(proposal_text)

            for file_path in adr_files:
                try:
                    existing_adr = parse_adr_file(file_path)
                    if existing_adr.status == "superseded":
                        continue  # Skip superseded ADRs

                    # Check for related content
                    existing_text = (
                        f"{existing_adr.title} {existing_adr.context} {existing_adr.decision}"
                    ).lower()

                    relevance_score = self._calculate_relevance(
                        key_terms, existing_text
                    )

                    if relevance_score > 0.3:  # Threshold for relevance
                        related.append(
                            {
                                "adr_id": existing_adr.id,
                                "title": existing_adr.title,
                                "relevance_score": relevance_score,
                                "matching_terms": [
                                    term for term in key_terms if term in existing_text
                                ],
                                "tags_overlap": bool(
                                    set(input_data.tags or [])
                                    & set(existing_adr.front_matter.tags or [])
                                ),
                            }
                        )

                except Exception:
                    continue  # Skip problematic files

            # Sort by relevance
            related.sort(
                key=lambda x: (
                    float(x["relevance_score"])
                    if isinstance(x["relevance_score"], int | float | str)
                    else 0.0
                ),
                reverse=True,
            )
            return related[:10]  # Return top 10 most relevant

        except Exception:
            return []  # Return empty if search fails

    def _extract_key_terms(self, text: str) -> list[str]:
        """Extract key technical terms from text."""
        # Common technology and architecture terms
        tech_patterns = [
            r"\b\w*sql\w*\b",
            r"\bmongo\w*\b",
            r"\bredis\b",  # Databases
            r"\breact\b",
            r"\bvue\b",
            r"\bangular\b",
            r"\bsvelte\b",  # Frontend
            r"\bexpress\b",
            r"\bdjango\b",
            r"\bflask\b",
            r"\bspring\b",  # Backend
            r"\bmicroservice\w*\b",
            r"\bmonolith\w*\b",
            r"\bserverless\b",  # Architecture
            r"\bapi\b",
            r"\brest\b",
            r"\bgraphql\b",
            r"\bgrpc\b",  # APIs
            r"\bdocker\b",
            r"\bkubernetes\b",
            r"\baws\b",
            r"\bazure\b",  # Infrastructure
            r"\btypescript\b",
            r"\bjavascript\b",
            r"\bpython\b",
            r"\bjava\b",  # Languages
        ]

        terms = []
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.extend([match.lower() for match in matches])

        # Add important words (length > 5)
        words = re.findall(r"\b\w{5,}\b", text.lower())
        terms.extend(words)

        return list(set(terms))  # Remove duplicates

    def _calculate_relevance(self, key_terms: list[str], existing_text: str) -> float:
        """Calculate relevance score between proposal and existing ADR."""
        if not key_terms:
            return 0.0

        matching_terms = [term for term in key_terms if term in existing_text]
        return len(matching_terms) / len(key_terms)

    def _detect_conflicts(
        self, input_data: CreationInput, related_adrs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect conflicts between proposal and existing ADRs."""
        conflicts = []

        try:
            # Load constraints contract to check policy conflicts
            builder = ConstraintsContractBuilder(adr_dir=self.adr_dir)
            contract = builder.build()

            # Check policy conflicts
            if input_data.policy:
                policy_conflicts = self._detect_policy_conflicts(
                    input_data.policy, contract
                )
                conflicts.extend(policy_conflicts)

            # Check direct contradictions in highly related ADRs
            for related_adr in related_adrs:
                if related_adr["relevance_score"] > 0.7:  # High relevance threshold
                    contradiction = self._check_for_contradictions(
                        input_data, related_adr["adr_id"]
                    )
                    if contradiction:
                        conflicts.append(contradiction)

        except Exception:
            pass  # Conflict detection is best-effort

        return conflicts

    def _detect_policy_conflicts(
        self, proposed_policy: dict[str, Any], contract: Any
    ) -> list[dict[str, Any]]:
        """Detect conflicts between proposed policy and existing policies."""
        conflicts = []

        # Check if proposed policy contradicts existing constraints
        for constraint in contract.constraints:
            if self._policies_conflict(proposed_policy, constraint.policy):
                conflicts.append(
                    {
                        "adr_id": constraint.adr_id,
                        "conflict_type": "policy_contradiction",
                        "conflict_detail": f"Proposed policy conflicts with {constraint.adr_id} policy",
                    }
                )

        return conflicts

    def _policies_conflict(
        self, policy1: dict[str, Any], policy2: dict[str, Any]
    ) -> bool:
        """Check if two policies contradict each other."""
        # Simple conflict detection - can be enhanced

        # Check import conflicts
        if "imports" in policy1 and "imports" in policy2:
            p1_disallow = set(policy1["imports"].get("disallow", []))
            p2_prefer = set(policy2["imports"].get("prefer", []))

            if p1_disallow & p2_prefer:  # Intersection means conflict
                return True

        return False

    def _check_for_contradictions(
        self, input_data: CreationInput, related_adr_id: str
    ) -> dict[str, Any] | None:
        """Check if proposal contradicts a specific ADR."""
        # This is a simplified version - could be enhanced with NLP

        # Load the related ADR
        try:
            adr_files = find_adr_files(self.adr_dir)
            for file_path in adr_files:
                adr = parse_adr_file(file_path)
                if adr.id == related_adr_id:
                    # Simple keyword-based contradiction detection
                    proposal_decision = input_data.decision.lower()
                    existing_decision = adr.decision.lower()

                    # Look for opposing terms
                    opposing_pairs = [
                        ("use", "avoid"),
                        ("adopt", "reject"),
                        ("implement", "remove"),
                        ("enable", "disable"),
                        ("allow", "forbid"),
                    ]

                    for word1, word2 in opposing_pairs:
                        if word1 in proposal_decision and word2 in existing_decision:
                            return {
                                "adr_id": related_adr_id,
                                "conflict_type": "decision_contradiction",
                                "conflict_detail": f"Proposal uses '{word1}' while {related_adr_id} uses '{word2}'",
                            }
                    break
        except Exception:
            pass

        return None

    def _build_adr_structure(self, adr_id: str, input_data: CreationInput) -> ADR:
        """Build ADR data structure from input."""

        # Build front matter
        front_matter = ADRFrontMatter(
            id=adr_id,
            title=input_data.title.strip(),
            status=ADRStatus(input_data.status),
            date=date.today(),
            deciders=input_data.deciders or [],
            tags=input_data.tags or [],
            supersedes=[],
            superseded_by=[],
            policy=(
                PolicyModel.model_validate(input_data.policy)
                if input_data.policy
                else None
            ),
        )

        # Build content sections
        content_parts = [
            "## Context",
            "",
            input_data.context.strip(),
            "",
            "## Decision",
            "",
            input_data.decision.strip(),
            "",
            "## Consequences",
            "",
            input_data.consequences.strip(),
        ]

        if input_data.alternatives:
            content_parts.extend(
                [
                    "",
                    "## Alternatives",
                    "",
                    input_data.alternatives.strip(),
                ]
            )

        content = "\n".join(content_parts)

        return ADR(
            front_matter=front_matter,
            content=content,
            file_path=None,  # Not loaded from disk
        )

    def _validate_adr_structure(self, adr: ADR) -> dict[str, Any]:
        """Validate the ADR structure."""
        try:
            # Use existing validation
            validation_result = validate_adr(adr, self.adr_dir)
            return {
                "valid": validation_result.is_valid,
                "errors": [str(error) for error in validation_result.errors],
                "warnings": [str(warning) for warning in validation_result.warnings],
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
            }

    def _generate_adr_file(self, adr: ADR) -> str:
        """Generate the ADR file."""
        # Create filename with slugified title
        title_slug = re.sub(r"[^\w\s-]", "", adr.title.lower())
        title_slug = re.sub(r"[\s_-]+", "-", title_slug).strip("-")
        file_path = Path(self.adr_dir) / f"{adr.id}-{title_slug}.md"

        # Ensure directory exists
        Path(self.adr_dir).mkdir(parents=True, exist_ok=True)

        # Generate MADR format content
        content = self._generate_madr_content(adr)

        # Write file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(file_path)

    def _generate_madr_content(self, adr: ADR) -> str:
        """Generate MADR format content for the ADR."""
        lines = []

        # YAML front-matter
        lines.append("---")
        lines.append(f'id: "{adr.front_matter.id}"')
        lines.append(f'title: "{adr.front_matter.title}"')
        lines.append(f"status: {adr.front_matter.status}")
        lines.append(f"date: {adr.front_matter.date}")

        if adr.front_matter.deciders:
            lines.append(f"deciders: {adr.front_matter.deciders}")

        if adr.front_matter.tags:
            lines.append(f"tags: {adr.front_matter.tags}")

        if adr.front_matter.supersedes:
            lines.append(f"supersedes: {adr.front_matter.supersedes}")

        if adr.front_matter.superseded_by:
            lines.append(f"superseded_by: {adr.front_matter.superseded_by}")

        if adr.front_matter.policy:
            lines.append("policy:")
            policy_dict = adr.front_matter.policy.model_dump(exclude_none=True)
            for key, value in policy_dict.items():
                lines.append(f"  {key}: {value}")

        lines.append("---")
        lines.append("")

        # MADR content
        lines.append("## Context")
        lines.append("")
        lines.append(adr.context)
        lines.append("")

        lines.append("## Decision")
        lines.append("")
        lines.append(adr.decision)
        lines.append("")

        lines.append("## Consequences")
        lines.append("")
        lines.append(adr.consequences)
        lines.append("")

        if adr.alternatives:
            lines.append("## Alternatives")
            lines.append("")
            lines.append(adr.alternatives)
            lines.append("")

        return "\n".join(lines)

    def _determine_review_requirements(
        self,
        adr: ADR,
        conflicts: list[dict[str, Any]],
        validation_result: dict[str, Any],
    ) -> bool:
        """Determine if human review is required before approval."""

        # Always require review for conflicts
        if conflicts:
            return True

        # Require review for validation errors
        if not validation_result.get("valid", True):
            return True

        # Require review for significant architectural decisions
        significant_terms = [
            "database",
            "architecture",
            "framework",
            "security",
            "performance",
            "scalability",
            "microservice",
            "monolith",
        ]

        adr_text = f"{adr.title} {adr.decision}".lower()
        if any(term in adr_text for term in significant_terms):
            return True

        # Default: minor decisions can be auto-approved if no conflicts
        return False

    def _generate_next_steps_guidance(
        self, adr_id: str, conflicts: list[dict[str, Any]], review_required: bool
    ) -> str:
        """Generate guidance for what the agent should do next."""

        if conflicts:
            conflict_ids = [c["adr_id"] for c in conflicts]
            return (
                f"⚠️ {adr_id} has conflicts with {', '.join(conflict_ids)}. "
                f"Review conflicts and consider using adr_supersede() if this decision should replace existing ones. "
                f"Otherwise, revise the proposal to avoid conflicts."
            )

        if review_required:
            return (
                f"📋 {adr_id} requires human review due to architectural significance. "
                f"Have a human review the proposal, then use adr_approve() to activate it."
            )

        return (
            f"✅ {adr_id} is ready for approval. "
            f"Use adr_approve('{adr_id}') to activate this decision and trigger policy enforcement."
        )

    def _generate_next_steps_list(
        self, adr_id: str, conflicts: list[dict[str, Any]], review_required: bool
    ) -> list[str]:
        """Generate next steps as a list for the agent."""

        if conflicts:
            conflict_ids = [c["adr_id"] for c in conflicts]
            return [
                f"Review conflicts with {', '.join(conflict_ids)}",
                f"Consider using adr_supersede() if {adr_id} should replace existing decisions",
                "Revise the proposal to avoid conflicts if superseding is not appropriate",
            ]

        if review_required:
            return [
                f"Have a human review {adr_id} due to architectural significance",
                f"Use adr_approve('{adr_id}') after review to activate the decision",
            ]

        return [
            f"Review the created ADR {adr_id}",
            f"Use adr_approve('{adr_id}') to activate this decision",
            "Trigger policy enforcement for the decision",
        ]
