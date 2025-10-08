"""ADR Kit - A toolkit for managing Architectural Decision Records (ADRs) in MADR format."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("adr-kit")
except importlib.metadata.PackageNotFoundError:
    # Fallback for development/editable installs
    __version__ = "0.0.0.dev"

from .core.model import ADR, ADRFrontMatter
from .core.parse import parse_adr_file, parse_front_matter
from .core.validate import ValidationResult, validate_adr

__all__ = [
    "ADR",
    "ADRFrontMatter",
    "parse_adr_file",
    "parse_front_matter",
    "validate_adr",
    "ValidationResult",
]
