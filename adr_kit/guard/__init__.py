"""Guard package — shim for backward compatibility."""

from adr_kit.enforcement.detection.detector import (
    CodeAnalysisResult,
    GuardSystem,
    PolicyViolation,
)

__all__ = ["GuardSystem", "PolicyViolation", "CodeAnalysisResult"]
