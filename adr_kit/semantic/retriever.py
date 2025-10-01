"""Semantic retrieval system for ADRs using local embeddings.

Design decisions:
- Use sentence-transformers for local embedding generation
- Store embeddings in .project-index/adr-vectors/ directory
- JSONL format for chunks with metadata
- NumPy format for embeddings matrix
- Cosine similarity for semantic matching
- BM25 pre-filtering for performance (optional)
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jsonlines
import numpy as np
from numpy.typing import NDArray

from ..core.model import ADR
from ..core.parse import ParseError, find_adr_files, parse_adr_file

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@dataclass
class SemanticChunk:
    """Represents a semantic chunk from an ADR."""

    chunk_id: str  # Unique identifier for this chunk
    adr_id: str  # ADR this chunk belongs to
    content: str  # The actual text content
    chunk_type: str  # Type: title, section, content
    section_name: str | None = None  # Section name if applicable
    start_pos: int | None = None  # Start position in original text
    end_pos: int | None = None  # End position in original text


@dataclass
class SemanticMatch:
    """Represents a semantic search match."""

    adr_id: str
    title: str
    status: str
    score: float
    chunks: list[SemanticChunk]
    excerpt: str
    related_adrs: list[str] | None = None
    policy_flags: list[str] | None = None


class SemanticChunker:
    """Splits ADR content into semantic chunks for embedding."""

    def __init__(self) -> None:
        self.max_chunk_size = 300  # Maximum characters per chunk
        self.overlap_size = 50  # Overlap between chunks
        self.section_headers = [
            "context",
            "decision",
            "consequences",
            "alternatives",
            "status",
            "background",
            "rationale",
            "implementation",
        ]

    def chunk_adr(self, adr: ADR) -> list[SemanticChunk]:
        """Split an ADR into semantic chunks.

        Args:
            adr: The ADR to chunk

        Returns:
            List of SemanticChunk objects
        """
        chunks = []
        chunk_counter = 0

        # Chunk 1: Title (always important)
        chunks.append(
            SemanticChunk(
                chunk_id=f"{adr.front_matter.id}-title-{chunk_counter}",
                adr_id=adr.front_matter.id,
                content=adr.front_matter.title,
                chunk_type="title",
            )
        )
        chunk_counter += 1

        # Chunk 2: Policy summary (if present)
        if adr.front_matter.policy:
            policy_summary = self._extract_policy_summary(adr.front_matter.policy)
            if policy_summary:
                chunks.append(
                    SemanticChunk(
                        chunk_id=f"{adr.front_matter.id}-policy-{chunk_counter}",
                        adr_id=adr.front_matter.id,
                        content=policy_summary,
                        chunk_type="policy",
                    )
                )
                chunk_counter += 1

        # Chunk 3+: Content sections
        content_chunks = self._chunk_content_by_sections(
            adr.content, adr.front_matter.id, chunk_counter
        )
        chunks.extend(content_chunks)

        return chunks

    def _extract_policy_summary(self, policy: Any) -> str | None:
        """Extract a text summary from structured policy."""
        parts = []

        if policy.imports:
            if policy.imports.prefer:
                parts.append(f"Prefers: {', '.join(policy.imports.prefer)}")
            if policy.imports.disallow:
                parts.append(f"Disallows: {', '.join(policy.imports.disallow)}")

        if policy.rationales:
            parts.append(f"Rationale: {', '.join(policy.rationales)}")

        return "; ".join(parts) if parts else None

    def _chunk_content_by_sections(
        self, content: str, adr_id: str, start_counter: int
    ) -> list[SemanticChunk]:
        """Split content into chunks, respecting section boundaries."""
        chunks = []
        chunk_counter = start_counter

        # Split by markdown headers
        sections = self._split_by_headers(content)

        for section_name, section_content in sections:
            if not section_content.strip():
                continue

            # If section is small enough, keep as single chunk
            if len(section_content) <= self.max_chunk_size:
                chunks.append(
                    SemanticChunk(
                        chunk_id=f"{adr_id}-{section_name or 'content'}-{chunk_counter}",
                        adr_id=adr_id,
                        content=section_content.strip(),
                        chunk_type="section",
                        section_name=section_name,
                    )
                )
                chunk_counter += 1
            else:
                # Split large sections into overlapping chunks
                section_chunks = self._split_with_overlap(
                    section_content, adr_id, section_name or "content", chunk_counter
                )
                chunks.extend(section_chunks)
                chunk_counter += len(section_chunks)

        return chunks

    def _split_by_headers(self, content: str) -> list[tuple[str | None, str]]:
        """Split content by markdown headers."""
        lines = content.split("\n")
        sections: list[tuple[str | None, str]] = []
        current_section: str | None = None
        current_content: list[str] = []

        for line in lines:
            # Check for markdown header
            if line.startswith("#"):
                # Save previous section
                if current_content:
                    sections.append((current_section, "\n".join(current_content)))

                # Start new section
                current_section = line.strip("# ").lower()
                current_content = []
            else:
                current_content.append(line)

        # Save final section
        if current_content:
            sections.append((current_section, "\n".join(current_content)))

        return sections

    def _split_with_overlap(
        self, text: str, adr_id: str, section_name: str, start_counter: int
    ) -> list[SemanticChunk]:
        """Split text into overlapping chunks."""
        chunks = []
        chunk_counter = start_counter

        words = text.split()
        start_idx = 0

        while start_idx < len(words):
            # Calculate end index for this chunk
            end_idx = min(start_idx + self._words_per_chunk(), len(words))

            # Extract chunk text
            chunk_text = " ".join(words[start_idx:end_idx])

            chunks.append(
                SemanticChunk(
                    chunk_id=f"{adr_id}-{section_name}-{chunk_counter}",
                    adr_id=adr_id,
                    content=chunk_text.strip(),
                    chunk_type="content",
                    section_name=section_name,
                )
            )

            chunk_counter += 1

            # Move start index with overlap
            overlap_words = min(self.overlap_size // 5, 10)  # Rough word count
            start_idx = end_idx - overlap_words

            if start_idx >= len(words) - overlap_words:
                break

        return chunks

    def _words_per_chunk(self) -> int:
        """Estimate words per chunk based on character limit."""
        return self.max_chunk_size // 5  # Rough average of 5 chars per word


class SemanticIndex:
    """Local semantic index for ADRs using sentence-transformers."""

    def __init__(self, project_root: Path | None = None):
        """Initialize semantic index.

        Args:
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        self.vectors_dir = self.project_root / ".project-index" / "adr-vectors"
        self.vectors_dir.mkdir(parents=True, exist_ok=True)

        # Storage files
        self.chunks_file = self.vectors_dir / "chunks.jsonl"
        self.embeddings_file = self.vectors_dir / "embeddings.npz"
        self.meta_file = self.vectors_dir / "meta.idx.json"

        # Configuration
        self.model_name = "all-MiniLM-L6-v2"  # Lightweight, good performance
        self.embedding_dim = 384  # Dimension for all-MiniLM-L6-v2

        # Initialize components
        self.chunker = SemanticChunker()
        self._model: SentenceTransformer | None = None
        self._embeddings: NDArray[Any] | None = None
        self._chunks: list[SemanticChunk] = []
        self._meta: dict[str, Any] = {}

    @property
    def model(self) -> "SentenceTransformer":
        """Lazy load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required for semantic search. "
                    "Install with: pip install sentence-transformers"
                ) from e
        return self._model

    def build_index(
        self, adr_dir: str = "docs/adr", force_rebuild: bool = False
    ) -> dict[str, Any]:
        """Build or update the semantic index.

        Args:
            adr_dir: Directory containing ADR files
            force_rebuild: Whether to force a complete rebuild

        Returns:
            Dictionary with indexing statistics
        """
        print("🔍 Building semantic index...")

        # Load existing index if available and not forcing rebuild
        if not force_rebuild and self._load_existing_index():
            print("📥 Loaded existing semantic index")

        # Find all ADR files
        adr_files = find_adr_files(Path(adr_dir))

        # Track what needs to be indexed
        new_chunks = []
        processed_adrs = set()

        for file_path in adr_files:
            try:
                adr = parse_adr_file(file_path, strict=False)
                if not adr:
                    continue

                # Skip if already indexed (unless force rebuild)
                if not force_rebuild and adr.front_matter.id in self._meta.get(
                    "adr_to_chunks", {}
                ):
                    processed_adrs.add(adr.front_matter.id)
                    continue

                # Chunk the ADR
                chunks = self.chunker.chunk_adr(adr)
                new_chunks.extend(chunks)
                processed_adrs.add(adr.front_matter.id)

            except ParseError:
                continue

        if not new_chunks and not force_rebuild:
            print("✅ Index is up to date")
            return {
                "total_chunks": len(self._chunks),
                "total_adrs": len(processed_adrs),
                "new_chunks": 0,
                "status": "up_to_date",
            }

        if force_rebuild:
            print("🔄 Force rebuilding entire index...")
            self._chunks = new_chunks
        else:
            print(f"📝 Adding {len(new_chunks)} new chunks...")
            self._chunks.extend(new_chunks)

        # Generate embeddings for new chunks
        if new_chunks:
            new_embeddings = self._generate_embeddings(
                [chunk.content for chunk in new_chunks]
            )

            if self._embeddings is not None and not force_rebuild:
                # Append to existing embeddings
                self._embeddings = np.vstack([self._embeddings, new_embeddings])
            else:
                # Create new embeddings matrix
                if force_rebuild and self._chunks:
                    all_texts = [chunk.content for chunk in self._chunks]
                    self._embeddings = self._generate_embeddings(all_texts)
                else:
                    self._embeddings = new_embeddings

        # Update metadata
        self._update_metadata()

        # Save index
        self._save_index()

        print(
            f"✅ Semantic index built: {len(self._chunks)} chunks, {len(processed_adrs)} ADRs"
        )

        return {
            "total_chunks": len(self._chunks),
            "total_adrs": len(processed_adrs),
            "new_chunks": len(new_chunks),
            "embedding_dim": self.embedding_dim,
            "model": self.model_name,
            "status": "updated",
        }

    def _generate_embeddings(self, texts: list[str]) -> NDArray[Any]:
        """Generate embeddings for a list of texts."""
        print(f"🧠 Generating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        return embeddings.astype(np.float32)

    def _load_existing_index(self) -> bool:
        """Load existing index from disk."""
        try:
            # Load chunks
            if self.chunks_file.exists():
                self._chunks = []
                with jsonlines.open(self.chunks_file) as reader:
                    for obj in reader:
                        self._chunks.append(SemanticChunk(**obj))

            # Load embeddings
            if self.embeddings_file.exists():
                data = np.load(self.embeddings_file)
                self._embeddings = data["embeddings"]

            # Load metadata
            if self.meta_file.exists():
                with open(self.meta_file) as f:
                    self._meta = json.load(f)

            return len(self._chunks) > 0 and self._embeddings is not None

        except Exception as e:
            print(f"⚠️ Could not load existing index: {e}")
            return False

    def _update_metadata(self) -> None:
        """Update metadata mappings."""
        chunk_to_row: dict[str, int] = {}
        adr_to_chunks: dict[str, list[str]] = {}

        for i, chunk in enumerate(self._chunks):
            chunk_to_row[chunk.chunk_id] = i

            if chunk.adr_id not in adr_to_chunks:
                adr_to_chunks[chunk.adr_id] = []
            adr_to_chunks[chunk.adr_id].append(chunk.chunk_id)

        self._meta = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "model": self.model_name,
            "embedding_dim": self.embedding_dim,
            "total_chunks": len(self._chunks),
            "chunk_to_row": chunk_to_row,
            "adr_to_chunks": adr_to_chunks,
        }

    def _save_index(self) -> None:
        """Save index to disk."""
        print("💾 Saving semantic index...")

        # Save chunks as JSONL
        with jsonlines.open(self.chunks_file, mode="w") as writer:
            for chunk in self._chunks:
                writer.write(
                    {
                        "chunk_id": chunk.chunk_id,
                        "adr_id": chunk.adr_id,
                        "content": chunk.content,
                        "chunk_type": chunk.chunk_type,
                        "section_name": chunk.section_name,
                    }
                )

        # Save embeddings as NPZ
        if self._embeddings is not None:
            np.savez_compressed(self.embeddings_file, embeddings=self._embeddings)

        # Save metadata as JSON
        with open(self.meta_file, "w") as f:
            json.dump(self._meta, f, indent=2)

    def search(
        self, query: str, k: int = 5, filter_status: set[str] | None = None
    ) -> list[SemanticMatch]:
        """Perform semantic search on the ADR index.

        Args:
            query: Search query text
            k: Number of results to return
            filter_status: Optional set of ADR statuses to filter by

        Returns:
            List of SemanticMatch objects
        """
        if not self._chunks or self._embeddings is None:
            return []

        # Generate query embedding
        query_embedding = self.model.encode([query]).astype(np.float32)

        # Compute cosine similarities
        similarities = np.dot(self._embeddings, query_embedding.T).flatten()
        similarities = similarities / (
            np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top-k similar chunks
        top_indices = np.argsort(similarities)[::-1][: k * 3]  # Get more for filtering

        # Group by ADR and aggregate scores
        adr_scores: dict[str, list[float]] = {}
        adr_chunks: dict[str, list[SemanticChunk]] = {}

        for idx in top_indices:
            chunk = self._chunks[idx]
            score = similarities[idx]

            if chunk.adr_id not in adr_scores:
                adr_scores[chunk.adr_id] = []
                adr_chunks[chunk.adr_id] = []

            adr_scores[chunk.adr_id].append(float(score))
            adr_chunks[chunk.adr_id].append(chunk)

        # Create matches
        matches = []
        for adr_id in adr_scores:
            # Calculate aggregate score (max of chunk scores)
            aggregate_score = max(adr_scores[adr_id])

            # Get best chunks for this ADR
            chunks = adr_chunks[adr_id][:2]  # Top 2 chunks per ADR

            # Create excerpt from best chunk
            best_chunk = chunks[0] if chunks else None
            excerpt = (
                best_chunk.content[:200] + "..."
                if best_chunk and len(best_chunk.content) > 200
                else best_chunk.content if best_chunk else ""
            )

            matches.append(
                SemanticMatch(
                    adr_id=adr_id,
                    title=self._get_adr_title(adr_id, chunks),
                    status=self._get_adr_status(adr_id),
                    score=float(aggregate_score),
                    chunks=chunks,
                    excerpt=excerpt,
                )
            )

        # Sort by score and return top-k
        matches.sort(key=lambda x: x.score, reverse=True)

        # Apply status filter if provided
        if filter_status:
            matches = [m for m in matches if m.status in filter_status]

        return matches[:k]

    def _get_adr_title(self, adr_id: str, chunks: list[SemanticChunk]) -> str:
        """Extract ADR title from chunks."""
        for chunk in chunks:
            if chunk.chunk_type == "title":
                return chunk.content
        return adr_id  # Fallback

    def _get_adr_status(self, adr_id: str) -> str:
        """Get ADR status (this is a simplified version)."""
        # In a full implementation, this would query the actual ADR
        # For now, return a default
        return "unknown"
