"""Semantic-aware policy violation detection for code changes.

Design decisions:
- Use semantic retrieval to find relevant ADRs for code changes
- Parse git diffs to extract file changes and imports
- Match policy violations using both pattern matching and semantic similarity
- Provide actionable guidance with specific ADR references
- Support multiple languages (Python, JavaScript, TypeScript, etc.)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.model import ADR
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from ..core.policy_extractor import PolicyExtractor
from ..semantic.retriever import SemanticIndex, SemanticMatch


@dataclass
class PolicyViolation:
    """Represents a policy violation detected in code changes."""

    violation_type: (
        str  # 'import_disallowed', 'import_not_preferred', 'boundary_violated'
    )
    severity: str  # 'error', 'warning', 'info'
    message: str  # Human-readable description
    file_path: str  # File where violation occurred
    line_number: int | None = None  # Line number if applicable
    adr_id: str | None = None  # ADR that defines the violated policy
    adr_title: str | None = None  # Title of the relevant ADR
    suggested_fix: str | None = None  # Suggested resolution
    context: str | None = None  # Additional context


@dataclass
class CodeAnalysisResult:
    """Result of analyzing code changes for policy violations."""

    violations: list[PolicyViolation]
    analyzed_files: list[str]
    relevant_adrs: list[SemanticMatch]
    summary: str

    @property
    def has_errors(self) -> bool:
        """Check if any error-level violations were found."""
        return any(v.severity == "error" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        """Check if any warning-level violations were found."""
        return any(v.severity == "warning" for v in self.violations)


class DiffParser:
    """Parse git diffs to extract meaningful code changes."""

    def __init__(self) -> None:
        self.import_patterns = {
            "python": [
                r"^import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
                r"^from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import",
            ],
            "javascript": [
                r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'require\([\'"]([^\'"]+)[\'"]\)',
            ],
            "typescript": [
                r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'require\([\'"]([^\'"]+)[\'"]\)',
            ],
        }

    def parse_diff(self, diff_text: str) -> dict[str, list[str]]:
        """Parse a git diff and extract added imports per file.

        Args:
            diff_text: Raw git diff output

        Returns:
            Dictionary mapping file paths to lists of added imports
        """
        file_changes: dict[str, list[str]] = {}
        current_file: str | None = None

        lines = diff_text.split("\n")
        for line in lines:
            # Track which file we're in
            if line.startswith("diff --git"):
                # Extract file path from "diff --git a/path/file.py b/path/file.py"
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3][2:]  # Remove "b/" prefix
                    file_changes[current_file] = []

            # Look for added lines (starting with +)
            elif line.startswith("+") and not line.startswith("+++"):
                if current_file:
                    added_line = line[1:]  # Remove + prefix
                    imports = self._extract_imports_from_line(added_line, current_file)
                    file_changes[current_file].extend(imports)

        return file_changes

    def _extract_imports_from_line(self, line: str, file_path: str) -> list[str]:
        """Extract import statements from a single line of code."""
        line = line.strip()
        if not line:
            return []

        # Determine language from file extension
        file_ext = Path(file_path).suffix.lower()
        language = self._get_language_from_extension(file_ext)

        imports = []
        patterns = self.import_patterns.get(language, [])

        for pattern in patterns:
            matches = re.findall(pattern, line)
            imports.extend(matches)

        return imports

    def _get_language_from_extension(self, ext: str) -> str:
        """Map file extension to language."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }
        return ext_map.get(ext, "unknown")


