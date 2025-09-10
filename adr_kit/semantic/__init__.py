"""Semantic retrieval system for ADRs.

This package provides semantic search capabilities using local embeddings
and vector similarity matching for intelligent ADR discovery.
"""

from .retriever import SemanticChunk, SemanticIndex, SemanticMatch

__all__ = ["SemanticIndex", "SemanticMatch", "SemanticChunk"]
