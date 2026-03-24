# RST — Module Restructure by Plane

## Context

Restructure `adr_kit/` into the three-plane architecture defined in `.agent/architecture.md`. Pure mechanical work — move files, update imports, no logic changes. Uses backward-compatible shims so tests pass at every intermediate step.

**Strategy**: Move files → create shims at old locations → verify tests pass → update source imports → update test imports → remove shims → final verify.

---

## Phase 0: Branch + Green Baseline

1. Invoke `/branch` with args: `"RST Module Restructure by Plane — architecture realignment"`
2. Run `make test-all && make lint` — must pass. If not, stop.

---

## Phase 1: Create New Directory Structure

Create directories and empty `__init__.py` files:

```bash
mkdir -p adr_kit/decision/workflows
mkdir -p adr_kit/decision/guidance
mkdir -p adr_kit/decision/gate
mkdir -p adr_kit/enforcement/adapters
mkdir -p adr_kit/enforcement/validation
mkdir -p adr_kit/enforcement/generation
mkdir -p adr_kit/enforcement/config
mkdir -p adr_kit/enforcement/detection
```

Create empty `__init__.py` in each new directory:
- `adr_kit/decision/__init__.py`
- `adr_kit/decision/workflows/__init__.py`
- `adr_kit/decision/guidance/__init__.py`
- `adr_kit/enforcement/__init__.py`
- `adr_kit/enforcement/adapters/__init__.py`
- `adr_kit/enforcement/validation/__init__.py`
- `adr_kit/enforcement/generation/__init__.py`
- `adr_kit/enforcement/config/__init__.py`

(gate/ and detection/ `__init__.py` come from `git mv` in Phase 2)

---

## Phase 2: Move Files with `git mv`

### Decision Plane — workflows
```
git mv adr_kit/workflows/base.py          adr_kit/decision/workflows/base.py
git mv adr_kit/workflows/creation.py      adr_kit/decision/workflows/creation.py
git mv adr_kit/workflows/approval.py      adr_kit/decision/workflows/approval.py
git mv adr_kit/workflows/supersede.py     adr_kit/decision/workflows/supersede.py
git mv adr_kit/workflows/preflight.py     adr_kit/decision/workflows/preflight.py
git mv adr_kit/workflows/analyze.py       adr_kit/decision/workflows/analyze.py
```

### Decision Plane — guidance
```
git mv adr_kit/workflows/decision_guidance.py  adr_kit/decision/guidance/decision_guidance.py
```

### Decision Plane — gate (entire package)
```
git mv adr_kit/gate/__init__.py         adr_kit/decision/gate/__init__.py
git mv adr_kit/gate/models.py           adr_kit/decision/gate/models.py
git mv adr_kit/gate/policy_engine.py    adr_kit/decision/gate/policy_engine.py
git mv adr_kit/gate/policy_gate.py      adr_kit/decision/gate/policy_gate.py
git mv adr_kit/gate/technical_choice.py adr_kit/decision/gate/technical_choice.py
```

### Enforcement Plane — adapters
```
git mv adr_kit/enforce/eslint.py  adr_kit/enforcement/adapters/eslint.py
git mv adr_kit/enforce/ruff.py    adr_kit/enforcement/adapters/ruff.py
```

### Enforcement Plane — validation
```
git mv adr_kit/enforce/validator.py  adr_kit/enforcement/validation/staged.py    # RENAMED
git mv adr_kit/enforce/stages.py     adr_kit/enforcement/validation/stages.py
```

### Enforcement Plane — reporter
```
git mv adr_kit/enforce/reporter.py  adr_kit/enforcement/reporter.py
```

### Enforcement Plane — generation
```
git mv adr_kit/enforce/script_generator.py  adr_kit/enforcement/generation/scripts.py  # RENAMED
git mv adr_kit/enforce/ci.py               adr_kit/enforcement/generation/ci.py
git mv adr_kit/enforce/hooks.py            adr_kit/enforcement/generation/hooks.py
```

### Enforcement Plane — config (from guardrail/)
```
git mv adr_kit/guardrail/config_writer.py  adr_kit/enforcement/config/writer.py    # RENAMED
git mv adr_kit/guardrail/file_monitor.py   adr_kit/enforcement/config/monitor.py   # RENAMED
git mv adr_kit/guardrail/manager.py        adr_kit/enforcement/config/manager.py
git mv adr_kit/guardrail/models.py         adr_kit/enforcement/config/models.py
```

