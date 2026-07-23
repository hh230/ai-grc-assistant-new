"""`ControlLibraryTool` — the first real GRC tool (ADR 0050).

It implements the frozen `tool_registry.Tool` protocol (`spec` + `invoke`), so it is registered in
the `ToolRegistry` and invoked by the Mission Engine's executor exactly like any tool — and a plan
step routes to it by name via `PlanStep.tool` (ADR 0048). It is **deterministic and read-only**: it
reads the step's opaque `instruction` as a control query and looks it up in the `FrameworkLibrary`.

The instruction is interpreted, in order:
  1. an **exact control code** (`A.8.5`) → that one control;
  2. a **theme / domain** (`Technological`) → every control in it;
  3. otherwise a **keyword** → controls whose code or title contains it.

The result is a `ToolStepResult` (ADR 0049): a readable summary in `output`, the matched control ids
in `source_ids` (the provenance — *which* controls answer the query), and a warning when nothing
matches. Being a deterministic catalog lookup, `confidence` stays `None` — the grounding is the
exact ids, not a probability. It never depends on an LLM: the verbatim normative text is the
Pipeline Tool's grounded-retrieval job (ADR 0050), not this catalog's.
"""

from __future__ import annotations

from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, ToolSpec, ToolStepResult

from framework_library.library import FrameworkLibrary
from framework_library.models import Control, Framework

CONTROL_LIBRARY_TOOL = "framework_control_library"
DEFAULT_FRAMEWORK_ID = "framework:iso_27001"


class ControlLibraryTool:
    """A registered `Tool` (satisfies the tool-registry `Tool` protocol structurally) that answers
    control-catalog queries over a `FrameworkLibrary`. Bind it to a default framework; a query may
    still target any loaded framework in a later slice (this MVP looks up the default)."""

    def __init__(
        self,
        library: FrameworkLibrary,
        *,
        default_framework_id: str = DEFAULT_FRAMEWORK_ID,
        version: int = 1,
        name: str = CONTROL_LIBRARY_TOOL,
    ) -> None:
        self._library = library
        self._default_framework_id = default_framework_id
        self._spec = ToolSpec(
            name=name,
            version=version,
            description=(
                "Look up controls in a compliance framework's catalog by code, theme, or "
                "title keyword. Deterministic, read-only; returns matched control ids as "
                "provenance."
            ),
            side_effect=SideEffectProfile.READ_ONLY,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        query = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip()
        framework = self._library.get(self._default_framework_id)
        matches, how = _resolve(framework, query)
        return _result(framework, query, matches, how).as_payload()


def _resolve(framework: Framework, query: str) -> tuple[tuple[Control, ...], str]:
    """Interpret the query against the framework: exact code, then theme, then keyword. Returns the
    matches and a short label for *how* they were found (for the human-readable summary)."""
    if not query:
        return framework.controls, "all controls"
    exact = framework.get(query)
    if exact is not None:
        return (exact,), f"code {exact.code}"
    by_domain = framework.by_domain(query)
    if by_domain:
        return by_domain, f"theme {query}"
    return framework.search(query), f"keyword {query!r}"


def _result(
    framework: Framework, query: str, matches: tuple[Control, ...], how: str
) -> ToolStepResult:
    if not matches:
        return ToolStepResult(
            ok=True,
            output=f"No {framework.name} controls matched {query!r}.",
            warnings=(f"no controls matched {query!r}",),
        )
    header = f"{framework.name} — {len(matches)} control(s) for {how}:"
    lines = [f"{c.code} {c.title}" + (f" [{c.domain}]" if c.domain else "") for c in matches]
    return ToolStepResult(
        ok=True,
        output="\n".join([header, *lines]),
        source_ids=tuple(c.id for c in matches),
    )
