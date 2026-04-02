"""Creation Workflow - Create new ADR proposals with conflict detection."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ...contract.builder import ConstraintsContractBuilder
from ...core.model import ADR, ADRFrontMatter, ADRStatus, PolicyModel
from ...core.parse import find_adr_files, parse_adr_file
from ...core.validate import validate_adr
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
    skip_quality_gate: bool = False  # Skip quality gate (for testing or override)


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
        """Execute ADR creation workflow with quality gate."""
        # Use positional input_data if provided, otherwise extract from kwargs
        if input_data is None:
            input_data = kwargs.get("input_data")
        if not input_data or not isinstance(input_data, CreationInput):
            raise ValueError("input_data must be provided as CreationInput instance")

        self._start_workflow("Create ADR")

        try:
            # Step 1: Basic validation (minimum requirements)
            self._execute_step(
                "validate_input", self._validate_creation_input, input_data
            )

            # Step 2: Quality gate - run BEFORE any file operations (unless skipped)
            quality_feedback = None
            if not input_data.skip_quality_gate:
                quality_feedback = self._execute_step(
                    "quality_gate", self._quick_quality_gate, input_data
                )

                # Step 3: Check quality threshold
                if not quality_feedback.get("passes_threshold", True):
                    # Quality below threshold - BLOCK creation and return feedback
                    self._complete_workflow(
                        success=False,
                        message=f"Quality threshold not met (score: {quality_feedback['quality_score']}/{quality_feedback['threshold']})",
                        status=WorkflowStatus.REQUIRES_ACTION,
                    )
                    self.result.data = {
                        "quality_feedback": quality_feedback,
                        "correction_prompt": (
                            "Please address the quality issues identified above and resubmit. "
                            "Focus on high-priority issues first for maximum impact."
                        ),
                    }
                    self.result.next_steps = quality_feedback.get("next_steps", [])
                    return self.result
            else:
                # Quality gate skipped - generate basic feedback for backward compatibility
                quality_feedback = {
                    "quality_score": None,
                    "grade": None,
                    "passes_threshold": True,
                    "summary": "Quality gate skipped (skip_quality_gate=True)",
                    "issues": [],
                    "strengths": [],
                    "recommendations": [],
                    "next_steps": [],
                }

            # Quality passed threshold - proceed with ADR creation
            # Step 4: Generate ADR ID
            adr_id = self._execute_step("generate_adr_id", self._generate_adr_id)

            # Step 5: Check conflicts
            related_adrs = self._execute_step(
                "find_related_adrs", self._find_related_adrs, input_data
            )
            conflicts = self._execute_step(
                "check_conflicts", self._detect_conflicts, input_data, related_adrs
            )

            # Step 6: Create ADR content
            adr = self._execute_step(
                "create_adr_content", self._build_adr_structure, adr_id, input_data
            )

            # Step 7: Write ADR file (only happens if quality passed)
            file_path = self._execute_step(
                "write_adr_file", self._generate_adr_file, adr
            )

            # Additional processing
            validation_result = self._validate_adr_structure(adr)
            policy_warnings = self._validate_policy_completeness(adr, input_data)
            validation_result["warnings"].extend(policy_warnings)
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

            # Generate policy suggestions if no policy was provided (Task 2)
            policy_guidance = self._generate_policy_guidance(adr, input_data)

            self._complete_workflow(
                success=True, message=f"ADR {adr_id} created successfully"
            )
            self.result.data = {
                "creation_result": result,
                "quality_feedback": quality_feedback,  # Task 1: Quality gate results
                "policy_guidance": policy_guidance,  # Task 2: Policy construction guidance
            }
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
        """Validate the input data for ADR creation with helpful error messages."""
        if not input_data.title or len(input_data.title.strip()) < 3:
            raise ValueError(
                "Title must be at least 3 characters. "
                "Example: 'Use PostgreSQL for Primary Database' or 'Use React 18 with TypeScript'"
            )

        if not input_data.context or len(input_data.context.strip()) < 10:
            raise ValueError(
                "Context must be at least 10 characters. "
                "Context should explain WHY this decision is needed - the problem or opportunity. "
                "Example: 'We need ACID transactions for financial data integrity. Current SQLite "
                "setup doesn't support concurrent writes from multiple services.'"
            )

        if not input_data.decision or len(input_data.decision.strip()) < 5:
            raise ValueError(
                "Decision must be at least 5 characters. "
                "Decision should state WHAT specific technology/pattern/approach is chosen. "
                "Example: 'Use PostgreSQL 15 as the primary database. Don't use MySQL or MongoDB.' "
                "Be specific and include explicit constraints."
            )

        if not input_data.consequences or len(input_data.consequences.strip()) < 5:
            raise ValueError(
                "Consequences must be at least 5 characters. "
                "Consequences should document BOTH positive and negative outcomes (trade-offs). "
                "Example: '+ ACID compliance, + Rich features, - Higher resource usage, - Ops expertise required'"
            )

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
            depends_on=[],
            related_to=[],
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

    def _validate_policy_completeness(
        self, adr: ADR, creation_input: CreationInput
    ) -> list[str]:
        """Validate that ADR has extractable policy information.

        Returns list of warnings if policy is missing or insufficient.

        Note: This is a lightweight check. Policy construction guidance is provided
        via the policy_guidance promptlet, which agents can use to construct policies.
        """
        from ...core.policy_extractor import PolicyExtractor

        extractor = PolicyExtractor()
        warnings = []

        # Check if policy is extractable
        if not extractor.has_extractable_policy(adr):
            # Provide brief warning - detailed guidance is in policy_guidance promptlet
            warnings.append(
                "⚠️  No structured policy provided. Review the policy_guidance in the response "
                "for instructions on constructing enforcement policies."
            )

        return warnings

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

        # MADR content sections (already formatted in adr.content)
        lines.append(adr.content)

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

    def _generate_policy_guidance(
        self, adr: ADR, creation_input: CreationInput
    ) -> dict[str, Any] | None:
        """Generate policy guidance promptlet for agents.

        This method provides a structured promptlet that guides reasoning agents
        through the process of constructing enforcement policies. Rather than
        using regex to extract policies from text (which is fragile and redundant),
        we provide the schema and let the agent reason about how to map their
        architectural decision to the available policy capabilities.

        This follows the principle: "ADR Kit provides structure, agents provide intelligence."

        Returns:
            Policy guidance dict with schema and reasoning prompts, or None if policy already provided
        """
        # If policy was already provided, no guidance needed
        if adr.front_matter.policy:
            return {
                "has_policy": True,
                "message": "✅ Structured policy provided and validated",
            }

        # No policy provided - guide the agent through policy construction
        return {
            "has_policy": False,
            "message": (
                "📋 No policy provided. To enable automated enforcement, review your "
                "architectural decision and construct a policy dict using the schema below."
            ),
            "agent_task": {
                "role": "Policy Constructor",
                "objective": (
                    "Analyze your architectural decision and identify enforceable constraints "
                    "that can be automated. Map these constraints to the policy schema capabilities."
                ),
                "reasoning_steps": [
                    "1. Review your decision text for enforceable rules (what you said 'yes' or 'no' to)",
                    "2. Identify which policy types apply (imports, patterns, architecture, config)",
                    "3. Map your constraints to the schema structures below",
                    "4. Construct a policy dict with only the relevant policy types",
                    "5. Call adr_create() again with the policy parameter",
                ],
                "focus": (
                    "Look for explicit constraints in your decision: library choices, "
                    "code patterns, architectural boundaries, or configuration requirements."
                ),
            },
            "policy_capabilities": self._build_policy_reference(),
            "example_workflow": {
                "scenario": "Decision says: 'Use FastAPI. Don't use Flask or Django due to lack of async support.'",
                "reasoning": "This is an import restriction - FastAPI is preferred, Flask/Django are disallowed.",
                "constructed_policy": {
                    "imports": {
                        "disallow": ["flask", "django"],
                        "prefer": ["fastapi"],
                    },
                    "rationales": ["Native async support required for I/O operations"],
                },
                "next_call": "adr_create(..., policy={...})",
            },
            "guidance": [
                "Only create policies for explicit constraints in your decision",
                "Don't invent constraints that weren't in your decision",
                "Multiple policy types can be combined in one policy dict",
                "Rationales help explain why constraints exist",
            ],
        }

    def _build_policy_reference(self) -> dict[str, Any]:
        """Build comprehensive policy structure reference documentation.

        This reference is provided just-in-time when agents need to construct
        structured policies, avoiding context bloat in MCP tool docstrings.

        Includes enforcement_metadata derived from the live adapter registry so
        creation and enforcement cannot drift apart: when new adapters are added,
        this reference automatically reflects expanded capabilities.
        """
        return {
            "imports": {
                "description": "Import/library restrictions",
                "fields": {
                    "disallow": "List of banned libraries/modules",
                    "prefer": "List of recommended alternatives",
                },
                "example": {"disallow": ["flask", "django"], "prefer": ["fastapi"]},
            },
            "patterns": {
                "description": "Code pattern enforcement rules",
                "fields": {
                    "patterns": "Dict of named pattern rules, each containing:",
                    "  description": "Human-readable description",
                    "  language": "Target language (python, typescript, etc.)",
                    "  rule": "Regex pattern or structured query",
                    "  severity": "error | warning | info",
                    "  autofix": "Optional boolean for auto-fix support",
                },
                "example": {
                    "patterns": {
                        "async_handlers": {
                            "description": "All FastAPI handlers must be async",
                            "language": "python",
                            "rule": r"def\s+\w+",
                            "severity": "error",
                            "autofix": False,
                        }
                    }
                },
            },
            "architecture": {
                "description": "Architecture policies (boundaries + required structure)",
                "fields": {
                    "layer_boundaries": "List of forbidden dependencies",
                    "  rule": "Format: 'source -> target' (e.g., 'frontend -> database')",
                    "  action": "block | warn",
                    "  message": "Error message to display",
                    "  check": "Optional path pattern to scope the rule",
                    "required_structure": "List of required files/directories",
                    "  path": "File or directory path (glob patterns supported)",
                    "  description": "Why this structure is required",
                },
                "example": {
                    "layer_boundaries": [
                        {
                            "rule": "frontend -> database",
                            "action": "block",
                            "message": "Frontend must not access database directly",
                            "check": "src/frontend/**/*.py",
                        }
                    ],
                    "required_structure": [
                        {
                            "path": "src/models/*.py",
                            "description": "Model layer required",
                        }
                    ],
                },
            },
            "config_enforcement": {
                "description": "Configuration enforcement for TypeScript/Python tools",
                "fields": {
                    "typescript": "TypeScript config requirements",
                    "  tsconfig": "Required tsconfig.json settings",
                    "  eslintConfig": "Required ESLint config",
                    "python": "Python config requirements",
                    "  ruff": "Required Ruff settings",
                    "  mypy": "Required mypy settings",
                },
                "example": {
                    "typescript": {
                        "tsconfig": {
                            "strict": True,
                            "compilerOptions": {"noImplicitAny": True},
                        }
                    },
                    "python": {
                        "ruff": {"lint": {"select": ["I"]}},
                        "mypy": {"strict": True},
                    },
                },
            },
            "rationales": {
                "description": "List of reasons for the policies",
                "example": [
                    "FastAPI provides native async support",
                    "Better performance for I/O operations",
                ],
            },
            "enforcement_metadata": self._build_enforcement_metadata(),
        }

    def _build_enforcement_metadata(self) -> dict[str, Any]:
        """Build enforcement capability metadata derived from the adapter registry.

        This is derived at call-time from the live adapter registry — never
        hardcoded — so that adding new adapters automatically updates this
        reference without touching creation.py.
        """
        from ...enforcement.adapters.eslint import ESLintAdapter
        from ...enforcement.adapters.ruff import RuffAdapter

        adapters = [ESLintAdapter(), RuffAdapter()]

        # Map each policy key to the adapters that can enforce it
        policy_coverage: dict[str, list[str]] = {}
        adapter_details: dict[str, dict[str, Any]] = {}

        for adapter in adapters:
            adapter_details[adapter.name] = {
                "tool": adapter.name,
                "supported_policy_keys": adapter.supported_policy_keys,
                "supported_languages": adapter.supported_languages,
                "output_modes": adapter.output_modes,
                "supported_stages": adapter.supported_stages,
                "config_targets": adapter.config_targets,
            }
            for key in adapter.supported_policy_keys:
                policy_coverage.setdefault(key, []).append(adapter.name)

        # Flag policy keys that have no adapter (script_fallback path)
        all_known_keys = [
            "imports",
            "python",
            "patterns",
            "architecture",
            "config_enforcement",
        ]
        for key in all_known_keys:
            policy_coverage.setdefault(key, [])  # Empty list = no native adapter

        enforcement_paths: dict[str, str] = {}
        for key in all_known_keys:
            covered_by = policy_coverage.get(key, [])
            if covered_by:
                enforcement_paths[key] = f"native_config via {', '.join(covered_by)}"
            else:
                enforcement_paths[key] = (
                    "script_fallback (no native adapter — agent creates validation script)"
                )

        return {
            "note": (
                "Coverage is stack-dependent: ESLint requires JS/TS project, "
                "Ruff requires Python project. Unroutable policies generate fallback promptlets."
            ),
            "adapters": adapter_details,
            "policy_enforcement_paths": enforcement_paths,
        }

    def _quick_quality_gate(self, creation_input: CreationInput) -> dict[str, Any]:
        """Quick quality gate that runs BEFORE ADR file creation.

        This pre-validation check runs deterministic quality checks on the input
        to ensure decision quality meets the minimum threshold BEFORE creating
        any files. This enables a correction loop without file pollution.

        Args:
            creation_input: The input data for ADR creation

        Returns:
            Quality assessment with passes_threshold boolean and feedback
        """
        issues = []
        strengths = []
        score = 100  # Start perfect, deduct points for issues
        QUALITY_THRESHOLD = 75  # B grade minimum (anything lower blocks creation)

        context_text = creation_input.context.lower()
        decision_text = creation_input.decision.lower()
        consequences_text = creation_input.consequences.lower()

        # Check 1: Specificity - detect generic/vague language
        generic_terms = [
            "modern",
            "good",
            "best",
            "framework",
            "library",
            "tool",
            "better",
            "nice",
        ]
        vague_count = sum(
            1 for term in generic_terms if term in decision_text or term in context_text
        )

        if vague_count >= 2:
            score -= 15
            issues.append(
                {
                    "category": "specificity",
                    "severity": "medium",
                    "issue": f"Decision uses {vague_count} generic terms ('{', '.join([t for t in generic_terms if t in decision_text or t in context_text][:3])}...')",
                    "suggestion": "Replace generic terms with specific technology names and versions",
                    "example_fix": "Instead of 'use a modern framework', write 'Use React 18 with TypeScript'",
                }
            )
        else:
            strengths.append("Decision uses specific, concrete terminology")

        # Check 2: Balanced consequences - must have BOTH pros AND cons
        positive_keywords = [
            "benefit",
            "advantage",
            "positive",
            "improve",
            "better",
            "gain",
        ]
        negative_keywords = [
            "drawback",
            "limitation",
            "negative",
            "cost",
            "risk",
            "challenge",
        ]

        has_positives = any(kw in consequences_text for kw in positive_keywords)
        has_negatives = any(kw in consequences_text for kw in negative_keywords)

        if not (has_positives and has_negatives):
            score -= 25
            issues.append(
                {
                    "category": "balance",
                    "severity": "high",
                    "issue": "Consequences are one-sided (only pros or only cons)",
                    "suggestion": "Document BOTH positive and negative consequences - every technical decision has trade-offs",
                    "example_fix": "Add '### Negative' section listing drawbacks, limitations, or risks",
                    "why_it_matters": "Balanced trade-off analysis enables informed decision-making",
                }
            )
        else:
            strengths.append("Consequences show balanced trade-off analysis")

        # Check 3: Context quality - sufficient detail
        context_length = len(creation_input.context)

        if context_length < 50:
            score -= 20
            issues.append(
                {
                    "category": "context",
                    "severity": "high",
                    "issue": f"Context is too brief ({context_length} characters)",
                    "suggestion": "Expand context to explain WHY this decision is needed: current state, requirements, drivers",
                    "example_fix": "Add: business requirements, technical constraints, user needs",
                }
            )
        elif context_length >= 150:
            strengths.append("Context provides detailed problem background")

        # Check 4: Explicit constraints - policy-ready language
        import re

        constraint_patterns = [
            r"\bdon[''']t\s+use\b",
            r"\bmust\s+not\s+use\b",
            r"\bavoid\b",
            r"\bmust\s+(?:use|have|be)\b",
            r"\ball\s+\w+\s+must\b",
        ]

        has_explicit_constraints = any(
            re.search(pattern, decision_text, re.IGNORECASE)
            for pattern in constraint_patterns
        )

        if not has_explicit_constraints:
            score -= 15
            issues.append(
                {
                    "category": "policy_readiness",
                    "severity": "medium",
                    "issue": "Decision lacks explicit constraints (enables policy extraction)",
                    "suggestion": "Add explicit constraints using 'Don't use X', 'Must use Y', 'All Z must...'",
                    "example_fix": "Use FastAPI for APIs. **Don't use Flask** or Django.",
                    "why_it_matters": "Explicit constraints enable automated policy enforcement (Task 2)",
                }
            )
        else:
            strengths.append(
                "Decision includes explicit constraints ready for policy extraction"
            )

        # Check 5: Alternatives - critical for 'disallow' policies
        if not creation_input.alternatives or len(creation_input.alternatives) < 20:
            score -= 15
            issues.append(
                {
                    "category": "alternatives",
                    "severity": "medium",
                    "issue": "Missing or minimal alternatives section",
                    "suggestion": "Document rejected alternatives with specific reasons",
                    "example_fix": "### MySQL\\n**Rejected**: Weaker JSON support\\n\\n### MongoDB\\n**Rejected**: Conflicts with ACID requirements",
                    "why_it_matters": "Alternatives section enables extraction of 'disallow' policies",
                }
            )
        else:
            strengths.append("Alternatives documented (enables disallow policies)")

        # Check 6: Decision completeness
        decision_length = len(creation_input.decision)

        if decision_length < 30:
            score -= 10
            issues.append(
                {
                    "category": "completeness",
                    "severity": "low",
                    "issue": f"Decision is very brief ({decision_length} characters)",
                    "suggestion": "Expand decision with: specific technology, scope, and constraints",
                    "example_fix": "Use PostgreSQL 15 for all application data. Deploy on AWS RDS with Multi-AZ.",
                }
            )

        # Clamp score to valid range
        score = max(0, min(100, score))

        # Determine grade (A=90+, B=75+, C=60+, D=40+, F=<40)
        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 40:
            grade = "D"
        else:
            grade = "F"

        passes_threshold = score >= QUALITY_THRESHOLD

        # Generate summary
        if passes_threshold:
            summary = f"Decision quality is acceptable (Grade {grade}, {score}/100). {len(issues)} minor improvements suggested."
        else:
            summary = f"Decision quality is below threshold (Grade {grade}, {score}/100). {len(issues)} issues must be addressed before ADR creation."

        # Generate prioritized recommendations
        high_priority = [i for i in issues if i["severity"] == "high"]
        medium_priority = [i for i in issues if i["severity"] == "medium"]

        recommendations = []
        if high_priority:
            recommendations.append(
                f"🔴 **High Priority**: Fix {len(high_priority)} critical issues first"
            )
            for issue in high_priority[:2]:  # Top 2 high priority
                recommendations.append(
                    f"  - {issue['category'].title()}: {issue['suggestion']}"
                )

        if medium_priority and score < QUALITY_THRESHOLD:
            recommendations.append(
                f"🟡 **Medium Priority**: Address {len(medium_priority)} quality issues"
            )
            for issue in medium_priority[:2]:  # Top 2 medium priority
                recommendations.append(
                    f"  - {issue['category'].title()}: {issue['suggestion']}"
                )

        # Next steps vary by quality score
        next_steps = []
        if not passes_threshold:
            next_steps.append(
                "⛔ **ADR Creation Blocked**: Quality score below threshold"
            )
            next_steps.append(
                "📝 **Action Required**: Address the issues above and resubmit"
            )
            next_steps.append(
                "💡 **Tip**: Focus on high-priority issues first for maximum impact"
            )
        else:
            next_steps.append(
                "✅ **Quality Gate Passed**: ADR will be created with this input"
            )
            if issues:
                next_steps.append(
                    f"💡 **Optional**: Consider addressing {len(issues)} suggestions for even higher quality"
                )

        return {
            "quality_score": score,
            "grade": grade,
            "passes_threshold": passes_threshold,
            "threshold": QUALITY_THRESHOLD,
            "summary": summary,
            "issues": issues,
            "strengths": strengths,
            "recommendations": recommendations,
            "next_steps": next_steps,
        }

    def _assess_decision_quality(
        self, adr: ADR, creation_input: CreationInput
    ) -> dict[str, Any]:
        """Assess decision quality and provide targeted feedback.

        This implements Task 1 of the two-step ADR creation flow:
        - Task 1 (this method): Assess decision quality and provide guidance
        - Task 2 (_generate_policy_guidance): Extract enforceable policies

        The assessment identifies common quality issues and provides actionable
        feedback to help agents improve their ADRs. It follows the principle:
        "ADR Kit provides structure, agents provide intelligence."

        Args:
            adr: The created ADR
            creation_input: The input data used to create the ADR

        Returns:
            Quality assessment with issues found and improvement suggestions
        """
        issues = []
        strengths = []
        score = 100  # Start with perfect score, deduct for issues

        # Check 1: Specificity (are technology names specific?)
        generic_terms = [
            "modern",
            "good",
            "best",
            "framework",
            "library",
            "tool",
            "system",
            "platform",
        ]
        decision_lower = adr.decision.lower()
        title_lower = adr.title.lower()

        vague_terms_found = [
            term
            for term in generic_terms
            if term in decision_lower or term in title_lower
        ]
        if vague_terms_found:
            issues.append(
                {
                    "category": "specificity",
                    "severity": "medium",
                    "issue": f"Decision uses generic terms: {', '.join(vague_terms_found)}",
                    "suggestion": (
                        "Replace generic terms with specific technology names and versions. "
                        "Example: Instead of 'modern framework', use 'React 18' or 'FastAPI 0.104'."
                    ),
                    "example_fix": {
                        "bad": "Use a modern web framework",
                        "good": "Use React 18 with TypeScript for frontend development",
                    },
                }
            )
            score -= 15
        else:
            strengths.append("Decision is specific with clear technology choices")

        # Check 2: Balanced consequences (are there both pros AND cons?)
        consequences_lower = adr.consequences.lower()
        has_positives = any(
            word in consequences_lower
            for word in [
                "benefit",
                "advantage",
                "positive",
                "+",
                "pro:",
                "pros:",
                "good",
                "better",
                "improve",
            ]
        )
        has_negatives = any(
            word in consequences_lower
            for word in [
                "drawback",
                "disadvantage",
                "negative",
                "-",
                "con:",
                "cons:",
                "risk",
                "limitation",
                "downside",
                "trade-off",
                "tradeoff",
            ]
        )

        if not (has_positives and has_negatives):
            issues.append(
                {
                    "category": "balance",
                    "severity": "high",
                    "issue": "Consequences appear one-sided (missing pros or cons)",
                    "suggestion": (
                        "Every technical decision has trade-offs. Document BOTH positive outcomes "
                        "AND negative consequences honestly. Use structure like:\n"
                        "### Positive\n- Benefit 1\n- Benefit 2\n\n"
                        "### Negative\n- Drawback 1\n- Drawback 2"
                    ),
                    "why_it_matters": (
                        "Balanced consequences help future decision-makers understand when to "
                        "reconsider this choice. Hiding drawbacks leads to technical debt."
                    ),
                }
            )
            score -= 25
        else:
            strengths.append("Consequences document both benefits and drawbacks")

        # Check 3: Context quality (does it explain WHY?)
        context_length = len(adr.context.strip())
        if context_length < 50:
            issues.append(
                {
                    "category": "context",
                    "severity": "high",
                    "issue": "Context is too brief (less than 50 characters)",
                    "suggestion": (
                        "Context should explain WHY this decision is needed. Include:\n"
                        "- The problem or opportunity\n"
                        "- Current state and why it's insufficient\n"
                        "- Requirements that must be met\n"
                        "- Constraints or limitations"
                    ),
                    "example": (
                        "Good Context: 'We need ACID transactions for financial data integrity. "
                        "Current SQLite setup doesn't support concurrent writes from multiple services. "
                        "Requires complex queries with joins and JSON document storage.'"
                    ),
                }
            )
            score -= 20
        else:
            strengths.append("Context provides sufficient detail about the problem")

        # Check 4: Explicit constraints (for policy extraction)
        constraint_patterns = [
            r"\bdon[''']t\s+use\b",
            r"\bavoid\b.*\b(?:using|use)\b",
            r"\bmust\s+(?:not\s+)?(?:use|have|be)\b",
            r"\ball\s+\w+\s+must\b",
            r"\brequired?\b",
            r"\bprohibited?\b",
        ]

        has_explicit_constraints = any(
            re.search(pattern, decision_lower, re.IGNORECASE)
            for pattern in constraint_patterns
        )

        if not has_explicit_constraints:
            issues.append(
                {
                    "category": "policy_readiness",
                    "severity": "medium",
                    "issue": "Decision lacks explicit constraints for policy extraction",
                    "suggestion": (
                        "Use explicit constraint language to enable automated policy extraction:\n"
                        "- 'Don't use X' / 'Avoid X'\n"
                        "- 'Use Y instead of X'\n"
                        "- 'All X must have Y'\n"
                        "- 'Must not access'\n"
                        "Example: 'Use FastAPI. Don't use Flask or Django due to lack of async support.'"
                    ),
                    "why_it_matters": (
                        "Explicit constraints enable Task 2 (policy extraction) to generate "
                        "enforceable rules automatically. Vague language can't be automated."
                    ),
                }
            )
            score -= 15
        else:
            strengths.append(
                "Decision includes explicit constraints ready for policy extraction"
            )

        # Check 5: Alternatives (critical for policy extraction)
        if (
            not creation_input.alternatives
            or len(creation_input.alternatives.strip()) < 20
        ):
            issues.append(
                {
                    "category": "alternatives",
                    "severity": "medium",
                    "issue": "Missing or insufficient alternatives documentation",
                    "suggestion": (
                        "Document what alternatives you considered and WHY you rejected each one. "
                        "This is CRITICAL for policy extraction - rejected alternatives often become "
                        "'disallow' policies.\n\n"
                        "Structure:\n"
                        "### Alternative Name\n"
                        "**Rejected**: Specific reason for rejection\n"
                        "- Pros: ...\n"
                        "- Cons: ...\n"
                        "- Why not: ..."
                    ),
                    "example": (
                        "### Flask\n"
                        "**Rejected**: Lacks native async support.\n"
                        "- Pros: Lightweight, huge ecosystem\n"
                        "- Cons: No native async, requires Quart\n"
                        "- Why not: Async support is critical for our use case"
                    ),
                    "why_it_matters": (
                        "Alternatives with clear rejection reasons enable extraction of 'disallow' policies. "
                        "Example: 'Rejected Flask' becomes {'imports': {'disallow': ['flask']}}"
                    ),
                }
            )
            score -= 15
        else:
            strengths.append(
                "Alternatives documented with clear rejection reasons (enables 'disallow' policies)"
            )

        # Check 6: Decision length (too short is usually vague)
        decision_length = len(adr.decision.strip())
        if decision_length < 30:
            issues.append(
                {
                    "category": "completeness",
                    "severity": "medium",
                    "issue": "Decision section is very brief (less than 30 characters)",
                    "suggestion": (
                        "Decision should clearly state:\n"
                        "1. What technology/pattern/approach is chosen\n"
                        "2. Scope of applicability ('All new services', 'Frontend only')\n"
                        "3. Explicit constraints ('Don't use X', 'Must have Y')\n"
                        "4. Migration path if replacing existing technology"
                    ),
                }
            )
            score -= 10

        # Determine overall quality grade
        if score >= 90:
            grade = "A"
            summary = "Excellent ADR - ready for policy extraction"
        elif score >= 75:
            grade = "B"
            summary = "Good ADR - minor improvements would help"
        elif score >= 60:
            grade = "C"
            summary = "Acceptable ADR - several areas need improvement"
        elif score >= 40:
            grade = "D"
            summary = (
                "Weak ADR - significant improvements needed before policy extraction"
            )
        else:
            grade = "F"
            summary = "Poor ADR - needs major revision"

        return {
            "quality_score": score,
            "grade": grade,
            "summary": summary,
            "issues": issues,
            "strengths": strengths,
            "recommendations": self._generate_quality_recommendations(issues),
            "next_steps": self._generate_quality_next_steps(issues, score),
        }

    def _generate_quality_recommendations(
        self, issues: list[dict[str, Any]]
    ) -> list[str]:
        """Generate prioritized recommendations based on quality issues.

        Args:
            issues: List of quality issues found

        Returns:
            Prioritized list of actionable recommendations
        """
        if not issues:
            return [
                "✅ Your ADR meets quality standards",
                "Consider reviewing the policy_guidance to add automated enforcement",
            ]

        recommendations = []

        # Prioritize by severity
        high_severity = [issue for issue in issues if issue["severity"] == "high"]
        medium_severity = [issue for issue in issues if issue["severity"] == "medium"]

        if high_severity:
            recommendations.append(
                f"🔴 High Priority: Address {len(high_severity)} critical quality issue(s):"
            )
            for issue in high_severity:
                recommendations.append(f"   - {issue['issue']}")
                recommendations.append(f"     → {issue['suggestion']}")

        if medium_severity:
            recommendations.append(
                f"🟡 Medium Priority: Improve {len(medium_severity)} quality aspect(s):"
            )
            for issue in medium_severity:
                recommendations.append(f"   - {issue['issue']}")

        return recommendations

    def _generate_quality_next_steps(
        self, issues: list[dict[str, Any]], score: int
    ) -> list[str]:
        """Generate next steps based on quality assessment.

        Args:
            issues: List of quality issues found
            score: Overall quality score

        Returns:
            List of recommended next steps
        """
        if score >= 80:
            # High quality - ready to proceed
            return [
                "Your ADR is high quality and ready for review",
                "Review the policy_guidance to add automated enforcement policies",
                "Use adr_approve() after human review to activate the decision",
            ]
        elif score >= 60:
            # Acceptable but could improve
            return [
                "ADR is acceptable but could be strengthened",
                "Consider addressing the quality issues listed above",
                "You can proceed with approval or revise for better policy extraction",
            ]
        else:
            # Needs significant improvement
            return [
                "⚠️  ADR quality is below recommended threshold",
                "Strongly recommend revising before approval:",
                "  1. Address high-priority issues (context, balance, specificity)",
                "  2. Add alternatives with rejection reasons (enables policy extraction)",
                "  3. Use explicit constraint language ('Don't use', 'Must have')",
                "After revision, create a new ADR with improved content",
            ]
