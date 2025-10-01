"""Hash-based caching system for constraints contracts.

This module provides efficient caching of the constraints contract based on
content hashes, avoiding expensive rebuilds when ADRs haven't changed.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.parse import find_adr_files
from .models import ConstraintsContract


class ContractCache:
    """Manages caching of constraints contracts based on ADR content hashes."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = cache_dir / "contract_cache.json"
        self.contract_file = cache_dir / "constraints_accepted.json"

    def get_cached_contract(self, adr_dir: Path) -> ConstraintsContract | None:
        """Get cached contract if it's still valid, None otherwise."""
        if not self.cache_file.exists() or not self.contract_file.exists():
            return None

        try:
            # Load cache metadata
            with open(self.cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)

            # Calculate current ADR content hash
            current_hash = self._calculate_adr_content_hash(adr_dir)

            # Check if cache is still valid
            if cache_data.get("adr_content_hash") == current_hash:
                # Load and return cached contract
                return ConstraintsContract.from_json_file(self.contract_file)

            return None

        except Exception:
            # If anything goes wrong, invalidate cache
            return None

    def save_contract(self, contract: ConstraintsContract, adr_dir: Path) -> None:
        """Save contract to cache with current ADR content hash."""
        try:
            # Calculate ADR content hash for cache validation
            adr_content_hash = self._calculate_adr_content_hash(adr_dir)

            # Save contract to file
            contract.to_json_file(self.contract_file)

            # Save cache metadata
            cache_data = {
                "adr_content_hash": adr_content_hash,
                "contract_hash": contract.metadata.hash,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "adr_directory": str(adr_dir),
                "source_adrs": contract.metadata.source_adrs,
            }

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, sort_keys=True)

        except Exception as e:
            # If caching fails, don't crash - just log and continue
            print(f"Warning: Failed to save contract cache: {e}")

    def invalidate(self) -> None:
        """Invalidate the cache by removing cache files."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
            if self.contract_file.exists():
                self.contract_file.unlink()
        except Exception:
            pass  # Best effort cleanup

    def _calculate_adr_content_hash(self, adr_dir: Path) -> str:
        """Calculate hash of all ADR file contents for cache validation."""
        try:
            adr_files = find_adr_files(adr_dir)
            file_hashes = []

            for file_path in sorted(adr_files):  # Sort for deterministic ordering
                try:
                    # Read file content
                    content = file_path.read_text(encoding="utf-8")
                    # Hash the content
                    file_hash = hashlib.sha256(content.encode()).hexdigest()
                    file_hashes.append(f"{file_path.name}:{file_hash}")
                except Exception:
                    # Skip files that can't be read
                    continue

            # Hash all file hashes together
            combined = "|".join(file_hashes)
            return hashlib.sha256(combined.encode()).hexdigest()

        except Exception:
            # If we can't calculate hash, return empty string to force rebuild
            return ""

    def get_cache_info(self) -> dict[str, Any]:
        """Get information about the current cache state."""
        if not self.cache_file.exists():
            return {
                "cached": False,
                "cache_file_exists": False,
                "contract_file_exists": self.contract_file.exists(),
            }

        try:
            with open(self.cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)

            return {
                "cached": True,
                "cache_file_exists": True,
                "contract_file_exists": self.contract_file.exists(),
                "cached_at": cache_data.get("cached_at"),
                "adr_content_hash": cache_data.get("adr_content_hash"),
                "contract_hash": cache_data.get("contract_hash"),
                "source_adrs": cache_data.get("source_adrs", []),
                "adr_directory": cache_data.get("adr_directory"),
            }

        except Exception:
            return {
                "cached": False,
                "cache_file_exists": True,
                "contract_file_exists": self.contract_file.exists(),
                "error": "Failed to read cache metadata",
            }