### Enforcement Plane — detection (from guard/)
```
git mv adr_kit/guard/__init__.py   adr_kit/enforcement/detection/__init__.py
git mv adr_kit/guard/detector.py   adr_kit/enforcement/detection/detector.py
```

### NOT moved
- `workflows/planning.py` — stays in `workflows/` (context plane, imported by mcp/server.py)
- `workflows/__init__.py` — stays, will be updated
- `knowledge/` — empty (only `__pycache__`), delete in Phase 7

---

## Phase 3: Fix Relative Imports in Moved Files

Each moved file that uses `from ..X` imports needs depth adjusted (`..` → `...`) because it's now one level deeper. Also fix cross-module references for renamed files.

### Decision Plane files

**`adr_kit/decision/workflows/creation.py`** — 4 top-level + 1 lazy:
- `from ..contract.builder` → `from ...contract.builder`
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`
- `from ..core.validate` → `from ...core.validate`
- Line ~555 (lazy): `from ..core.policy_extractor` → `from ...core.policy_extractor`

**`adr_kit/decision/workflows/approval.py`** — 7 top-level + 3 lazy:
- `from ..contract.builder` → `from ...contract.builder`
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`
- `from ..core.validate` → `from ...core.validate`
- `from ..enforce.eslint` → `from ...enforcement.adapters.eslint`
- `from ..enforce.ruff` → `from ...enforcement.adapters.ruff`
- `from ..guardrail.manager` → `from ...enforcement.config.manager`
- `from ..index.json_index` → `from ...index.json_index`
- Line ~287 (lazy): `from ..core.model` → `from ...core.model`
- Line ~383 (lazy): `from ..enforce.script_generator` → `from ...enforcement.generation.scripts`
- Line ~410 (lazy): `from ..enforce.hooks` → `from ...enforcement.generation.hooks`

**`adr_kit/decision/workflows/supersede.py`** — 2 top-level:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`

**`adr_kit/decision/workflows/preflight.py`** — 2 top-level:
- `from ..contract.builder` → `from ...contract.builder`
- `from ..contract.models` → `from ...contract.models`

**`adr_kit/decision/workflows/analyze.py`** — 1 top-level:
- `from ..core.parse` → `from ...core.parse`

**`adr_kit/decision/workflows/base.py`** — no `..` imports. No changes.

**`adr_kit/decision/guidance/decision_guidance.py`** — no `..` imports. No changes.

**`adr_kit/decision/gate/policy_engine.py`** — 1 top-level:
- `from ..contract` → `from ...contract`

### Enforcement Plane files

**`adr_kit/enforcement/adapters/eslint.py`** — 3 top-level:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`
- `from ..core.policy_extractor` → `from ...core.policy_extractor`

**`adr_kit/enforcement/adapters/ruff.py`** — 2 top-level:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`

**`adr_kit/enforcement/validation/staged.py`** (was validator.py) — 2 top-level:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`
- `from .stages import` — stays (sibling)

**`adr_kit/enforcement/validation/stages.py`** — no `..` imports. No changes.

**`adr_kit/enforcement/reporter.py`** — 1 internal:
- `from .validator import ValidationResult` → `from .validation.staged import ValidationResult`

**`adr_kit/enforcement/generation/scripts.py`** (was script_generator.py) — 2 top-level + 1 sibling:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`
- `from .stages import` → `from ..validation.stages import` (stages moved to validation/)

**`adr_kit/enforcement/generation/ci.py`** — no `..` imports. No changes.

**`adr_kit/enforcement/generation/hooks.py`** — no `..` imports. No changes.

**`adr_kit/enforcement/config/manager.py`** — 1 top-level + 2 sibling renames:
- `from ..contract` → `from ...contract`
- `from .config_writer` → `from .writer` (file renamed)
- `from .file_monitor` → `from .monitor` (file renamed)

**`adr_kit/enforcement/config/monitor.py`** (was file_monitor.py) — 2 top-level:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`

**`adr_kit/enforcement/config/writer.py`** (was config_writer.py) — no `..` imports. Only `.models` (stays).

