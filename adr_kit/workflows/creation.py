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

            # Generate policy suggestions if no policy was provided
            policy_guidance = self._generate_policy_guidance(adr, input_data)

            self._complete_workflow(
                success=True, message=f"ADR {adr_id} created successfully"
            )
            self.result.data = {
                "creation_result": result,
                "policy_guidance": policy_guidance,  # New: return policy guidance to agent
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

    def _validate_policy_completeness(
        self, adr: ADR, creation_input: CreationInput
    ) -> list[str]:
        """Validate that ADR has extractable policy information.

        Returns list of warnings if policy is missing or insufficient.
        """
        from ..core.policy_extractor import PolicyExtractor

        extractor = PolicyExtractor()
        warnings = []

        # Check if policy is extractable
        if not extractor.has_extractable_policy(adr):
            # Analyze decision and alternatives to suggest policy
            alternatives_text = creation_input.alternatives or ""
            suggested = self._suggest_policy_from_alternatives(
                creation_input.decision, alternatives_text
            )

            if suggested:
                # Policy could be auto-generated from content
                import json

                warnings.append(
                    "⚠️  No structured policy provided, but enforceable policies detected in content."
                )
                warnings.append(
                    f"📋 Suggested policy structure:\n{json.dumps(suggested, indent=2)}"
                )
                warnings.append(
                    "💡 To enable automatic enforcement, include a 'policy' block with this structure when creating the ADR."
                )
            else:
                # No detectable policy at all
                warnings.append(
                    "⚠️  No structured policy provided and no enforceable policies detected in content."
                )
                warnings.append(
                    "📖 Use pattern-friendly language to enable constraint extraction:\n"
                    "   • Import restrictions: 'Don't use X', 'Prefer Y over X'\n"
                    "   • Code patterns: 'All X must be Y', 'X must have Y'\n"
                    "   • Architecture: 'X must not access Y', 'Required: path/to/file'\n"
                    "   • Config: 'TypeScript strict mode required', 'Ruff must check imports'"
                )
                warnings.append(
                    "💡 Or include a structured 'policy' block for guaranteed enforcement."
                )

        return warnings

    def _suggest_policy_from_alternatives(
        self, decision: str, alternatives: str
    ) -> dict[str, Any] | None:
        """Suggest policy structure based on decision and alternatives text.

        This is a comprehensive policy suggestion engine that analyzes the
        decision and alternatives to detect enforceable policies across all
        policy types: imports, patterns, architecture, and config enforcement.
        """
        # Combine decision and alternatives for comprehensive analysis
        full_text = f"{decision}\n\n{alternatives}"

        suggested_policy: dict[str, Any] = {}

        # 1. Extract Import Policies
        import_policy = self._suggest_import_policies(full_text, decision)
        if import_policy:
            suggested_policy["imports"] = import_policy

        # 2. Extract Pattern Policies
        pattern_policy = self._suggest_pattern_policies(full_text)
        if pattern_policy:
            suggested_policy["patterns"] = pattern_policy

        # 3. Extract Architecture Policies
        architecture_policy = self._suggest_architecture_policies(full_text)
        if architecture_policy:
            suggested_policy["architecture"] = architecture_policy

        # 4. Extract Config Enforcement Policies
        config_policy = self._suggest_config_policies(full_text)
        if config_policy:
            suggested_policy["config_enforcement"] = config_policy

        # 5. Extract Rationales
        rationales = self._suggest_rationales(full_text)
        if rationales:
            suggested_policy["rationales"] = rationales

        return suggested_policy if suggested_policy else None

    def _suggest_import_policies(
        self, full_text: str, decision: str
    ) -> dict[str, Any] | None:
        """Suggest import/library policies from text."""
        disallow = set()
        prefer = set()

        # Pattern 1: "Don't use X", "Avoid X", "Ban X", "X is deprecated"
        ban_patterns = [
            r"(?i)(?:don't\s+use|avoid|ban|deprecated?)\s+([a-zA-Z0-9\-_@/.]+)",
            r"(?i)no\s+longer\s+use\s+([a-zA-Z0-9\-_@/.]+)",
            r"(?i)([a-zA-Z0-9\-_@/.]+)\s+is\s+deprecated",
        ]

        for pattern in ban_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                normalized = self._normalize_library_name(match)
                if normalized:
                    disallow.add(normalized)

        # Pattern 2: "Use Y instead of X", "Prefer Y over X", "Replace X with Y"
        preference_patterns = [
            r"(?i)use\s+([a-zA-Z0-9\-_@/.]+)\s+instead\s+of\s+([a-zA-Z0-9\-_@/.]+)",
            r"(?i)prefer\s+([a-zA-Z0-9\-_@/.]+)\s+over\s+([a-zA-Z0-9\-_@/.]+)",
            r"(?i)replace\s+([a-zA-Z0-9\-_@/.]+)\s+with\s+([a-zA-Z0-9\-_@/.]+)",
        ]

        for pattern in preference_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                if len(match) == 2:  # (preferred, deprecated)
                    preferred, deprecated = match
                    preferred_norm = self._normalize_library_name(preferred)
                    deprecated_norm = self._normalize_library_name(deprecated)
                    if preferred_norm:
                        prefer.add(preferred_norm)
                    if deprecated_norm:
                        disallow.add(deprecated_norm)

        # Pattern 3: Extract from alternatives section
        # "### Technology Name\n- Rejected"
        heading_matches = re.findall(
            r"(?i)###\s+([a-zA-Z0-9\-_@/. ]+?)\n\s*-\s*Reject(?:ed)?", full_text
        )
        for match in heading_matches:
            first_word = match.strip().split()[0] if match.strip().split() else ""
            if first_word and len(first_word) > 2:
                if re.match(r"^[A-Za-z][A-Za-z0-9\-_.]*$", first_word):
                    normalized = self._normalize_library_name(first_word)
                    if normalized:
                        disallow.add(normalized)

        # Pattern 3b: "Rejected X and Y" format
        rejected_and_pattern = r"(?i)Rejected?\s+([A-Za-z][A-Za-z0-9\-_.@/]*)"
        rejected_and_matches = re.findall(rejected_and_pattern, full_text)
        for match in rejected_and_matches:
            normalized = self._normalize_library_name(match)
            if normalized:
                disallow.add(normalized)

        # Pattern 4: Extract chosen technology from decision
        use_matches = re.findall(r"(?i)Use\s+([a-zA-Z0-9\-_@/.]+)", decision)
        for match in use_matches:
            normalized = self._normalize_library_name(match)
            if normalized:
                prefer.add(normalized)

        if disallow or prefer:
            return {
                "disallow": sorted(disallow) if disallow else None,
                "prefer": sorted(prefer) if prefer else None,
            }

        return None

    def _suggest_pattern_policies(self, full_text: str) -> dict[str, Any] | None:
        """Suggest code pattern policies from text."""
        patterns_dict = {}

        # Pattern 1: "All X must be Y"
        all_must_patterns = re.findall(
            r"(?i)all\s+([a-zA-Z0-9\-_\s]+?)\s+must\s+be\s+([a-zA-Z0-9\-_\s]+)",
            full_text,
        )
        for _idx, (subject, requirement) in enumerate(all_must_patterns, start=1):
            rule_name = f"all_{subject.strip().lower().replace(' ', '_')}_must_be_{requirement.strip().lower().replace(' ', '_')}"
            patterns_dict[rule_name] = {
                "description": f"All {subject.strip()} must be {requirement.strip()}",
                "severity": "error",
                "rule": f"{subject.strip()}.*{requirement.strip()}",  # Simple regex placeholder
            }

        # Pattern 2: "X must have Y" or "X must include Y"
        must_have_patterns = re.findall(
            r"(?i)([a-zA-Z0-9\-_\s]+?)\s+must\s+(?:have|include)\s+([a-zA-Z0-9\-_\s]+)",
            full_text,
        )
        for _idx, (subject, requirement) in enumerate(must_have_patterns, start=1):
            rule_name = f"{subject.strip().lower().replace(' ', '_')}_must_have_{requirement.strip().lower().replace(' ', '_')}"
            patterns_dict[rule_name] = {
                "description": f"{subject.strip()} must have {requirement.strip()}",
                "severity": "error",
                "rule": f"{subject.strip()}.*{requirement.strip()}",
            }

        # Pattern 3: "No X allowed" or "X is forbidden"
        no_allowed_patterns = re.findall(
            r"(?i)no\s+([a-zA-Z0-9\-_\s]+?)\s+(?:allowed|permitted)", full_text
        )
        for match in no_allowed_patterns:
            rule_name = f"no_{match.strip().lower().replace(' ', '_')}_allowed"
            patterns_dict[rule_name] = {
                "description": f"No {match.strip()} allowed",
                "severity": "error",
                "rule": f"(?!.*{match.strip()})",  # Negative lookahead
            }

        return {"patterns": patterns_dict} if patterns_dict else None

    def _suggest_architecture_policies(self, full_text: str) -> dict[str, Any] | None:
        """Suggest architecture policies (boundaries + structure) from text."""
        layer_boundaries = []
        required_structure = []

        # Pattern 1: "X must not access/call/use Y"
        boundary_patterns = [
            r"(?i)([a-zA-Z0-9\-_]+)\s+must\s+not\s+(?:access|call|use|import)\s+([a-zA-Z0-9\-_]+)",
            r"(?i)no\s+direct\s+access\s+from\s+([a-zA-Z0-9\-_]+)\s+to\s+([a-zA-Z0-9\-_]+)",
            r"(?i)([a-zA-Z0-9\-_]+)\s+(?:cannot|should\s+not)\s+(?:access|import)\s+([a-zA-Z0-9\-_]+)",
        ]

        for pattern in boundary_patterns:
            matches = re.findall(pattern, full_text)
            for source, target in matches:
                layer_boundaries.append(
                    {
                        "rule": f"{source.strip()} -> {target.strip()}",
                        "action": "block",
                        "message": f"{source.strip()} must not access {target.strip()}",
                    }
                )

        # Pattern 2: "Required: path/to/file"
        required_patterns = re.findall(
            r"(?i)required:\s+([a-zA-Z0-9\-_/.]+)", full_text
        )
        for path in required_patterns:
            required_structure.append(
                {"path": path.strip(), "description": f"Required: {path.strip()}"}
            )

        # Pattern 3: "Must have X directory/file"
        must_have_structure = re.findall(
            r"(?i)must\s+have\s+([a-zA-Z0-9\-_/.]+)\s+(directory|file|folder)",
            full_text,
        )
        for path, _ in must_have_structure:
            required_structure.append(
                {"path": path.strip(), "description": f"Required {path.strip()}"}
            )

        policy = {}
        if layer_boundaries:
            policy["layer_boundaries"] = layer_boundaries
        if required_structure:
            policy["required_structure"] = required_structure

        return policy if policy else None

    def _suggest_config_policies(self, full_text: str) -> dict[str, Any] | None:
        """Suggest configuration enforcement policies from text."""
        config_policy = {}

        # TypeScript config patterns
        ts_patterns = {
            r"(?i)typescript.*strict\s+mode": {"tsconfig": {"strict": True}},
            r"(?i)tsconfig.*strict.*true": {"tsconfig": {"strict": True}},
            r"(?i)enable.*noImplicitAny": {
                "tsconfig": {"compilerOptions": {"noImplicitAny": True}}
            },
        }

        typescript_config = {}
        for pattern, config in ts_patterns.items():
            if re.search(pattern, full_text):
                typescript_config.update(config)

        if typescript_config:
            config_policy["typescript"] = typescript_config

        # Python config patterns
        py_patterns = {
            r"(?i)ruff.*check.*imports": {"ruff": {"lint": {"select": ["I"]}}},
            r"(?i)mypy.*strict": {"mypy": {"strict": True}},
        }

        python_config = {}
        for pattern, config in py_patterns.items():
            if re.search(pattern, full_text):
                python_config.update(config)

        if python_config:
            config_policy["python"] = python_config

        return config_policy if config_policy else None

    def _suggest_rationales(self, full_text: str) -> list[str] | None:
        """Extract rationales for the policies from content."""
        rationales = set()

        # Pattern 1: "For X" or "To X"
        rationale_patterns = [
            r"(?i)for\s+(performance|security|maintainability|consistency|bundle\s+size|scalability)",
            r"(?i)to\s+(?:improve|enhance|ensure|maintain)\s+(performance|security|maintainability|consistency)",
            r"(?i)(?:better|improved)\s+(performance|security|maintainability|developer\s+experience|dx)",
            r"(?i)because\s+(?:of\s+)?([^.]+)",
        ]

        for pattern in rationale_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                rationale = match.strip().replace("_", " ").capitalize()
                if len(rationale) > 5:  # Filter out too-short matches
                    rationales.add(rationale)

        return sorted(rationales) if rationales else None

    def _normalize_library_name(self, name: str) -> str | None:
        """Normalize library names using common mappings."""
        # Common library name mappings for normalization
        library_mappings = {
            "react-query": "@tanstack/react-query",
            "react query": "@tanstack/react-query",
            "tanstack query": "@tanstack/react-query",
            "axios": "axios",
            "fetch": "fetch",
            "lodash": "lodash",
            "moment": "moment",
            "momentjs": "moment",
            "moment.js": "moment",
            "date-fns": "date-fns",
            "dayjs": "dayjs",
            "jquery": "jquery",
            "underscore": "underscore",
            "flask": "flask",
            "django": "django",
            "fastapi": "fastapi",
            "express": "express",
        }

        name_lower = name.lower().strip()
        return library_mappings.get(name_lower, name if len(name) > 1 else None)

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

    def _generate_policy_guidance(
        self, adr: ADR, creation_input: CreationInput
    ) -> dict[str, Any] | None:
        """Generate policy guidance promptlet for agents.

        This method creates actionable guidance for agents when policies
        could be extracted from the ADR content but weren't provided
        as structured policy in the front-matter.

        Returns:
            Policy guidance dict with suggestions, or None if policy already provided
        """
        # If policy was already provided, no guidance needed
        if adr.front_matter.policy:
            return {
                "has_policy": True,
                "message": "✅ Structured policy provided and validated",
                "suggestion": None,
            }

        # Analyze decision and alternatives to detect enforceable policies
        alternatives_text = creation_input.alternatives or ""
        suggested = self._suggest_policy_from_alternatives(
            creation_input.decision, alternatives_text
        )

        if suggested:
            # Enforceable policies detected - provide guidance
            import json

            return {
                "has_policy": False,
                "detectable": True,
                "message": (
                    "📋 Enforceable policies detected in ADR content but no structured policy provided. "
                    "To enable automatic enforcement, include a 'policy' parameter when creating ADRs."
                ),
                "suggestion": suggested,
                "suggestion_json": json.dumps(suggested, indent=2),
                "example_usage": (
                    f"adr_create(\n"
                    f"  title='{creation_input.title}',\n"
                    f"  context='{creation_input.context[:50]}...',\n"
                    f"  decision='{creation_input.decision[:50]}...',\n"
                    f"  consequences='{creation_input.consequences[:50]}...',\n"
                    f"  policy={json.dumps(suggested)}\n"
                    f")"
                ),
                "guidance": [
                    "Use the suggested policy structure to enable enforcement",
                    "Adjust the policy dict based on your specific requirements",
                    "Call adr_create() again with the policy parameter",
                ],
                "policy_reference": self._build_policy_reference(),
            }
        else:
            # No enforceable policies detected
            return {
                "has_policy": False,
                "detectable": False,
                "message": (
                    "⚠️  No structured policy provided and no enforceable policies detected in content. "
                    "Use pattern-friendly language to enable constraint extraction."
                ),
                "guidance": [
                    "Import restrictions: 'Don't use X', 'Prefer Y over X'",
                    "Code patterns: 'All X must be Y', 'X must have Y'",
                    "Architecture: 'X must not access Y', 'Required: path/to/file'",
                    "Config: 'TypeScript strict mode required', 'Ruff must check imports'",
                ],
                "suggestion": None,
            }

    def _build_policy_reference(self) -> dict[str, Any]:
        """Build comprehensive policy structure reference documentation.

        This reference is provided just-in-time when agents need to construct
        structured policies, avoiding context bloat in MCP tool docstrings.
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
        }