class SemanticPolicyMatcher:
    """Match code changes to relevant ADRs using semantic similarity."""

    def __init__(self, semantic_index: SemanticIndex):
        self.semantic_index = semantic_index

    def find_relevant_adrs(
        self, file_changes: dict[str, list[str]], context_lines: list[str] | None = None
    ) -> list[SemanticMatch]:
        """Find ADRs that are semantically relevant to the code changes.

        Args:
            file_changes: Dictionary of file paths to imported modules
            context_lines: Additional context lines from the diff

        Returns:
            List of relevant ADR matches
        """
        # Build query from file paths, imports, and context
        query_parts: list[str] = []

        # Add file path context
        for file_path in file_changes.keys():
            path_parts = Path(file_path).parts
            query_parts.extend(path_parts)

        # Add import context
        for imports in file_changes.values():
            query_parts.extend(imports)

        # Add code context if available
        if context_lines:
            for line in context_lines[:5]:  # Limit to avoid noise
                clean_line = re.sub(r"[^\w\s]", " ", line).strip()
                if clean_line and len(clean_line) > 3:
                    query_parts.append(clean_line)

        # Create semantic query
        query = " ".join(query_parts)

        # Search for relevant ADRs (accepted ones are most relevant)
        matches = self.semantic_index.search(
            query=query,
            k=10,
            filter_status={"accepted", "proposed"},  # Focus on active ADRs
        )

        return matches