**`adr_kit/enforcement/detection/detector.py`** — 4 top-level:
- `from ..core.model` → `from ...core.model`
- `from ..core.parse` → `from ...core.parse`
- `from ..core.policy_extractor` → `from ...core.policy_extractor`
- `from ..semantic.retriever` → `from ...semantic.retriever`

---

## Phase 4: Create Backward-Compatible Shims at Old Locations

### `adr_kit/workflows/` shims

Create these files (one-liner each):
```
adr_kit/workflows/base.py:               from adr_kit.decision.workflows.base import *  # noqa: F401,F403
adr_kit/workflows/creation.py:           from adr_kit.decision.workflows.creation import *  # noqa: F401,F403
adr_kit/workflows/approval.py:           from adr_kit.decision.workflows.approval import *  # noqa: F401,F403
adr_kit/workflows/supersede.py:          from adr_kit.decision.workflows.supersede import *  # noqa: F401,F403
adr_kit/workflows/preflight.py:          from adr_kit.decision.workflows.preflight import *  # noqa: F401,F403
adr_kit/workflows/analyze.py:            from adr_kit.decision.workflows.analyze import *  # noqa: F401,F403
adr_kit/workflows/decision_guidance.py:  from adr_kit.decision.guidance.decision_guidance import *  # noqa: F401,F403
```

**`adr_kit/workflows/__init__.py`** — replace content with:
```python
"""Workflow orchestration — shim for backward compatibility."""
from .planning import PlanningWorkflow
from adr_kit.decision.workflows.analyze import AnalyzeProjectWorkflow
from adr_kit.decision.workflows.approval import ApprovalWorkflow
from adr_kit.decision.workflows.base import BaseWorkflow, WorkflowError, WorkflowResult, WorkflowStatus
from adr_kit.decision.workflows.creation import CreationWorkflow
from adr_kit.decision.workflows.preflight import PreflightWorkflow
from adr_kit.decision.workflows.supersede import SupersedeWorkflow

__all__ = [
    "BaseWorkflow", "WorkflowResult", "WorkflowError", "WorkflowStatus",
    "ApprovalWorkflow", "CreationWorkflow", "PreflightWorkflow",
    "PlanningWorkflow", "SupersedeWorkflow", "AnalyzeProjectWorkflow",
]
```

**`adr_kit/workflows/planning.py`** — fix broken sibling import:
- `from .base import BaseWorkflow, WorkflowResult` → `from adr_kit.decision.workflows.base import BaseWorkflow, WorkflowResult`

### `adr_kit/gate/` shims

Recreate the directory and files:
```
adr_kit/gate/__init__.py:         (re-export all names from adr_kit.decision.gate — copy the original __all__ list, import each from new location)
adr_kit/gate/models.py:           from adr_kit.decision.gate.models import *  # noqa: F401,F403
adr_kit/gate/policy_engine.py:    from adr_kit.decision.gate.policy_engine import *  # noqa: F401,F403
adr_kit/gate/policy_gate.py:      from adr_kit.decision.gate.policy_gate import *  # noqa: F401,F403
adr_kit/gate/technical_choice.py: from adr_kit.decision.gate.technical_choice import *  # noqa: F401,F403
```

### `adr_kit/enforce/` shims

Replace all files (they were emptied by `git mv`):
```
adr_kit/enforce/__init__.py:          (re-export CIWorkflowGenerator from enforcement.generation.ci, ScriptGenerator from enforcement.generation.scripts)
adr_kit/enforce/eslint.py:            from adr_kit.enforcement.adapters.eslint import *  # noqa: F401,F403
adr_kit/enforce/ruff.py:              from adr_kit.enforcement.adapters.ruff import *  # noqa: F401,F403
adr_kit/enforce/validator.py:         from adr_kit.enforcement.validation.staged import *  # noqa: F401,F403
adr_kit/enforce/stages.py:            from adr_kit.enforcement.validation.stages import *  # noqa: F401,F403
adr_kit/enforce/reporter.py:          from adr_kit.enforcement.reporter import *  # noqa: F401,F403
adr_kit/enforce/script_generator.py:  from adr_kit.enforcement.generation.scripts import *  # noqa: F401,F403
adr_kit/enforce/ci.py:                from adr_kit.enforcement.generation.ci import *  # noqa: F401,F403
adr_kit/enforce/hooks.py:             from adr_kit.enforcement.generation.hooks import *  # noqa: F401,F403
```

