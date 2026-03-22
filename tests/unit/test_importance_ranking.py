"""Tests for importance-weighted ADR ranking."""

from datetime import date

from adr_kit.context.analyzer import TaskContext, TaskType
from adr_kit.context.ranker import RelevanceRanker
from adr_kit.core.model import (
    ADR,
    ADRFrontMatter,
    ADRStatus,
    ArchitecturePolicy,
    ImportPolicy,
    LayerBoundaryRule,
    PatternPolicy,
    PatternRule,
    PolicyModel,
    PythonPolicy,
)


def make_adr(
    adr_id: str,
    title: str,
    status: ADRStatus = ADRStatus.ACCEPTED,
    tags: list[str] | None = None,
    policy: PolicyModel | None = None,
    content: str = "",
) -> ADR:
    return ADR(
        front_matter=ADRFrontMatter(
            id=adr_id,
            title=title,
            status=status,
            date=date.today(),
            deciders=["test"],
            tags=tags,
            policy=policy,
        ),
        content=content,
    )


class TestCalculateImportanceScore:
    """Unit tests for RelevanceRanker.calculate_importance_score()."""

    def setup_method(self):
        self.ranker = RelevanceRanker()

    def test_no_policy_no_tags_no_references(self):
        """ADR with nothing special gets a low but non-negative score."""
        adr = make_adr("ADR-0001", "Use Postgres")
        score = self.ranker.calculate_importance_score(adr, [adr])
        assert 0.0 <= score <= 0.30  # only minor contribution from anything

    def test_policy_richness_boosts_score(self):
        """ADRs with more policy constraints score higher."""
        sparse = make_adr(
            "ADR-0001",
            "Use Postgres",
            policy=PolicyModel(
                imports=ImportPolicy(disallow=["mysql"]),
            ),
        )
        rich = make_adr(
            "ADR-0002",
            "Use FastAPI",
            policy=PolicyModel(
                imports=ImportPolicy(disallow=["flask", "django"], prefer=["fastapi"]),
                python=PythonPolicy(disallow_imports=["flask"]),
            ),
        )
        sparse_score = self.ranker.calculate_importance_score(sparse, [sparse, rich])
        rich_score = self.ranker.calculate_importance_score(rich, [sparse, rich])
        assert rich_score > sparse_score

    def test_tag_breadth_boosts_score(self):
        """ADRs covering more domains score higher."""
        narrow = make_adr("ADR-0001", "Auth config", tags=["security"])
        broad = make_adr(
            "ADR-0002",
            "Platform decision",
            tags=["security", "backend", "frontend", "database"],
        )
        narrow_score = self.ranker.calculate_importance_score(narrow, [narrow, broad])
        broad_score = self.ranker.calculate_importance_score(broad, [narrow, broad])
        assert broad_score > narrow_score

    def test_centrality_boosts_score(self):
        """ADRs referenced by other ADRs score higher."""
        foundational = make_adr("ADR-0001", "Use Python")
        referencer = make_adr(
            "ADR-0002",
            "Async framework",
            content="This builds on ADR-0001 which chose Python.",
        )
        # foundational is referenced by referencer
        f_score = self.ranker.calculate_importance_score(
            foundational, [foundational, referencer]
        )
        r_score = self.ranker.calculate_importance_score(
            referencer, [foundational, referencer]
        )
        assert f_score > r_score

    def test_superseded_status_penalises_score(self):
        """Superseded ADRs score much lower — they are archival."""
        active = make_adr("ADR-0001", "Use FastAPI", tags=["backend", "api"])
        superseded = make_adr(
            "ADR-0002",
            "Old framework choice",
            status=ADRStatus.SUPERSEDED,
            tags=["backend", "api"],
        )
        # ADRFrontMatter validator requires superseded_by when status=superseded
        superseded.front_matter.superseded_by = ["ADR-0001"]

        active_score = self.ranker.calculate_importance_score(
            active, [active, superseded]
        )
        superseded_score = self.ranker.calculate_importance_score(
            superseded, [active, superseded]
        )
        assert active_score > superseded_score * 4  # superseded should be << active

    def test_rejected_status_penalises_score(self):
        """Rejected ADRs score very low."""
        active = make_adr("ADR-0001", "Use FastAPI", tags=["backend"])
        rejected = make_adr(
            "ADR-0002", "Use Flask", status=ADRStatus.REJECTED, tags=["backend"]
        )
        active_score = self.ranker.calculate_importance_score(
            active, [active, rejected]
        )
        rejected_score = self.ranker.calculate_importance_score(
            rejected, [active, rejected]
        )
        assert active_score > rejected_score

    def test_score_capped_at_one(self):
        """Score never exceeds 1.0 regardless of signals."""
        very_rich = make_adr(
            "ADR-0001",
            "Core platform ADR",
            tags=["backend", "frontend", "security", "database", "deployment", "infra"],
            policy=PolicyModel(
                imports=ImportPolicy(
                    disallow=["a", "b", "c", "d", "e", "f"],
                    prefer=["x", "y", "z"],
                ),
                python=PythonPolicy(disallow_imports=["a", "b", "c"]),
                patterns=PatternPolicy(
                    patterns={
                        "rule1": PatternRule(
                            description="Rule 1", rule=r"async\s+def", language="python"
                        ),
                        "rule2": PatternRule(
                            description="Rule 2", rule=r"def\s+\w+", language="python"
                        ),
                    }
                ),
                architecture=ArchitecturePolicy(
                    layer_boundaries=[
                        LayerBoundaryRule(rule="ui -> database"),
                        LayerBoundaryRule(rule="api -> storage"),
                    ]
                ),
            ),
        )
        # Many referencers
        referencers = [
            make_adr(f"ADR-{i:04d}", f"Extension {i}", content="Extends ADR-0001")
            for i in range(2, 12)
        ]
        score = self.ranker.calculate_importance_score(
            very_rich, [very_rich] + referencers
        )
        assert score <= 1.0

    def test_score_is_non_negative(self):
        """Score is always >= 0.0."""
        adr = make_adr("ADR-0001", "Minimal ADR")
        score = self.ranker.calculate_importance_score(adr, [adr])
        assert score >= 0.0


