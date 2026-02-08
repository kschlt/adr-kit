"""Knowledge module for ADR-Kit AI Steering Suite.

Provides machine-readable evaluation criteria and category mappings
that workflows use to assemble focused promptlets for the calling
agent's LLM.

Key components:
- KnowledgeLoader: Loads evaluation criteria and category mappings from JSON
"""

from .loader import CategoryCriteria, KnowledgeLoader

__all__ = [
    "KnowledgeLoader",
    "CategoryCriteria",
]
