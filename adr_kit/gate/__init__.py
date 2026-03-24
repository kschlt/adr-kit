"""Gate package — shim for backward compatibility."""

from adr_kit.decision.gate.models import (
    CategoryRule,
    GateConfig,
    GateDecision,
    NameMapping,
)
from adr_kit.decision.gate.policy_engine import PolicyConfig, PolicyEngine
from adr_kit.decision.gate.policy_gate import GateResult, PolicyGate
from adr_kit.decision.gate.technical_choice import (
    ChoiceType,
    DependencyChoice,
    FrameworkChoice,
    TechnicalChoice,
    create_technical_choice,
)

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
    "NameMapping",
]
