"""The `Capability` — the product-facing unit (ADR 0046 §4).

A **Capability** is *what the Assistant can do, in the user's terms* ("review this vendor", "make a
policy"). It is a **pure, declarative record** with **no business logic** (a hard Slice-2
constraint): it names itself, describes itself, declares the inputs it needs, and declares the
Mission type it resolves to. It does **not** know how to build a plan (that is the Mission Catalog),
select itself (the Selector), or run anything (the Mission Engine).

`resolver` is deliberately a single Mission type id in Slice 2 (a capability resolves to exactly one
Mission). The design keeps `Capability → Mission(s)` as the seam where a future capability can
orchestrate several Missions — but that is not built here (no multi-Mission, no orchestration).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    """One product capability. Immutable and logic-free (ADR 0046 §4)."""

    id: str
    name: str = ""
    description: str = ""
    # The "input schema": the input keys this capability expects. **Declared, not enforced in
    # Slice 2** — the Selector's only job is existence (ADR 0046 §4); input validation is a later
    # refinement, so this is carried as metadata, not checked here.
    input_schema: tuple[str, ...] = ()
    # The Mission *type* id this capability resolves to (Slice 2: exactly one). The Mission Catalog
    # turns that id into a concrete plan. This is a plain, declarative pointer — never a callable,
    # so no logic lives on the capability.
    resolver: str = ""
