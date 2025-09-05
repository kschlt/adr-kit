"""Preflight policy gate system for ADR-Kit.

The gate system provides proactive architectural control by intercepting major
technical choices BEFORE they're implemented. This ensures agents pause for
human approval when architectural decisions are needed.

Key components:
- PolicyGate: Main gate engine that evaluates technical choices
- TechnicalChoice: Models for representing decisions that need evaluation
- GateDecision: Result types (ALLOWED, REQUIRES_ADR, BLOCKED, CONFLICT)
- PolicyEngine: Rule evaluation engine with allow/deny lists and defaults
"""

from .policy_gate import PolicyGate, GateResult
from .technical_choice import TechnicalChoice, ChoiceType, DependencyChoice, FrameworkChoice, create_technical_choice
from .policy_engine import PolicyEngine, PolicyConfig
from .models import GateConfig, CategoryRule, NameMapping, GateDecision

__all__ = [
    "PolicyGate",
    "GateDecision", 
    "GateResult",
    "TechnicalChoice",
    "ChoiceType",
    "DependencyChoice",
    "FrameworkChoice",
    "create_technical_choice", 
    "PolicyEngine",
    "PolicyConfig",
    "GateConfig",
    "CategoryRule",
    "NameMapping"
]