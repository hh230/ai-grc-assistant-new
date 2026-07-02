"""grc_domain — the pure Domain Layer of the AI GRC Assistant.

This package contains business rules only. It has **no dependency** on FastAPI,
SQLAlchemy, any LLM SDK, or any other framework (CLAUDE.md §15). It depends on the Python
standard library alone. Persistence, APIs, AI, and databases live in other layers and
depend inward on this one — never the reverse.

Bounded contexts (each a subpackage):

- ``tenancy``     — Organization, User
- ``workspace``   — Workspace
- ``frameworks``  — Framework definitions and cross-framework mappings
- ``controls``    — customer Control implementations
- ``policies``    — Policy authoring lifecycle
- ``risks``       — Risk identification, scoring, acceptance
- ``assessments`` — gap/coverage Assessments
- ``evidence``    — Evidence artifacts and validity
- ``knowledge``   — the canonical structured-knowledge model (sources, versions, objects)
- ``extraction``  — Knowledge Extraction Engine domain (ExtractionRun and its lifecycle)
- ``reporting``   — Report deliverables
- ``platform``    — Tool / Agent / Plugin governance descriptors
- ``missions``    — the Mission aggregate and its lifecycle (the unit of work)
- ``audit``       — append-only AuditRecord trail

The ``extraction`` context is a supporting subdomain: it depends on ``knowledge`` (it
produces that context's objects) and never the reverse.

The ``shared`` subpackage holds the shared kernel: base Entity / AggregateRoot /
ValueObject / DomainEvent, typed identifiers, common value objects, and the base exception
hierarchy.
"""
from __future__ import annotations

__all__ = [
    "shared",
    "tenancy",
    "workspace",
    "frameworks",
    "controls",
    "policies",
    "risks",
    "assessments",
    "evidence",
    "knowledge",
    "extraction",
    "reporting",
    "platform",
    "missions",
    "audit",
]

__version__ = "0.0.0"
