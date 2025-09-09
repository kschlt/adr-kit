"""Planning Context Service for ADR-Kit.

The context service provides curated, token-efficient architectural guidance
for agents working on specific tasks. Instead of searching through all ADRs,
agents get exactly what they need: constraints + relevant decisions + guidance.

Key components:
- PlanningContext: Main service for generating context packets
- ContextPacket: The curated context delivered to agents
- TaskAnalyzer: Analyzes tasks to determine relevant architectural decisions
- RelevanceRanker: Ranks ADRs by relevance to specific tasks
- GuidanceGenerator: Creates contextual promptlets for agents
"""

from .planner import PlanningContext, PlanningConfig
from .models import ContextPacket, ContextualADR, PlanningGuidance, TaskHint
from .analyzer import TaskAnalyzer, TaskContext, TaskType
from .ranker import RelevanceRanker, RelevanceScore, RankingStrategy
from .guidance import GuidanceGenerator, GuidanceType, ContextualPromptlet

__all__ = [
    "PlanningContext",
    "PlanningConfig",
    "ContextPacket",
    "ContextualADR",
    "PlanningGuidance",
    "TaskHint",
    "TaskAnalyzer",
    "TaskContext",
    "TaskType",
    "RelevanceRanker",
    "RelevanceScore",
    "RankingStrategy",
    "GuidanceGenerator",
    "GuidanceType",
    "ContextualPromptlet",
]
