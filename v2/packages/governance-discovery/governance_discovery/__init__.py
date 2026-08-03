"""Rasheed V2 **Governance Discovery** engine (ADR 0066) — the adaptive-interview decision engine
behind the AI Governance Planning Engine.

Deterministic and data-driven throughout (CLAUDE.md §6 pillar 8, §19): composable **Knowledge
Packs** (`pack.py`) contribute typed **Signals** (`signal.py`) interpreted by a small declarative
**predicate DSL** (`predicate.py`). **Tier A** (`engine.py`) runs after every answer and only ever
decides the next question. **Tier B** (`analysis.py`) runs exactly once, at conclusion, producing
frameworks/maturity/capacity/gaps/plan_items in one atomic pass — nothing is ever computed or
exposed incrementally. The **capacity model** (`capacity.py`) and **scheduler** (`scheduler.py`)
size the resulting plan to what the organization can actually execute, never a fixed template.

    from governance_discovery import DiscoveryEngine, DiscoverySessionState, SignalSet, analyze
    from governance_discovery.pack import load_bundled_packs

    engine = DiscoveryEngine(load_bundled_packs())
    state = DiscoverySessionState(signals=SignalSet())
    question = engine.next_question(state)  # Tier A: one question at a time
    # ... accumulate answers into `state.signals` ...
    if engine.is_concluded(state):
        applicability = analyze(state.signals, engine)  # Tier B: one-shot, at conclusion
"""

from governance_discovery.analysis import (
    Applicability,
    analyze,
    rate_maturity_scores,
    score_maturity,
)
from governance_discovery.capacity import compute_capacity
from governance_discovery.engine import STAGE_ORDER, DiscoveryEngine, DiscoverySessionState
from governance_discovery.execution import effective_signals
from governance_discovery.pack import KnowledgePack, Question, load_bundled_packs, load_packs
from governance_discovery.plan import GovernancePlan, PlanEvent, PlanItem
from governance_discovery.predicate import evaluate, referenced_signals
from governance_discovery.scheduler import compute_due_at, schedule
from governance_discovery.session import DiscoverySession
from governance_discovery.signal import Signal, SignalSet, ValueType

__all__ = [
    "DiscoveryEngine",
    "DiscoverySessionState",
    "STAGE_ORDER",
    "DiscoverySession",
    "Signal",
    "SignalSet",
    "ValueType",
    "KnowledgePack",
    "Question",
    "load_packs",
    "load_bundled_packs",
    "evaluate",
    "referenced_signals",
    "analyze",
    "Applicability",
    "compute_capacity",
    "schedule",
    "compute_due_at",
    "effective_signals",
    "GovernancePlan",
    "PlanItem",
    "PlanEvent",
    "score_maturity",
    "rate_maturity_scores",
]