class GuardSystem:
    """Main guard system for detecting ADR policy violations in code changes."""

    def __init__(self, project_root: Path | None = None, adr_dir: str = "docs/adr"):
        """Initialize guard system with semantic index and policy extractor.

        Args:
            project_root: Project root directory
            adr_dir: Directory containing ADR files
        """
        self.project_root = project_root or Path.cwd()
        self.adr_dir = adr_dir

        # Initialize components
        self.semantic_index = SemanticIndex(project_root)
        self.policy_extractor = PolicyExtractor()
        self.diff_parser = DiffParser()
        self.semantic_matcher = SemanticPolicyMatcher(self.semantic_index)

        # Load ADR policies cache
        self._policy_cache: dict[str, Any] = {}
        self._load_adr_policies()

    def _load_adr_policies(self) -> None:
        """Load and cache policies from all ADRs."""
        print("🔍 Loading ADR policies for guard system...")

        adr_files = find_adr_files(Path(self.adr_dir))
        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if not adr:
                    continue

                # Extract policy using hybrid approach
                policy = self.policy_extractor.extract_policy(adr)
                if policy:
                    self._policy_cache[adr.front_matter.id] = {
                        "adr": adr,
                        "policy": policy,
                    }

            except ParseError:
                continue

        print(f"✅ Loaded {len(self._policy_cache)} ADRs with policies")

    def analyze_diff(
        self, diff_text: str, build_index: bool = True
    ) -> CodeAnalysisResult:
        """Analyze a git diff for policy violations.

        Args:
            diff_text: Raw git diff output
            build_index: Whether to rebuild semantic index before analysis

        Returns:
            CodeAnalysisResult with violations and recommendations
        """
        print("🛡️ Analyzing code changes for policy violations...")

        # Build semantic index if requested
        if build_index:
            print("📊 Building semantic index...")
            self.semantic_index.build_index(self.adr_dir)

        # Parse diff to extract file changes
        file_changes = self.diff_parser.parse_diff(diff_text)

        if not file_changes:
            return CodeAnalysisResult(
                violations=[],
                analyzed_files=[],
                relevant_adrs=[],
                summary="No code changes detected in diff",
            )

        print(f"📁 Analyzing changes in {len(file_changes)} files")

        # Find semantically relevant ADRs
        relevant_adrs = self.semantic_matcher.find_relevant_adrs(file_changes)

        # Check for policy violations
        violations = []
        for file_path, imports in file_changes.items():
            # Check violations against ALL ADRs with policies, not just semantically relevant ones
            all_adrs_for_violation_check = []
            for adr_id, policy_info in self._policy_cache.items():
                # Create a mock SemanticMatch for all ADRs with policies
                all_adrs_for_violation_check.append(
                    type(
                        "MockMatch",
                        (),
                        {
                            "adr_id": adr_id,
                            "title": policy_info["adr"].front_matter.title,
                            "score": 1.0,  # Full score since we're checking all
                        },
                    )()
                )

            file_violations = self._check_file_violations(
                file_path, imports, all_adrs_for_violation_check
            )
            violations.extend(file_violations)

        # Generate summary
        summary = self._generate_summary(violations, file_changes, relevant_adrs)

        return CodeAnalysisResult(
            violations=violations,
            analyzed_files=list(file_changes.keys()),
            relevant_adrs=relevant_adrs,
            summary=summary,
        )

    def _check_file_violations(
        self, file_path: str, imports: list[str], relevant_adrs: list[SemanticMatch]
    ) -> list[PolicyViolation]:
        """Check a single file for policy violations."""
        violations = []

        # Get file language for targeted policy checking
        file_ext = Path(file_path).suffix.lower()
        language = self._get_language_from_extension(file_ext)

        # Check each relevant ADR for violations
        for adr_match in relevant_adrs[:5]:  # Check top 5 most relevant
            if adr_match.adr_id not in self._policy_cache:
                continue

            policy_info = self._policy_cache[adr_match.adr_id]
            adr = policy_info["adr"]
            policy = policy_info["policy"]

            # Check import violations
            violations.extend(
                self._check_import_violations(file_path, imports, adr, policy, language)
            )

            # Check boundary violations (simplified for now)
            violations.extend(
                self._check_boundary_violations(file_path, imports, adr, policy)
            )

        return violations

    def _check_import_violations(
        self, file_path: str, imports: list[str], adr: ADR, policy: Any, language: str
    ) -> list[PolicyViolation]:
        """Check for import policy violations."""
        violations = []

        # Check disallowed imports
        disallowed_imports = []
        if policy.imports and policy.imports.disallow:
            disallowed_imports.extend(policy.imports.disallow)
        if language == "python" and policy.python and policy.python.disallow_imports:
            disallowed_imports.extend(policy.python.disallow_imports)

        for import_name in imports:
            # Check against disallowed list
            for disallowed in disallowed_imports:
                if self._import_matches_pattern(import_name, disallowed):
                    violations.append(
                        PolicyViolation(
                            violation_type="import_disallowed",
                            severity="error",
                            message=f"Import '{import_name}' is disallowed by ADR {adr.front_matter.id}",
                            file_path=file_path,
                            adr_id=adr.front_matter.id,
                            adr_title=adr.front_matter.title,
                            suggested_fix=self._suggest_import_alternative(
                                import_name, policy
                            ),
                            context=f"Disallowed pattern: {disallowed}",
                        )
                    )

        # Check preferred imports (warning if not used)
        if policy.imports and policy.imports.prefer:
            for import_name in imports:
                # Check if there's a preferred alternative
                preferred_alternative = self._find_preferred_alternative(
                    import_name, policy.imports.prefer
                )
                if preferred_alternative:
                    violations.append(
                        PolicyViolation(
                            violation_type="import_not_preferred",
                            severity="warning",
                            message=f"Consider using '{preferred_alternative}' instead of '{import_name}' (ADR {adr.front_matter.id})",
                            file_path=file_path,
                            adr_id=adr.front_matter.id,
                            adr_title=adr.front_matter.title,
                            suggested_fix=f"Replace with: {preferred_alternative}",
                            context="Preferred by ADR policy",
                        )
                    )

        return violations

    def _check_boundary_violations(
        self, file_path: str, imports: list[str], adr: ADR, policy: Any
    ) -> list[PolicyViolation]:
        """Check for architectural boundary violations."""
        violations: list[PolicyViolation] = []

        if not policy.boundaries or not policy.boundaries.rules:
            return violations

        # Simplified boundary checking - can be expanded
        for rule in policy.boundaries.rules:
            if "cross-layer" in rule.forbid.lower() or "layer" in rule.forbid.lower():
                # Check for layer violations based on file path
                file_layer = self._determine_file_layer(file_path)
                for import_name in imports:
                    import_layer = self._determine_import_layer(import_name)
                    if (
                        file_layer
                        and import_layer
                        and self._violates_layer_rule(file_layer, import_layer)
                    ):
                        violations.append(
                            PolicyViolation(
                                violation_type="boundary_violated",
                                severity="error",
                                message=f"Cross-layer import violation: {file_layer} → {import_layer} (ADR {adr.front_matter.id})",
                                file_path=file_path,
                                adr_id=adr.front_matter.id,
                                adr_title=adr.front_matter.title,
                                context=f"Rule: {rule.forbid}",
                            )
                        )

        return violations

    def _import_matches_pattern(self, import_name: str, pattern: str) -> bool:
        """Check if import matches a disallow pattern."""
        # Support glob-like patterns
        if "*" in pattern:
            # Convert glob to regex
            regex_pattern = pattern.replace("*", ".*")
            return re.match(regex_pattern, import_name) is not None
        else:
            # Exact match or prefix match
            return import_name == pattern or import_name.startswith(pattern + ".")

    def _suggest_import_alternative(self, import_name: str, policy: Any) -> str | None:
        """Suggest an alternative import based on policy preferences."""
        if policy.imports and policy.imports.prefer:
            # Find a preferred import that might replace this one
            for preferred in policy.imports.prefer:
                if self._are_similar_imports(import_name, preferred):
                    return str(preferred)
        return None

    def _find_preferred_alternative(
        self, import_name: str, preferred_imports: list[str]
    ) -> str | None:
        """Find if there's a preferred alternative to the current import."""
        for preferred in preferred_imports:
            if self._are_similar_imports(import_name, preferred):
                return preferred
        return None

    def _are_similar_imports(self, import1: str, import2: str) -> bool:
        """Check if two imports are functionally similar."""
        # Simplified similarity check - can be made more sophisticated
        common_alternatives = {
            "lodash": ["ramda", "underscore"],
            "moment": ["dayjs", "date-fns"],
            "axios": ["fetch", "node-fetch"],
            "jquery": ["vanilla-js", "native-dom"],
        }

        for base, alternatives in common_alternatives.items():
            if import1.startswith(base) and any(
                import2.startswith(alt) for alt in alternatives
            ):
                return True
            if import2.startswith(base) and any(
                import1.startswith(alt) for alt in alternatives
            ):
                return True

        return False

    def _determine_file_layer(self, file_path: str) -> str | None:
        """Determine architectural layer from file path."""
        path_parts = file_path.lower().split("/")

        layer_indicators = {
            "controller": ["controller", "api", "route"],
            "service": ["service", "business", "logic"],
            "repository": ["repository", "data", "model", "db"],
            "view": ["view", "template", "component", "ui"],
        }

        for layer, indicators in layer_indicators.items():
            if any(indicator in path_parts for indicator in indicators):
                return layer

        return None

    def _determine_import_layer(self, import_name: str) -> str | None:
        """Determine architectural layer from import name."""
        import_lower = import_name.lower()

        if any(x in import_lower for x in ["express", "fastapi", "flask"]):
            return "controller"
        elif any(x in import_lower for x in ["mongoose", "sqlalchemy", "prisma"]):
            return "repository"
        elif any(x in import_lower for x in ["react", "vue", "angular"]):
            return "view"

        return None

    def _violates_layer_rule(self, from_layer: str, to_layer: str) -> bool:
        """Check if import between layers violates architecture rules."""
        # Simplified layer rule: views shouldn't import repositories directly
        if from_layer == "view" and to_layer == "repository":
            return True

        return False

    def _get_language_from_extension(self, ext: str) -> str:
        """Map file extension to language."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }
        return ext_map.get(ext, "unknown")

    def _generate_summary(
        self,
        violations: list[PolicyViolation],
        file_changes: dict[str, list[str]],
        relevant_adrs: list[SemanticMatch],
    ) -> str:
        """Generate human-readable summary of the analysis."""
        if not violations:
            return f"✅ No policy violations found in {len(file_changes)} files"

        error_count = sum(1 for v in violations if v.severity == "error")
        warning_count = sum(1 for v in violations if v.severity == "warning")

        summary_parts = ["🛡️ Policy analysis complete:"]

        if error_count > 0:
            summary_parts.append(
                f"❌ {error_count} error{'s' if error_count != 1 else ''}"
            )

        if warning_count > 0:
            summary_parts.append(
                f"⚠️ {warning_count} warning{'s' if warning_count != 1 else ''}"
            )

        if relevant_adrs:
            adr_ids = [adr.adr_id for adr in relevant_adrs[:3]]
            summary_parts.append(f"📋 Relevant ADRs: {', '.join(adr_ids)}")

        return " | ".join(summary_parts)
