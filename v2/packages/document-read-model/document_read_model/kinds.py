"""The product vocabulary for evidence — the `evidence_kind` a Document is classified under.

This is the classification the user chooses at upload, and the grouping the Knowledge view is
built around (Design rule 1: *Knowledge = Evidence Collections*). It is named **`evidence_kind`**,
never `*_type`, because "type" is already overloaded in the platform (Mission Type · Content-Type
· MIME type · Result type) and this is a *classification of evidence* (REST_API_CONTRACT_V1 §2, S4
footnote).

The **order of declaration is the display order** of the collections in the Knowledge view; `OTHER`
is the catch-all and sorts last. `DocumentStatus` is the ingestion lifecycle of a Document —
modelled as a status because a Document is an entity whose ingestion is a process (Design rule 2:
*Upload is an event; a Document is an entity*), even though S4 does upload→ingest→ready in one call.

`DocumentItem` stores these as plain strings (like `MissionListItem.status`), so the read model is
storage-agnostic and never rejects a value it is handed; these enums are the *validated* vocabulary
the API boundary accepts and the view orders by.
"""

from __future__ import annotations

from enum import Enum


class EvidenceKind(str, Enum):
    """The evidence classifications a Document can carry (the six of REST_API_CONTRACT_V1 §2).

    Subclasses `str` so a member is usable directly as its wire value
    (`EvidenceKind.POLICY == "policy"`) while staying an enumerable, ordered vocabulary."""

    POLICY = "policy"
    PROCEDURE = "procedure"
    STANDARD = "standard"
    SOC_REPORT = "soc_report"
    RISK_REGISTER = "risk_register"
    OTHER = "other"


# The canonical display order for the Knowledge view's collections (declaration order; OTHER last).
# A document whose stored kind is not one of these sorts after them, alphabetically — the read model
# never drops a row just because its kind is unfamiliar.
KIND_ORDER: tuple[str, ...] = tuple(kind.value for kind in EvidenceKind)


def is_known_kind(value: str) -> bool:
    """Whether `value` is one of the six product evidence kinds. The API boundary validates uploads
    with this; the read model itself does not (it stores whatever it is projected)."""
    return value in KIND_ORDER


def kind_sort_key(evidence_kind: str) -> tuple[int, str]:
    """Order a kind by its place in `KIND_ORDER`, unknown kinds last (then alphabetically). Used so
    the collections list renders in the product's intended order regardless of insertion order."""
    try:
        return (KIND_ORDER.index(evidence_kind), evidence_kind)
    except ValueError:
        return (len(KIND_ORDER), evidence_kind)


class DocumentStatus(str, Enum):
    """A Document's ingestion lifecycle (REST_API_CONTRACT_V1 §2: ingesting·ready·failed)."""

    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"
