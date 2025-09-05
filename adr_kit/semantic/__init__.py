"""Semantic retrieval system for ADRs.

This package provides semantic search capabilities using local embeddings
and vector similarity matching for intelligent ADR discovery.
"""

from .retriever import SemanticIndex, SemanticMatch, SemanticChunk

__all__ = ["SemanticIndex", "SemanticMatch", "SemanticChunk"]