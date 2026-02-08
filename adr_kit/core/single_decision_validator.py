"""Single Decision Validator - Ensures ADRs contain only one architectural decision.

This module implements validation logic to detect when an ADR attempts to document
multiple independent decisions, which should instead be split into separate ADRs.

Design principles:
- ADRs should follow the Single Responsibility Principle
- Each ADR documents ONE architectural decision with its rationale
- Multiple related implementation details are OK, multiple independent decisions are not
- Validation provides warnings, not hard blocks (user can override)
"""

import re
from dataclasses import dataclass
from typing import Any

from .model import ADR, PolicyModel


@dataclass
class ValidationWarning:
    """A warning about potential multiple decisions in an ADR."""

    type: str  # WARNING_TYPE constant
    message: str  # Human-readable description
    suggestion: str  # Actionable guidance
    severity: str  # "low", "medium", "high"
    evidence: list[str]  # Specific examples from the ADR


# Warning type constants
MULTIPLE_DECISIONS_IN_TITLE = "MULTIPLE_DECISIONS_IN_TITLE"
MULTIPLE_CHOICES_IN_DECISION = "MULTIPLE_CHOICES_IN_DECISION"
POLICY_SPANS_MULTIPLE_DOMAINS = "POLICY_SPANS_MULTIPLE_DOMAINS"
EXCESSIVE_AND_USAGE = "EXCESSIVE_AND_USAGE"


