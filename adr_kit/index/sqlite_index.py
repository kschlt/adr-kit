"""SQLite index generation for ADRs.

Design decisions:
- Use SQLite for queryable ADR catalog with relational data
- Store ADR metadata in structured tables for complex queries
- Support ADR relationship tracking (supersedes/superseded_by)
- Enable full-text search on ADR content
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..core.model import ADR, ADRStatus
from ..core.parse import ParseError, find_adr_files, parse_adr_file
from ..core.validate import validate_adr_file


class ADRSQLiteIndex:
    """SQLite index generator for ADRs."""

    def __init__(self, db_path: Path | str = ".project-index/catalog.db"):
        self.db_path = Path(db_path)
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Connect to SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row  # Enable dict-like access
        self._create_tables()

    def disconnect(self) -> None:
        """Disconnect from SQLite database."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def _create_tables(self) -> None:
        """Create database tables for ADR indexing."""
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()

        # Main ADRs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS adrs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                date TEXT NOT NULL,
                file_path TEXT,
                content TEXT,
                content_preview TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # ADR deciders (many-to-many relationship)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS adr_deciders (
                adr_id TEXT,
                decider TEXT,
                PRIMARY KEY (adr_id, decider),
                FOREIGN KEY (adr_id) REFERENCES adrs (id) ON DELETE CASCADE
            )
        """
        )

        # ADR tags (many-to-many relationship)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS adr_tags (
                adr_id TEXT,
                tag TEXT,
                PRIMARY KEY (adr_id, tag),
                FOREIGN KEY (adr_id) REFERENCES adrs (id) ON DELETE CASCADE
            )
        """
        )

        # ADR relationships (supersedes/superseded_by)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS adr_links (
                from_adr_id TEXT,
                to_adr_id TEXT,
                link_type TEXT, -- 'supersedes' or 'superseded_by'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (from_adr_id, to_adr_id, link_type),
                FOREIGN KEY (from_adr_id) REFERENCES adrs (id) ON DELETE CASCADE,
                FOREIGN KEY (to_adr_id) REFERENCES adrs (id) ON DELETE CASCADE
            )
        """
        )

        # Index metadata
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_adrs_status ON adrs (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_adrs_date ON adrs (date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_adr_tags_tag ON adr_tags (tag)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_adr_links_from ON adr_links (from_adr_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_adr_links_to ON adr_links (to_adr_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_adr_links_type ON adr_links (link_type)"
        )

        # Create full-text search table
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS adr_fts USING fts5(
                id,
                title,
                content,
                content='adrs',
                content_rowid='rowid'
            )
        """
        )

        # Create triggers to keep FTS table in sync
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS adr_fts_insert AFTER INSERT ON adrs BEGIN
                INSERT INTO adr_fts(id, title, content) VALUES (new.id, new.title, new.content);
            END
        """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS adr_fts_update AFTER UPDATE ON adrs BEGIN
                UPDATE adr_fts SET title=new.title, content=new.content WHERE id=new.id;
            END
        """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS adr_fts_delete AFTER DELETE ON adrs BEGIN
                DELETE FROM adr_fts WHERE id=old.id;
            END
        """
        )

        self.connection.commit()

    def clear_index(self) -> None:
        """Clear all ADR data from the index."""
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM adr_links")
        cursor.execute("DELETE FROM adr_tags")
        cursor.execute("DELETE FROM adr_deciders")
        cursor.execute("DELETE FROM adrs")
        cursor.execute("DELETE FROM adr_fts")
        self.connection.commit()

    def index_adr(self, adr: ADR) -> None:
        """Add or update a single ADR in the index.

        Args:
            adr: The ADR to index
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()

        # Convert date to string
        date_str = (
            adr.front_matter.date.isoformat()
            if isinstance(adr.front_matter.date, date)
            else str(adr.front_matter.date)
        )
        status_str = (
            adr.front_matter.status.value
            if isinstance(adr.front_matter.status, ADRStatus)
            else str(adr.front_matter.status)
        )

        # Generate content preview
        content_preview = self._generate_content_preview(adr.content)

        # Insert or update ADR record
        cursor.execute(
            """
            INSERT OR REPLACE INTO adrs
            (id, title, status, date, file_path, content, content_preview, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                adr.front_matter.id,
                adr.front_matter.title,
                status_str,
                date_str,
                str(adr.file_path) if adr.file_path else None,
                adr.content,
                content_preview,
                datetime.now().isoformat(),
            ),
        )

        # Clear existing relationships for this ADR
        cursor.execute(
            "DELETE FROM adr_deciders WHERE adr_id = ?", (adr.front_matter.id,)
        )
        cursor.execute("DELETE FROM adr_tags WHERE adr_id = ?", (adr.front_matter.id,))
        cursor.execute(
            "DELETE FROM adr_links WHERE from_adr_id = ?", (adr.front_matter.id,)
        )

        # Insert deciders
        if adr.front_matter.deciders:
            for decider in adr.front_matter.deciders:
                cursor.execute(
                    "INSERT INTO adr_deciders (adr_id, decider) VALUES (?, ?)",
                    (adr.front_matter.id, decider),
                )

        # Insert tags
        if adr.front_matter.tags:
            for tag in adr.front_matter.tags:
                cursor.execute(
                    "INSERT INTO adr_tags (adr_id, tag) VALUES (?, ?)",
                    (adr.front_matter.id, tag),
                )

        # Insert supersedes relationships
        if adr.front_matter.supersedes:
            for superseded_id in adr.front_matter.supersedes:
                cursor.execute(
                    "INSERT INTO adr_links (from_adr_id, to_adr_id, link_type) VALUES (?, ?, ?)",
                    (adr.front_matter.id, superseded_id, "supersedes"),
                )

        # Insert superseded_by relationships
        if adr.front_matter.superseded_by:
            for superseding_id in adr.front_matter.superseded_by:
                cursor.execute(
                    "INSERT INTO adr_links (from_adr_id, to_adr_id, link_type) VALUES (?, ?, ?)",
                    (adr.front_matter.id, superseding_id, "superseded_by"),
                )

        self.connection.commit()

    def _generate_content_preview(self, content: str, max_length: int = 200) -> str:
        """Generate a preview of ADR content."""
        lines = content.split("\n")
        content_lines = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                content_lines.append(line)
                if len(" ".join(content_lines)) > max_length:
                    break

        preview = " ".join(content_lines)
        if len(preview) > max_length:
            preview = preview[:max_length].rsplit(" ", 1)[0] + "..."

        return preview

    def build_index(
        self, adr_directory: Path | str = "docs/adr", validate: bool = True
    ) -> dict[str, Any]:
        """Build the complete ADR index.

        Args:
            adr_directory: Directory containing ADR files
            validate: If True, validate ADRs before indexing

        Returns:
            Dictionary with indexing statistics
        """
        if not self.connection:
            self.connect()

        self.clear_index()

        adr_files = find_adr_files(adr_directory)
        stats: dict[str, Any] = {
            "total_files": len(adr_files),
            "indexed": 0,
            "errors": [],
        }

        for file_path in adr_files:
            try:
                if validate:
                    result = validate_adr_file(file_path)
                    if not result.is_valid:
                        stats["errors"].append(
                            {
                                "file": str(file_path),
                                "errors": [str(issue) for issue in result.errors],
                            }
                        )
                        continue
                    adr = result.adr
                else:
                    adr = parse_adr_file(file_path, strict=False)

                if adr:
                    self.index_adr(adr)
                    stats["indexed"] += 1

            except (ParseError, Exception) as e:
                stats["errors"].append({"file": str(file_path), "errors": [str(e)]})

        # Update index metadata
        self._update_metadata(stats, adr_directory)

        return stats

    def _update_metadata(
        self, stats: dict[str, Any], adr_directory: Path | str
    ) -> None:
        """Update index metadata."""
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()
        metadata = [
            ("generated_at", datetime.now().isoformat()),
            ("adr_directory", str(adr_directory)),
            ("total_adrs", str(stats["indexed"])),
            ("total_errors", str(len(stats["errors"]))),
        ]

        for key, value in metadata:
            cursor.execute(
                "INSERT OR REPLACE INTO index_metadata (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, datetime.now().isoformat()),
            )

        self.connection.commit()

    def query_adrs(
        self,
        status: str | list[str] | None = None,
        tags: str | list[str] | None = None,
        deciders: str | list[str] | None = None,
        search_text: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query ADRs with filters.

        Args:
            status: Filter by status (single or multiple)
            tags: Filter by tags (single or multiple)
            deciders: Filter by deciders (single or multiple)
            search_text: Full-text search in title/content
            limit: Maximum number of results

        Returns:
            List of ADR records as dictionaries
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()

        # Build query
        base_query = "SELECT DISTINCT a.* FROM adrs a"
        conditions = []
        params = []

        # Join with tags table if needed
        if tags:
            base_query += " JOIN adr_tags at ON a.id = at.adr_id"
            tag_list = [tags] if isinstance(tags, str) else tags
            placeholders = ",".join(["?" for _ in tag_list])
            conditions.append(f"at.tag IN ({placeholders})")
            params.extend(tag_list)

        # Join with deciders table if needed
        if deciders:
            base_query += " JOIN adr_deciders ad ON a.id = ad.adr_id"
            decider_list = [deciders] if isinstance(deciders, str) else deciders
            placeholders = ",".join(["?" for _ in decider_list])
            conditions.append(f"ad.decider IN ({placeholders})")
            params.extend(decider_list)

        # Status filter
        if status:
            status_list = [status] if isinstance(status, str) else status
            placeholders = ",".join(["?" for _ in status_list])
            conditions.append(f"a.status IN ({placeholders})")
            params.extend(status_list)

        # Full-text search
        if search_text:
            base_query += " JOIN adr_fts fts ON a.id = fts.id"
            conditions.append("adr_fts MATCH ?")
            params.append(search_text)

        # Add WHERE clause
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        # Add ordering and limit
        base_query += " ORDER BY a.id"
        if limit:
            base_query += f" LIMIT {limit}"

        cursor.execute(base_query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_adr_relationships(self, adr_id: str) -> dict[str, list[str]]:
        """Get ADR relationships (supersedes/superseded_by).

        Args:
            adr_id: The ADR ID to get relationships for

        Returns:
            Dictionary with 'supersedes' and 'superseded_by' lists
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()

        # Get supersedes relationships
        cursor.execute(
            "SELECT to_adr_id FROM adr_links WHERE from_adr_id = ? AND link_type = 'supersedes'",
            (adr_id,),
        )
        supersedes = [row[0] for row in cursor.fetchall()]

        # Get superseded_by relationships
        cursor.execute(
            "SELECT to_adr_id FROM adr_links WHERE from_adr_id = ? AND link_type = 'superseded_by'",
            (adr_id,),
        )
        superseded_by = [row[0] for row in cursor.fetchall()]

        return {"supersedes": supersedes, "superseded_by": superseded_by}

    def get_statistics(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Dictionary with various statistics about the index
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = self.connection.cursor()

        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM adrs")
        total_adrs = cursor.fetchone()[0]

        # Status distribution
        cursor.execute("SELECT status, COUNT(*) FROM adrs GROUP BY status")
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Tag distribution
        cursor.execute(
            "SELECT tag, COUNT(*) FROM adr_tags GROUP BY tag ORDER BY COUNT(*) DESC LIMIT 10"
        )
        top_tags = {row[0]: row[1] for row in cursor.fetchall()}

        # Get metadata
        cursor.execute("SELECT key, value FROM index_metadata")
        metadata = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_adrs": total_adrs,
            "status_counts": status_counts,
            "top_tags": top_tags,
            "metadata": metadata,
        }


def generate_sqlite_index(
    adr_directory: Path | str = "docs/adr",
    db_path: Path | str = ".project-index/catalog.db",
    validate: bool = True,
) -> dict[str, Any]:
    """Generate SQLite ADR index.

    Args:
        adr_directory: Directory containing ADR files
        db_path: Path to SQLite database file
        validate: If True, validate ADRs before indexing

    Returns:
        Dictionary with indexing statistics
    """
    index = ADRSQLiteIndex(db_path)
    try:
        index.connect()
        return index.build_index(adr_directory, validate=validate)
    finally:
        index.disconnect()
