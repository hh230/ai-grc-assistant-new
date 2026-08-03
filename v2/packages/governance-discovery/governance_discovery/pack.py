"""Knowledge Packs (ADR 0066 §2.1–§2.2) — self-contained data documents, the *only* thing that
changes to add coverage. The engine that loads and interprets them never changes to add a pack.

A pack declares its own `activation_predicate`; the `core` pack (no predicate) is always active.
Multiple packs are active simultaneously by design — an organization is rarely one industry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from governance_discovery.predicate import Expr
from governance_discovery.signal import ValueType

CORE_PACK_ID = "pack:core"


@dataclass(frozen=True)
class Question:
    id: str
    version: str
    prompt_key: str
    value_type: ValueType
    writes_signal: str
    priority: int
    stage: str
    applicability_predicate: Expr | None = None
    options: tuple[str, ...] | None = None
    # A question is REQUIRED unless explicitly marked optional (free-text clarifications, extra
    # context) — required-ness feeds `engine.REQUIRED_PRIORITY_THRESHOLD` coverage/confidence.
    required: bool = True
    # Presentation only — never changes what the value IS (that's `value_type`), only how the
    # interview renders the input: "dropdown" | "buttons" | "chips" | "number" | "date" |
    # "short_text". The engine and predicate evaluation never read this field.
    ui_hint: str | None = None
    # A multi-select question's Signal value is a list of option values rather than one.
    allow_multiple: bool = False


@dataclass(frozen=True)
class RecommendsFramework:
    framework_id: str
    confidence: float
    rationale_key: str


@dataclass(frozen=True)
class MaturityDimensionScore:
    dimension: str
    delta: int


@dataclass(frozen=True)
class PlanSeed:
    id: str
    pillar: str
    title_key: str
    rationale_key: str
    urgency: str  # critical | high | medium | low
    effort_size: str  # trivial | small | medium | large
    depends_on: tuple[str, ...] = ()
    # What completing this recommendation is equivalent to, in the same Signal vocabulary the
    # interview speaks — `{"signal": key, "value": ...}` (ADR 0066 §5.3). Optional: some items are
    # too broad to collapse into one signal, and completing them updates status with no signal
    # effect. Never looked up live from the pack at completion time — pinned onto the persisted
    # `governance_plan_items.resolves_signal` at plan-creation time for reproducibility.
    resolves_signal: dict | None = None


@dataclass(frozen=True)
class FlagsGap:
    gap_id: str
    severity: str
    rationale_key: str


@dataclass(frozen=True)
class Effect:
    recommends_framework: RecommendsFramework | None = None
    maturity_dimension_score: MaturityDimensionScore | None = None
    plan_seed: PlanSeed | None = None
    flags_gap: FlagsGap | None = None


@dataclass(frozen=True)
class Rule:
    id: str
    version: str
    predicate: Expr
    effect: Effect


@dataclass(frozen=True)
class KnowledgePack:
    pack_id: str
    version: str
    labels: dict[str, str]
    aliases: tuple[str, ...] = ()
    activation_predicate: Expr | None = None
    questions: tuple[Question, ...] = ()
    rules: tuple[Rule, ...] = ()

    @property
    def is_always_active(self) -> bool:
        return self.activation_predicate is None


def _parse_effect(raw: dict) -> Effect:
    return Effect(
        recommends_framework=(
            RecommendsFramework(**raw["recommends_framework"])
            if raw.get("recommends_framework")
            else None
        ),
        maturity_dimension_score=(
            MaturityDimensionScore(**raw["maturity_dimension_score"])
            if raw.get("maturity_dimension_score")
            else None
        ),
        plan_seed=(
            PlanSeed(
                depends_on=tuple(raw["plan_seed"].get("depends_on", ())),
                **{k: v for k, v in raw["plan_seed"].items() if k != "depends_on"},
            )
            if raw.get("plan_seed")
            else None
        ),
        flags_gap=FlagsGap(**raw["flags_gap"]) if raw.get("flags_gap") else None,
    )


def _parse_question(raw: dict) -> Question:
    return Question(
        id=raw["id"],
        version=raw["version"],
        prompt_key=raw["prompt_key"],
        value_type=ValueType(raw["value_type"]),
        writes_signal=raw["writes_signal"],
        priority=raw["priority"],
        stage=raw["stage"],
        applicability_predicate=raw.get("applicability_predicate"),
        options=tuple(raw["options"]) if raw.get("options") else None,
        required=raw.get("required", True),
        ui_hint=raw.get("ui_hint"),
        allow_multiple=raw.get("allow_multiple", False),
    )


def _parse_rule(raw: dict) -> Rule:
    return Rule(
        id=raw["id"],
        version=raw["version"],
        predicate=raw["predicate"],
        effect=_parse_effect(raw["effect"]),
    )


def pack_from_dict(raw: dict) -> KnowledgePack:
    """Parse and lightly validate a pack document. Malformed data fails fast here rather than at
    runtime (CI schema validation, tracked for Phase 5, tightens this further)."""
    for required in ("pack_id", "version", "labels"):
        if required not in raw:
            raise ValueError(f"knowledge pack missing required field: {required}")
    if not str(raw["pack_id"]).startswith("pack:"):
        raise ValueError(f"pack_id must start with 'pack:': {raw['pack_id']!r}")
    return KnowledgePack(
        pack_id=raw["pack_id"],
        version=raw["version"],
        labels=raw["labels"],
        aliases=tuple(raw.get("aliases", ())),
        activation_predicate=raw.get("activation_predicate"),
        questions=tuple(_parse_question(q) for q in raw.get("questions", ())),
        rules=tuple(_parse_rule(r) for r in raw.get("rules", ())),
    )


def load_pack(path: Path) -> KnowledgePack:
    return pack_from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_packs(directory: Path) -> dict[str, KnowledgePack]:
    """Load every `*.json` pack in a directory, keyed by `pack_id`. Exactly one must be the
    always-active `core` pack — the engine refuses to operate without it."""
    packs = {}
    for path in sorted(directory.glob("*.json")):
        pack = load_pack(path)
        packs[pack.pack_id] = pack
    if CORE_PACK_ID not in packs:
        raise ValueError(f"no {CORE_PACK_ID} pack found in {directory}")
    return packs


BUNDLED_PACKS_DIR = Path(__file__).resolve().parent / "packs"


def load_bundled_packs() -> dict[str, KnowledgePack]:
    return load_packs(BUNDLED_PACKS_DIR)