### `adr_kit/guardrail/` shims

Replace all files:
```
adr_kit/guardrail/__init__.py:      (re-export all 12 names from enforcement.config.* modules — copy original __all__)
adr_kit/guardrail/config_writer.py: from adr_kit.enforcement.config.writer import *  # noqa: F401,F403
adr_kit/guardrail/file_monitor.py:  from adr_kit.enforcement.config.monitor import *  # noqa: F401,F403
adr_kit/guardrail/manager.py:       from adr_kit.enforcement.config.manager import *  # noqa: F401,F403
adr_kit/guardrail/models.py:        from adr_kit.enforcement.config.models import *  # noqa: F401,F403
```

### `adr_kit/guard/` shims

Recreate:
```
adr_kit/guard/__init__.py:  (re-export GuardSystem, PolicyViolation, CodeAnalysisResult from enforcement.detection)
adr_kit/guard/detector.py:  from adr_kit.enforcement.detection.detector import *  # noqa: F401,F403
```

### Verify: `make test-all && make lint`

All 309+ tests must pass. If not, debug shims before proceeding.

### Commit: `refactor: move files into decision/ and enforcement/ planes with backward-compat shims`

---

## Phase 5: Update Source Imports

### `adr_kit/mcp/server.py` (lines 13-18)

| Old | New |
|-----|-----|
| `from ..workflows.analyze import ...` | `from ..decision.workflows.analyze import ...` |
| `from ..workflows.approval import ...` | `from ..decision.workflows.approval import ...` |
| `from ..workflows.creation import ...` | `from ..decision.workflows.creation import ...` |
| `from ..workflows.planning import ...` | **NO CHANGE** (stays in workflows/) |
| `from ..workflows.preflight import ...` | `from ..decision.workflows.preflight import ...` |
| `from ..workflows.supersede import ...` | `from ..decision.workflows.supersede import ...` |

### `adr_kit/cli.py` (all lazy imports in function bodies)

Find and replace each:
| Old | New |
|-----|-----|
| `from .workflows.analyze import` | `from .decision.workflows.analyze import` |
| `from .workflows.approval import` | `from .decision.workflows.approval import` |
| `from .workflows.creation import` | `from .decision.workflows.creation import` |
| `from .workflows.preflight import` | `from .decision.workflows.preflight import` |
| `from .enforce.hooks import` | `from .enforcement.generation.hooks import` |
| `from .gate import PolicyGate, create_technical_choice` | `from .decision.gate import PolicyGate, create_technical_choice` |
| `from .gate import PolicyGate` | `from .decision.gate import PolicyGate` |
| `from .guardrail import GuardrailManager` | `from .enforcement.config.manager import GuardrailManager` |
| `from .enforce.stages import` | `from .enforcement.validation.stages import` |
| `from .enforce.validator import` | `from .enforcement.validation.staged import` |
| `from .enforce.reporter import` | `from .enforcement.reporter import` |
| `from .enforce.script_generator import` | `from .enforcement.generation.scripts import` |
| `from .enforce.ci import` | `from .enforcement.generation.ci import` |

### Verify: `make test-all && make lint`

### Commit: `refactor: update source imports to new decision/ and enforcement/ paths`

---

## Phase 6: Update Test Imports

### Workflow test imports — replace `adr_kit.workflows.X` → `adr_kit.decision.workflows.X`

Files (8):
- `tests/integration/test_mcp_workflow_integration.py` — many imports, but `adr_kit.workflows.planning` stays unchanged
- `tests/integration/test_comprehensive_scenarios.py`
- `tests/integration/test_workflow_creation.py`
- `tests/integration/test_workflow_analyze.py`
- `tests/unit/test_workflow_base.py`
- `tests/unit/test_policy_validation.py`
- `tests/integration/test_decision_quality_assessment.py`

Special case:
- `tests/unit/test_decision_guidance.py`: `adr_kit.workflows.decision_guidance` → `adr_kit.decision.guidance.decision_guidance`

### Enforcement test imports

