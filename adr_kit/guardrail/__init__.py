"""Guardrail package — shim for backward compatibility."""

from adr_kit.enforcement.config.manager import GuardrailManager
from adr_kit.enforcement.config.models import (
    ApplyResult,
    ConfigTemplate,
    FragmentTarget,
    FragmentType,
    GuardrailConfig,
)
from adr_kit.enforcement.config.monitor import ChangeEvent, ChangeType, FileMonitor
from adr_kit.enforcement.config.writer import (
    ConfigFragment,
    ConfigWriter,
    SentinelBlock,
)

__all__ = [
    "GuardrailManager",
    "ConfigWriter",
    "ConfigFragment",
    "SentinelBlock",
    "FileMonitor",
    "ChangeEvent",
    "ChangeType",
    "GuardrailConfig",
    "FragmentTarget",
    "ApplyResult",
    "ConfigTemplate",
    "FragmentType",
]