class SingleDecisionValidator:
    """Validates that an ADR contains a single architectural decision."""

    def __init__(self) -> None:
        """Initialize the validator with pattern definitions."""
        # Technology choice verbs
        self.choice_verbs = [
            "use",
            "choose",
            "select",
            "adopt",
            "deploy",
            "implement",
            "integrate",
        ]

        # Direct technology-to-domain mappings
        self.tech_domains = {
            # Backend frameworks/languages
            "fastapi": "backend",
            "flask": "backend",
            "django": "backend",
            "express": "backend",
            "spring": "backend",
            "rails": "backend",
            "node.js": "backend",
            "nodejs": "backend",
            "python": "backend",
            "java": "backend",
            "go": "backend",
            "rust": "backend",
            "bottle": "backend",
            # Frontend frameworks/libraries
            "react": "frontend",
            "vue": "frontend",
            "angular": "frontend",
            "svelte": "frontend",
            "next.js": "frontend",
            "nextjs": "frontend",
            "nuxt": "frontend",
            "typescript": "frontend",
            "javascript": "frontend",
            "tailwind": "frontend",
            "tailwindcss": "frontend",
            "bootstrap": "frontend",
            # Databases
            "postgresql": "database",
            "postgres": "database",
            "mysql": "database",
            "mongodb": "database",
            "redis": "database",
            "sqlite": "database",
            "cassandra": "database",
            "dynamodb": "database",
            "elasticsearch": "database",
            # Infrastructure/deployment
            "docker": "infrastructure",
            "kubernetes": "infrastructure",
            "k8s": "infrastructure",
            "aws": "infrastructure",
            "azure": "infrastructure",
            "gcp": "infrastructure",
            "fly.io": "infrastructure",
        }

        # Common technology categories for domain detection (fallback)
        self.domain_keywords = {
            "backend": ["api", "server", "backend", "service", "endpoint"],
            "frontend": ["ui", "frontend", "client", "component", "view"],
            "database": ["database", "db", "storage", "persistence", "data"],
            "infrastructure": [
                "deploy",
                "host",
                "infrastructure",
                "docker",
                "kubernetes",
            ],
            "testing": ["test", "testing", "qa", "quality"],
            "security": ["auth", "security", "encryption", "permission"],
        }

    def validate(self, adr: ADR) -> list[ValidationWarning]:
        """Validate that ADR contains a single decision.

        Returns list of warnings (empty if no issues detected).
        """
        warnings: list[ValidationWarning] = []

        # Check 1: Title contains "and" with multiple choices
        title_warnings = self._check_title(adr.front_matter.title)
        warnings.extend(title_warnings)

        # Check 2: Decision section has multiple independent choices
        decision_warnings = self._check_decision_section(adr.parsed_content.decision)
        warnings.extend(decision_warnings)

        # Check 3: Policy spans too many unrelated domains
        if adr.front_matter.policy:
            policy_warnings = self._check_policy_domains(adr.front_matter.policy)
            warnings.extend(policy_warnings)

        # Check 4: Excessive "and" usage throughout
        and_warnings = self._check_excessive_and_usage(
            adr.front_matter.title, adr.parsed_content.decision
        )
        warnings.extend(and_warnings)

        return warnings

    def _check_title(self, title: str) -> list[ValidationWarning]:
        """Check if title suggests multiple decisions."""
        warnings = []

        # Pattern: "Use X and Y" or "Choose X and Y"
        title_lower = title.lower()

        if " and " not in title_lower:
            return warnings

        # Check if "and" connects two technology choices
        for verb in self.choice_verbs:
            # Pattern: "Use X and Y", "Use X and deploy to Y"
            pattern = rf"\b{verb}\s+\w+\s+and\s+(\w+\s+)?\w+"
            if re.search(pattern, title_lower):
                warnings.append(
                    ValidationWarning(
                        type=MULTIPLE_DECISIONS_IN_TITLE,
                        message=f"Title contains '{verb} ... and ...' suggesting multiple decisions",
                        suggestion="Consider splitting into separate ADRs, one per technology choice",
                        severity="high",
                        evidence=[title],
                    )
                )
                break

        # Pattern: "X and Y" where X and Y are both technology names (capitalized)
        # Example: "FastAPI and PostgreSQL", "React and TypeScript"
        if " and " in title_lower:
            # Look for two capitalized terms connected by "and"
            capital_and_pattern = r"\b([A-Z][a-z]*(?:[A-Z][a-z]*)*)\s+and\s+([A-Z][a-z]*(?:[A-Z][a-z]*)*)\b"
            matches = re.findall(capital_and_pattern, title)
            if matches and len(matches) > 0:
                tech1, tech2 = matches[0]
                # Check if they're in different domains
                domain1 = self._detect_domain(tech1.lower())
                domain2 = self._detect_domain(tech2.lower())

                if domain1 and domain2 and domain1 != domain2:
                    warnings.append(
                        ValidationWarning(
                            type=MULTIPLE_DECISIONS_IN_TITLE,
                            message=f"Title combines technologies from different domains: '{tech1}' ({domain1}) and '{tech2}' ({domain2})",
                            suggestion=f"Split into: (1) ADR for {tech1} ({domain1}), (2) ADR for {tech2} ({domain2})",
                            severity="high",
                            evidence=[title],
                        )
                    )

        return warnings

    def _check_decision_section(self, decision_text: str) -> list[ValidationWarning]:
        """Check if decision section contains multiple independent choices."""
        warnings = []

        if not decision_text:
            return warnings

        # Count technology choice statements
        choice_pattern = r"\b(" + "|".join(self.choice_verbs) + r")\s+([A-Z]\w+)"
        matches = re.findall(choice_pattern, decision_text, re.IGNORECASE)

        if len(matches) > 2:  # Allow up to 2 related choices (e.g., "Use React with TypeScript")
            technologies = [match[1] for match in matches]
            warnings.append(
                ValidationWarning(
                    type=MULTIPLE_CHOICES_IN_DECISION,
                    message=f"Decision section contains {len(matches)} distinct technology choices: {', '.join(technologies)}",
                    suggestion="Each major technology choice should be its own ADR with dedicated rationale",
                    severity="medium",
                    evidence=[f"{match[0]} {match[1]}" for match in matches[:3]],
                )
            )

        # Check for sentences with multiple "and" connecting technologies
        sentences = decision_text.split(".")
        for sentence in sentences:
            and_count = sentence.lower().count(" and ")
            if and_count >= 2:  # Multiple "and"s in one sentence
                # Check if it's listing technologies
                tech_count = sum(
                    1 for verb in self.choice_verbs if verb in sentence.lower()
                )
                if tech_count >= 2:
                    warnings.append(
                        ValidationWarning(
                            type=EXCESSIVE_AND_USAGE,
                            message="Decision sentence combines multiple technology choices with 'and'",
                            suggestion="Break down into one ADR per major technology decision",
                            severity="medium",
                            evidence=[sentence.strip()[:100]],
                        )
                    )
                    break

        return warnings

    def _check_policy_domains(self, policy: PolicyModel) -> list[ValidationWarning]:
        """Check if policy spans too many unrelated domains."""
        warnings = []

        # Detect which domains the policy touches
        policy_domains = set()

        # Check import policies
        if policy.imports:
            all_imports = (policy.imports.disallow or []) + (policy.imports.prefer or [])
            for imp in all_imports:
                domain = self._detect_domain(imp.lower())
                if domain:
                    policy_domains.add(domain)

        # Check Python policies
        if policy.python and policy.python.disallow_imports:
            for imp in policy.python.disallow_imports:
                domain = self._detect_domain(imp.lower())
                if domain:
                    policy_domains.add(domain)

        # Check boundary policies (infrastructure/architecture)
        if policy.boundaries:
            if policy.boundaries.layers or policy.boundaries.rules:
                policy_domains.add("architecture")

        # Warning if policy spans 3+ unrelated domains
        if len(policy_domains) >= 3:
            warnings.append(
                ValidationWarning(
                    type=POLICY_SPANS_MULTIPLE_DOMAINS,
                    message=f"Policy spans {len(policy_domains)} domains: {', '.join(sorted(policy_domains))}",
                    suggestion="Consider creating separate ADRs for each domain (backend, frontend, database, etc.)",
                    severity="medium",
                    evidence=[f"Domains: {', '.join(sorted(policy_domains))}"],
                )
            )

        return warnings

    def _check_excessive_and_usage(
        self, title: str, decision_text: str
    ) -> list[ValidationWarning]:
        """Check for excessive use of 'and' suggesting scope creep."""
        warnings = []

        combined_text = f"{title} {decision_text}"
        and_count = combined_text.lower().count(" and ")

        # If "and" appears 4+ times, likely trying to do too much
        if and_count >= 4:
            warnings.append(
                ValidationWarning(
                    type=EXCESSIVE_AND_USAGE,
                    message=f"ADR contains '{and_count}' instances of 'and' - may indicate scope creep",
                    suggestion="Focus on one primary decision; related details can be implementation notes",
                    severity="low",
                    evidence=[
                        f"'and' appears {and_count} times across title and decision"
                    ],
                )
            )

        return warnings

    def _detect_domain(self, text: str) -> str | None:
        """Detect which domain a technology/term belongs to."""
        text_lower = text.lower()

        # First, check direct technology mappings
        if text_lower in self.tech_domains:
            return self.tech_domains[text_lower]

        # Then check if text contains any mapped technology
        for tech, domain in self.tech_domains.items():
            if tech in text_lower:
                return domain

        # Finally, fall back to keyword matching
        for domain, keywords in self.domain_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return domain

        return None

    def has_critical_warnings(self, warnings: list[ValidationWarning]) -> bool:
        """Check if any warnings are critical (high severity)."""
        return any(w.severity == "high" for w in warnings)

    def format_warnings_for_display(self, warnings: list[ValidationWarning]) -> str:
        """Format warnings for human-readable display."""
        if not warnings:
            return "✅ No validation warnings - ADR focuses on single decision"

        output = ["⚠️  Single Decision Validation Warnings:\n"]

        for i, warning in enumerate(warnings, 1):
            severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🔵"}[
                warning.severity
            ]

            output.append(f"{i}. {severity_emoji} {warning.message}")
            output.append(f"   💡 Suggestion: {warning.suggestion}")

            if warning.evidence:
                output.append(f"   📝 Evidence:")
                for evidence in warning.evidence[:2]:  # Show first 2 pieces
                    output.append(f"      - {evidence}")

            output.append("")  # Blank line

        return "\n".join(output)


def validate_single_decision(adr: ADR) -> tuple[bool, list[ValidationWarning]]:
    """Convenience function to validate an ADR.

    Returns:
        (is_valid, warnings) where is_valid is False if there are critical warnings
    """
    validator = SingleDecisionValidator()
    warnings = validator.validate(adr)

    # Consider valid unless there are high severity warnings
    is_valid = not validator.has_critical_warnings(warnings)

    return is_valid, warnings
