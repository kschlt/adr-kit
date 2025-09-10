"""ADR relevance ranking system for contextual planning."""

import re
from datetime import date
from enum import Enum

from ..core.model import ADR, ADRStatus
from .analyzer import TaskContext
from .models import RelevanceScore


class RankingStrategy(str, Enum):
    """Strategies for ranking ADR relevance."""

    LEXICAL = "lexical"  # Simple keyword matching
    SEMANTIC = "semantic"  # Semantic similarity (future)
    HYBRID = "hybrid"  # Combination approach
    RECENCY = "recency"  # Weight recent decisions more
    STATUS_AWARE = "status_aware"  # Consider ADR status in ranking


class RelevanceRanker:
    """Ranks ADRs by relevance to specific tasks and contexts."""

    def __init__(self, strategy: RankingStrategy = RankingStrategy.HYBRID):
        self.strategy = strategy

        # Technology category mappings for better matching
        self.tech_categories = {
            "frontend": [
                "react",
                "vue",
                "angular",
                "javascript",
                "typescript",
                "css",
                "html",
                "ui",
                "ux",
                "component",
            ],
            "backend": [
                "api",
                "server",
                "service",
                "nodejs",
                "python",
                "java",
                "go",
                "database",
                "sql",
            ],
            "data": [
                "database",
                "sql",
                "nosql",
                "mongodb",
                "postgres",
                "mysql",
                "redis",
                "schema",
                "migration",
            ],
            "testing": [
                "test",
                "testing",
                "jest",
                "pytest",
                "spec",
                "coverage",
                "unit",
                "integration",
            ],
            "deployment": [
                "deploy",
                "ci",
                "cd",
                "docker",
                "kubernetes",
                "aws",
                "cloud",
                "infrastructure",
            ],
            "security": [
                "auth",
                "authentication",
                "authorization",
                "security",
                "oauth",
                "jwt",
                "encryption",
            ],
        }

    def rank_adrs_for_task(
        self, adrs: list[ADR], task_context: TaskContext
    ) -> list[RelevanceScore]:
        """Rank ADRs by relevance to a specific task context."""
        scores = []

        for adr in adrs:
            score = self._calculate_relevance_score(adr, task_context)
            if score.score > 0.1:  # Only include ADRs with meaningful relevance
                scores.append(score)

        # Sort by score (highest first)
        scores.sort(key=lambda x: x.score, reverse=True)

        return scores

    def _calculate_relevance_score(
        self, adr: ADR, task_context: TaskContext
    ) -> RelevanceScore:
        """Calculate relevance score for a single ADR."""
        factors = {}
        reasons = []

        # 1. Technology overlap
        tech_score, tech_reasons = self._score_technology_overlap(adr, task_context)
        factors["technology"] = tech_score
        reasons.extend(tech_reasons)

        # 2. Keyword overlap
        keyword_score, keyword_reasons = self._score_keyword_overlap(adr, task_context)
        factors["keywords"] = keyword_score
        reasons.extend(keyword_reasons)

        # 3. ADR status weight
        status_score = self._score_adr_status(adr)
        factors["status"] = status_score
        if status_score > 0:
            status_val = (
                adr.front_matter.status.value
                if hasattr(adr.front_matter.status, "value")
                else str(adr.front_matter.status)
            )
            reasons.append(f"ADR status: {status_val}")

        # 4. Recency weight
        recency_score = self._score_recency(adr)
        factors["recency"] = recency_score

        # 5. Policy relevance
        policy_score, policy_reasons = self._score_policy_relevance(adr, task_context)
        factors["policy"] = policy_score
        reasons.extend(policy_reasons)

        # 6. Task type alignment
        task_type_score, task_type_reasons = self._score_task_type_alignment(
            adr, task_context
        )
        factors["task_type"] = task_type_score
        reasons.extend(task_type_reasons)

        # Calculate weighted final score
        final_score = self._compute_weighted_score(factors)

        return RelevanceScore(
            adr_id=adr.id,
            score=final_score,
            reasons=reasons[:5],  # Limit to top 5 reasons
            factors=factors,
        )

    def _score_technology_overlap(
        self, adr: ADR, task_context: TaskContext
    ) -> tuple[float, list[str]]:
        """Score based on technology overlap."""
        adr_text = f"{adr.front_matter.title} {adr.content}".lower()
        adr_technologies = set()
        reasons = []

        # Extract technologies from ADR content
        for category, techs in self.tech_categories.items():
            for tech in techs:
                if tech in adr_text:
                    adr_technologies.add(tech)
                    adr_technologies.add(category)

        # Find overlap with task technologies
        overlap = adr_technologies.intersection(task_context.technologies)

        if not overlap:
            return 0.0, []

        # Score based on overlap ratio and importance
        overlap_ratio = len(overlap) / max(len(task_context.technologies), 1)
        tech_score = min(overlap_ratio * 2, 1.0)  # Cap at 1.0

        # Generate reasons
        if len(overlap) <= 3:
            reasons.append(f"Shared technologies: {', '.join(sorted(overlap))}")
        else:
            top_overlap = sorted(overlap)[:3]
            reasons.append(
                f"Shared technologies: {', '.join(top_overlap)} and {len(overlap)-3} more"
            )

        return tech_score, reasons

    def _score_keyword_overlap(
        self, adr: ADR, task_context: TaskContext
    ) -> tuple[float, list[str]]:
        """Score based on keyword overlap."""
        adr_text = f"{adr.front_matter.title} {adr.content}".lower()
        adr_keywords = set(re.findall(r"\b[a-zA-Z]{3,}\b", adr_text))

        # Find overlap with task keywords
        overlap = adr_keywords.intersection(task_context.keywords)

        if not overlap:
            return 0.0, []

        # Score based on overlap significance
        overlap_ratio = len(overlap) / max(len(task_context.keywords), 1)
        keyword_score = min(overlap_ratio, 0.5)  # Cap at 0.5 for keywords

        reasons = []
        if len(overlap) <= 2:
            reasons.append(f"Keyword overlap: {', '.join(sorted(overlap))}")

        return keyword_score, reasons

    def _score_adr_status(self, adr: ADR) -> float:
        """Score based on ADR status (accepted decisions are most relevant)."""
        status_weights = {
            ADRStatus.ACCEPTED: 1.0,
            ADRStatus.PROPOSED: 0.7,  # Still relevant for context
            ADRStatus.SUPERSEDED: 0.3,  # Less relevant but provides history
            ADRStatus.DEPRECATED: 0.2,
            ADRStatus.REJECTED: 0.1,
        }

        return status_weights.get(adr.front_matter.status, 0.5)

    def _score_recency(self, adr: ADR) -> float:
        """Score based on how recent the ADR is."""
        adr_date = adr.front_matter.date
        today = date.today()
        days_old = (today - adr_date).days

        # Recent ADRs (< 30 days) get bonus, very old (> 365 days) get penalty
        if days_old < 30:
            return 0.2  # Recent bonus
        elif days_old > 365:
            return -0.1  # Old penalty
        else:
            return 0.0  # Neutral

    def _score_policy_relevance(
        self, adr: ADR, task_context: TaskContext
    ) -> tuple[float, list[str]]:
        """Score based on whether ADR has policies relevant to the task."""
        if not adr.front_matter.policy:
            return 0.0, []

        policy = adr.front_matter.policy
        reasons = []
        score = 0.0

        # Import policies are highly relevant for dependency-related tasks
        if policy.imports and task_context.task_type.value in [
            "dependency",
            "feature",
            "refactor",
        ]:
            score += 0.3
            reasons.append("Has import/dependency policies")

        # Boundary policies relevant for architectural tasks
        if policy.boundaries and any(
            word in task_context.keywords
            for word in ["architecture", "structure", "layer"]
        ):
            score += 0.2
            reasons.append("Has architectural boundary policies")

        return min(score, 0.5), reasons  # Cap policy score

    def _score_task_type_alignment(
        self, adr: ADR, task_context: TaskContext
    ) -> tuple[float, list[str]]:
        """Score based on how well ADR aligns with task type."""
        adr_text = f"{adr.front_matter.title} {adr.content}".lower()
        task_type = task_context.task_type.value
        reasons = []

        # Task type specific patterns
        alignment_patterns = {
            "feature": ["implement", "add", "new", "feature", "functionality"],
            "bugfix": ["fix", "bug", "issue", "problem", "resolve"],
            "refactor": ["refactor", "improve", "optimize", "restructure"],
            "dependency": ["library", "package", "dependency", "framework", "install"],
            "testing": ["test", "testing", "coverage", "spec", "validation"],
            "security": ["auth", "security", "permission", "access", "encryption"],
            "performance": ["performance", "speed", "optimize", "cache", "memory"],
        }

        patterns = alignment_patterns.get(task_type, [])
        matches = sum(1 for pattern in patterns if pattern in adr_text)

        if matches > 0:
            score = min(matches * 0.1, 0.3)  # Cap at 0.3
            reasons.append(f"Aligns with {task_type} task type")
            return score, reasons

        return 0.0, []

    def _compute_weighted_score(self, factors: dict[str, float]) -> float:
        """Compute final weighted relevance score."""
        # Weights for different factors
        weights = {
            "technology": 0.35,  # Technology overlap is most important
            "keywords": 0.20,  # Keyword overlap is significant
            "status": 0.20,  # ADR status matters
            "policy": 0.15,  # Policy relevance is important
            "task_type": 0.10,  # Task type alignment helps
            "recency": 0.05,  # Recency is a minor factor
        }

        # Calculate weighted sum
        weighted_sum = sum(
            weights.get(factor, 0) * value for factor, value in factors.items()
        )

        # Apply strategy-specific adjustments
        if self.strategy == RankingStrategy.RECENCY:
            # Boost recency weight
            weighted_sum = weighted_sum * 0.8 + factors.get("recency", 0) * 0.2
        elif self.strategy == RankingStrategy.STATUS_AWARE:
            # Boost status weight
            weighted_sum = weighted_sum * 0.8 + factors.get("status", 0) * 0.2

        return max(0.0, min(1.0, weighted_sum))  # Clamp to [0,1]

    def get_top_n_relevant(
        self, adrs: list[ADR], task_context: TaskContext, n: int = 5
    ) -> list[tuple[ADR, RelevanceScore]]:
        """Get top N most relevant ADRs with their scores."""
        scores = self.rank_adrs_for_task(adrs, task_context)

        # Create lookup for ADRs by ID
        adr_lookup = {adr.id: adr for adr in adrs}

        # Return top N with ADRs
        top_scores = scores[:n]
        return [
            (adr_lookup[score.adr_id], score)
            for score in top_scores
            if score.adr_id in adr_lookup
        ]
