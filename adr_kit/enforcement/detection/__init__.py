"""Guard system for ADR policy enforcement in code changes.

This package provides semantic-aware policy violation detection for code diffs,
integrating with the ADR semantic retrieval system for context-aware enforcement.
"""

from .detector import CodeAnalysisResult, GuardSystem, PolicyViolation

__all__ = ["GuardSystem", "PolicyViolation", "CodeAnalysisResult"]
