"""Main Planning Context Service - curated architectural intelligence for agents."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contract import ConstraintsContractBuilder
from ..core.model import ADR, ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from .analyzer import TaskAnalyzer, TaskContext
from .guidance import GuidanceGenerator
from .models import ContextPacket, ContextualADR, TaskHint
from .ranker import RankingStrategy, RelevanceRanker


@dataclass
class PlanningConfig:
    """Configuration for the planning context service."""

    adr_dir: Path
    max_relevant_adrs: int = 5
    max_token_budget: int = 800  # Target token count for context packets
    ranking_strategy: RankingStrategy = RankingStrategy.HYBRID
    include_superseded: bool = False  # Whether to include superseded ADRs

    def __post_init__(self) -> None:
        self.adr_dir = Path(self.adr_dir)


class PlanningContext:
    """Main service for generating curated planning context packets for agents.

    This is the key service that transforms the agent experience from
    "search through all ADRs" to "here's exactly what you need for this task".
    """

    def __init__(self, config: PlanningConfig):
        self.config = config
        self.analyzer = TaskAnalyzer()
        self.ranker = RelevanceRanker(config.ranking_strategy)
        self.guidance_generator = GuidanceGenerator()
        self.contract_builder = ConstraintsContractBuilder(config.adr_dir)

    def create_context_packet(self, task_hint: TaskHint) -> ContextPacket:
        """Create a curated context packet for a specific task.

        This is the main entry point that produces the planning context
        that agents use to understand architectural constraints and guidance.
        """

        # 1. Analyze the task to understand what the agent is trying to do
        task_context = self.analyzer.analyze_task(task_hint)

        # 2. Load current constraints contract
        constraints_contract = None
        try:
            constraints_contract = self.contract_builder.build_contract()
        except Exception:
            # If contract build fails, continue without constraints
            pass

        # 3. Load and filter ADRs
        all_adrs = self._load_all_adrs()
        relevant_adrs = self._find_relevant_adrs(all_adrs, task_context)

        # 4. Generate contextual guidance
        relevance_scores = self.ranker.rank_adrs_for_task(all_adrs, task_context)
        guidance = self.guidance_generator.generate_guidance(
            task_context, constraints_contract, relevant_adrs, relevance_scores
        )

        # 5. Create summary guidance
        summary = self.guidance_generator.generate_summary_guidance(
            task_context, relevant_adrs, constraints_contract
        )

        # 6. Build context packet
        context_packet = ContextPacket(
            task_description=task_hint.task_description,
            task_type=task_context.task_type.value,
            hard_constraints=self._extract_hard_constraints(constraints_contract),
            contract_hash=(
                constraints_contract.metadata.hash if constraints_contract else ""
            ),
            relevant_adrs=relevant_adrs,
            guidance=guidance,
            token_estimate=0,  # Will be calculated
            adr_directory=str(self.config.adr_dir),
            summary=summary,
        )

        # 7. Update token estimate and optimize if needed
        context_packet.update_token_estimate()
        if context_packet.token_estimate > self.config.max_token_budget:
            context_packet = self._optimize_token_usage(context_packet)

        return context_packet

    def create_context_for_files(
        self,
        task_description: str,
        changed_files: list[str],
        task_type: str | None = None,
    ) -> ContextPacket:
        """Create context packet based on files being changed."""

        # Extract technologies from file paths
        technologies = self._extract_technologies_from_files(changed_files)

        task_hint = TaskHint(
            task_description=task_description,
            changed_files=changed_files,
            technologies_mentioned=list(technologies),
            task_type=task_type,
            priority="medium",  # Default priority
        )

        return self.create_context_packet(task_hint)

    def create_bulk_context(self, task_hints: list[TaskHint]) -> list[ContextPacket]:
        """Create context packets for multiple related tasks."""
        return [self.create_context_packet(hint) for hint in task_hints]

    def _load_all_adrs(self) -> list[ADR]:
        """Load all ADRs from the configured directory."""
        adr_files = find_adr_files(self.config.adr_dir)
        adrs = []

        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if adr:
                    # Filter by status if configured
                    if (
                        not self.config.include_superseded
                        and adr.front_matter.status == ADRStatus.SUPERSEDED
                    ):
                        continue
                    adrs.append(adr)
            except ParseError:
                # Skip malformed ADRs
                continue

        return adrs

    def _find_relevant_adrs(
        self, all_adrs: list[ADR], task_context: TaskContext
    ) -> list[ContextualADR]:
        """Find and rank ADRs relevant to the task context."""

        # Get relevance scores
        top_relevant = self.ranker.get_top_n_relevant(
            all_adrs, task_context, self.config.max_relevant_adrs
        )

        # Convert to ContextualADR objects
        contextual_adrs = []
        for adr, score in top_relevant:
            contextual_adr = ContextualADR(
                id=adr.id,
                title=adr.front_matter.title,
                status=adr.front_matter.status,
                summary=self._generate_adr_summary(adr),
                relevance_score=score.score,
                relevance_reason=", ".join(score.reasons[:2]),  # Top 2 reasons
                key_constraints=self._extract_key_constraints(adr),
                related_technologies=self._extract_related_technologies(adr),
            )
            contextual_adrs.append(contextual_adr)

        return contextual_adrs

    def _extract_hard_constraints(self, contract: Any | None) -> dict[str, Any]:
        """Extract hard constraints from the constraints contract."""
        if not contract or contract.constraints.is_empty():
            return {}

        constraints: dict[str, Any] = {}

        # Import constraints
        if contract.constraints.imports:
            constraints["imports"] = {}
            if contract.constraints.imports.disallow:
                constraints["imports"][
                    "disallow"
                ] = contract.constraints.imports.disallow
            if contract.constraints.imports.prefer:
                constraints["imports"]["prefer"] = contract.constraints.imports.prefer

        # Boundary constraints
        if contract.constraints.boundaries:
            constraints["boundaries"] = {}
            if contract.constraints.boundaries.rules:
                constraints["boundaries"]["rules"] = [
                    {"forbid": rule.forbid}
                    for rule in contract.constraints.boundaries.rules
                ]

        # Python constraints
        if contract.constraints.python and contract.constraints.python.disallow_imports:
            constraints["python"] = {
                "disallow_imports": contract.constraints.python.disallow_imports
            }

        return constraints

    def _generate_adr_summary(self, adr: ADR) -> str:
        """Generate a concise summary of an ADR."""
        # Extract first sentence of context or decision section
        content = adr.content.lower()

        # Look for common patterns
        patterns = [
            r"## context\s*\n(.+?)(?:\n|\.|!|\?)",
            r"## decision\s*\n(.+?)(?:\n|\.|!|\?)",
            r"## summary\s*\n(.+?)(?:\n|\.|!|\?)",
            r"^(.+?)(?:\n|\.|!|\?)",  # First sentence of content
        ]

        for pattern in patterns:
            import re

            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                summary = match.group(1).strip()
                # Clean up and limit length
                summary = re.sub(r"\s+", " ", summary)  # Normalize whitespace
                if len(summary) > 100:
                    summary = summary[:97] + "..."
                return summary

        # Fallback to title-based summary
        return f"Decision about {adr.front_matter.title.lower()}"

    def _extract_key_constraints(self, adr: ADR) -> list[str]:
        """Extract key constraints from an ADR."""
        constraints = []

        # Extract from structured policy
        if adr.front_matter.policy:
            policy = adr.front_matter.policy

            if policy.imports:
                if policy.imports.disallow:
                    constraints.extend(
                        [f"Don't use {item}" for item in policy.imports.disallow[:2]]
                    )
                if policy.imports.prefer:
                    constraints.extend(
                        [f"Prefer {item}" for item in policy.imports.prefer[:2]]
                    )

            if policy.boundaries and policy.boundaries.rules:
                for rule in policy.boundaries.rules[:2]:
                    constraints.append(f"Boundary: {rule.forbid}")

        # Extract from content (simple patterns)
        content = adr.content.lower()
        constraint_patterns = [
            r"must (not )?(.+?)(?:\n|\.)",
            r"should (not )?(.+?)(?:\n|\.)",
            r"required? to (.+?)(?:\n|\.)",
            r"forbidden to (.+?)(?:\n|\.)",
        ]

        import re

        for pattern in constraint_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:1]:  # Limit to avoid too many
                if isinstance(match, tuple):
                    not_part, constraint = match
                    prefix = "Don't" if not_part else "Must"
                    constraints.append(f"{prefix} {constraint.strip()}")
                else:
                    constraints.append(f"Must {match.strip()}")

        return constraints[:3]  # Limit to top 3 constraints

    def _extract_related_technologies(self, adr: ADR) -> list[str]:
        """Extract technologies mentioned in an ADR."""
        text = f"{adr.front_matter.title} {adr.content}".lower()
        technologies = []

        # Common technology patterns
        tech_patterns = [
            r"\b(react|vue|angular|javascript|typescript|python|java|go|rust)\b",
            r"\b(nodejs|express|django|flask|spring|gin)\b",
            r"\b(postgres|mysql|mongodb|redis|sqlite)\b",
            r"\b(docker|kubernetes|aws|gcp|azure)\b",
            r"\b(jest|pytest|junit|mocha)\b",
        ]

        import re

        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            technologies.extend(matches)

        # Remove duplicates and limit
        return list(set(technologies))[:5]

    def _extract_technologies_from_files(self, changed_files: list[str]) -> set[str]:
        """Extract technologies from file paths."""
        technologies = set()

        for file_path in changed_files:
            path = Path(file_path)

            # File extension mapping
            ext_mapping = {
                ".js": "javascript",
                ".jsx": "react",
                ".ts": "typescript",
                ".tsx": "react",
                ".py": "python",
                ".java": "java",
                ".go": "go",
                ".rs": "rust",
                ".sql": "database",
                ".yml": "config",
                ".yaml": "config",
                ".json": "config",
                ".md": "docs",
            }

            if path.suffix in ext_mapping:
                technologies.add(ext_mapping[path.suffix])

            # Directory patterns
            if "test" in str(path).lower():
                technologies.add("testing")
            if "component" in str(path).lower():
                technologies.add("react")
            if "api" in str(path).lower():
                technologies.add("backend")

        return technologies

    def _optimize_token_usage(self, context_packet: ContextPacket) -> ContextPacket:
        """Optimize context packet to fit within token budget."""

        # If over budget, reduce content strategically
        if context_packet.token_estimate > self.config.max_token_budget:

            # 1. Reduce number of relevant ADRs
            if len(context_packet.relevant_adrs) > 3:
                context_packet.relevant_adrs = context_packet.relevant_adrs[:3]

            # 2. Reduce guidance items
            if len(context_packet.guidance) > 5:
                # Keep highest priority guidance
                context_packet.guidance = sorted(
                    context_packet.guidance,
                    key=lambda g: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                        g.priority, 3
                    ),
                )[:5]

            # 3. Truncate ADR summaries
            for adr in context_packet.relevant_adrs:
                if adr.summary and len(adr.summary) > 60:
                    adr.summary = adr.summary[:57] + "..."

            # 4. Reduce key constraints per ADR
            for adr in context_packet.relevant_adrs:
                if len(adr.key_constraints) > 2:
                    adr.key_constraints = adr.key_constraints[:2]

            # Update token estimate after optimization
            context_packet.update_token_estimate()

        return context_packet

    def get_service_status(self) -> dict[str, Any]:
        """Get status of the planning context service."""
        try:
            all_adrs = self._load_all_adrs()

            return {
                "service_ready": True,
                "adr_directory": str(self.config.adr_dir),
                "config": {
                    "max_relevant_adrs": self.config.max_relevant_adrs,
                    "max_token_budget": self.config.max_token_budget,
                    "ranking_strategy": self.config.ranking_strategy.value,
                    "include_superseded": self.config.include_superseded,
                },
                "statistics": {
                    "total_adrs": len(all_adrs),
                    "accepted_adrs": len(
                        [
                            adr
                            for adr in all_adrs
                            if adr.front_matter.status == ADRStatus.ACCEPTED
                        ]
                    ),
                    "proposed_adrs": len(
                        [
                            adr
                            for adr in all_adrs
                            if adr.front_matter.status == ADRStatus.PROPOSED
                        ]
                    ),
                },
                "message": "Planning context service ready to generate curated guidance",
            }

        except Exception as e:
            return {
                "service_ready": False,
                "error": str(e),
                "message": "Planning context service initialization failed",
            }
