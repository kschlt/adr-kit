"""Automatic Guardrail Management System.

This module implements automatic application of configuration fragments
when ADR policies change, providing the "Guardrail Manager" component
from the architectural vision.
"""

from .manager import GuardrailManager
from .config_writer import ConfigWriter, ConfigFragment, SentinelBlock
from .file_monitor import FileMonitor, ChangeEvent, ChangeType
from .models import (
    GuardrailConfig,
    FragmentTarget,
    ApplyResult,
    ConfigTemplate,
    FragmentType,
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