| File | Old | New |
|------|-----|-----|
| `tests/unit/test_staged_enforcement.py` | `adr_kit.enforce.stages` | `adr_kit.enforcement.validation.stages` |
| `tests/unit/test_staged_enforcement.py` | `adr_kit.enforce.validator` | `adr_kit.enforcement.validation.staged` |
| `tests/unit/test_reporter.py` | `adr_kit.enforce.reporter` | `adr_kit.enforcement.reporter` |
| `tests/unit/test_reporter.py` | `adr_kit.enforce.stages` | `adr_kit.enforcement.validation.stages` |
| `tests/unit/test_reporter.py` | `adr_kit.enforce.validator` | `adr_kit.enforcement.validation.staged` |
| `tests/unit/test_script_generator.py` | `adr_kit.enforce.script_generator` | `adr_kit.enforcement.generation.scripts` |
| `tests/unit/test_hook_generator.py` | `adr_kit.enforce.hooks` | `adr_kit.enforcement.generation.hooks` |
| `tests/unit/test_ci_generator.py` | `adr_kit.enforce.ci` | `adr_kit.enforcement.generation.ci` |

**IMPORTANT**: `test_staged_enforcement.py` has dynamic imports inside test function bodies (not just at the top). Search the ENTIRE file for `from adr_kit.enforce.` patterns.

### Verify: `make test-all && make lint`

### Commit: `refactor: update test imports to new decision/ and enforcement/ paths`

---

## Phase 7: Remove Shims and Clean Up

### Delete workflow shims (keep `__init__.py` and `planning.py`)
```bash
rm adr_kit/workflows/base.py adr_kit/workflows/creation.py adr_kit/workflows/approval.py
rm adr_kit/workflows/supersede.py adr_kit/workflows/preflight.py adr_kit/workflows/analyze.py
rm adr_kit/workflows/decision_guidance.py
```

### Update `adr_kit/workflows/__init__.py` — final form:
```python
"""Workflow orchestration. Planning workflow stays here (context plane).
All other workflows have moved to adr_kit.decision.workflows."""
from adr_kit.decision.workflows.base import BaseWorkflow, WorkflowError, WorkflowResult, WorkflowStatus
from .planning import PlanningWorkflow

__all__ = [
    "BaseWorkflow", "WorkflowResult", "WorkflowError", "WorkflowStatus",
    "PlanningWorkflow",
]
```

### Delete entire old directories
```bash
rm -rf adr_kit/gate/
rm -rf adr_kit/enforce/
rm -rf adr_kit/guardrail/
rm -rf adr_kit/guard/
rm -rf adr_kit/knowledge/   # empty, only __pycache__
```

### Verify: `make test-all && make lint`

### Commit: `refactor: remove backward-compat shims and old directories`

---

## Phase 8: Final Verification

1. `make test-all` — all 309+ tests pass
2. `make lint` — clean
3. Verify no stale imports remain:
```bash
grep -rn "from.*\.gate\." adr_kit/ --include="*.py" | grep -v __pycache__ | grep -v decision
grep -rn "from.*\.enforce\." adr_kit/ --include="*.py" | grep -v __pycache__ | grep -v enforcement
grep -rn "from.*\.guardrail\." adr_kit/ --include="*.py" | grep -v __pycache__
grep -rn "from.*\.guard\." adr_kit/ --include="*.py" | grep -v __pycache__ | grep -v enforcement
grep -rn "adr_kit\.gate\." tests/ --include="*.py"
grep -rn "adr_kit\.enforce\." tests/ --include="*.py"
grep -rn "adr_kit\.guardrail\." tests/ --include="*.py"
grep -rn "adr_kit\.guard\." tests/ --include="*.py"
```
All must return zero results.

4. Verify directory structure: `find adr_kit/ -name "*.py" -not -path "*__pycache__*" | sort`

---

## Critical Notes for Executor

1. **Line numbers are approximate** — always use string matching (Edit tool's `old_string`), never line numbers alone.
2. **`approval.py` is the trickiest file** — 10 relative imports including 3 lazy ones in function bodies.
3. **`reporter.py`** has an internal import `from .validator` that changes to `from .validation.staged` (not a depth change, a path restructure).
4. **`scripts.py`** (was script_generator.py) has `from .stages` that changes to `from ..validation.stages`.
5. **`manager.py`** (in config/) has `from .config_writer` → `from .writer` and `from .file_monitor` → `from .monitor` (file renames).
6. **`planning.py`** stays but its `from .base` import breaks — fix it in Phase 4.
7. **After each phase, run `make test-all && make lint`** before proceeding.