class TestImportanceBoostInRanking:
    """Test that importance scoring affects rank_adrs_for_task output."""

    def setup_method(self):
        self.ranker = RelevanceRanker()

    def _task_context(self) -> TaskContext:
        return TaskContext(
            task_description="Add a new backend API endpoint",
            task_type=TaskType.FEATURE,
            keywords={"backend", "api", "endpoint"},
            technologies={"backend", "api"},
            file_patterns=set(),
            priority_indicators=[],
            complexity_indicators=[],
        )

    def test_importance_factor_included_in_score_factors(self):
        """The 'importance' factor should appear in scored results."""
        adr = make_adr(
            "ADR-0001",
            "Use FastAPI for backend",
            tags=["backend", "api"],
            policy=PolicyModel(
                imports=ImportPolicy(disallow=["flask"], prefer=["fastapi"])
            ),
        )
        scores = self.ranker.rank_adrs_for_task([adr], self._task_context())
        if scores:  # ADR must pass threshold to appear
            assert "importance" in scores[0].factors

    def test_policy_rich_adr_ranks_above_thin_adr(self):
        """Among two similarly-relevant ADRs, the policy-rich one should rank first."""
        thin = make_adr("ADR-0001", "Use backend service", tags=["backend", "api"])
        rich = make_adr(
            "ADR-0002",
            "Use FastAPI for backend services",
            tags=["backend", "api"],
            policy=PolicyModel(
                imports=ImportPolicy(disallow=["flask", "django"], prefer=["fastapi"]),
                python=PythonPolicy(disallow_imports=["flask"]),
            ),
        )
        scores = self.ranker.rank_adrs_for_task([thin, rich], self._task_context())
        assert len(scores) >= 2
        # rich ADR should rank first
        assert scores[0].adr_id == "ADR-0002"
