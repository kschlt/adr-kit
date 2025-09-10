"""Automatic Guardrail Management System.

This module implements automatic application of configuration fragments
when ADR policies change, providing the "Guardrail Manager" component
from the architectural vision.
"""

from .config_writer import ConfigFragment, ConfigWriter, SentinelBlock
from .file_monitor import ChangeEvent, ChangeType, FileMonitor
from .manager import GuardrailManager
from .models import (
    ApplyResult,
    ConfigTemplate,
    FragmentTarget,
    FragmentType,
    GuardrailConfig,
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
