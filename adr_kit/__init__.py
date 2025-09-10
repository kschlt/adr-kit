"""ADR Kit - A toolkit for managing Architectural Decision Records (ADRs) in MADR format."""

__version__ = "0.2.2"

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
