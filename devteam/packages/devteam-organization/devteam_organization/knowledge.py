"""Framework knowledge for the GRC Expert — a real, injectable control catalog (CLAUDE.md §13).

The GRC Expert maps a mission to the controls it touches across the frameworks the platform serves
(ISO 27001, NIST CSF, SOC 2, PCI DSS, GDPR). This is *real reference data* — well-known control
identifiers — matched by real keyword analysis, never fabricated. It is an injected seam
(``FrameworkKnowledge``) so the deterministic default here can later be swapped for the full
``framework-library`` tool (ADR 0050) without touching the agent — the same way the Developer's
``PatchProposer`` can be swapped for an LLM.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameworkControl:
    """One control a mission touches: which framework, its stable identifier, and its title."""

    framework: str
    control_id: str
    title: str

    @property
    def label(self) -> str:
        return f"{self.framework} {self.control_id} — {self.title}"


# ``goal text -> the controls it touches``. Injected, so the default below is swappable.
FrameworkKnowledge = Callable[[str], Sequence[FrameworkControl]]


# A curated cross-framework catalog keyed by the compliance theme a mission raises. Every identifier
# is a real control from the named standard. Kept small and honest: enough to map the common GRC
# themes; the full library replaces it behind the same seam.
_THEMES: dict[str, tuple[FrameworkControl, ...]] = {
    "access": (
        FrameworkControl("ISO 27001", "A.5.15", "Access control"),
        FrameworkControl("NIST CSF", "PR.AA", "Identity Management & Access Control"),
        FrameworkControl("SOC 2", "CC6.1", "Logical access controls"),
        FrameworkControl("PCI DSS", "Req 7", "Restrict access by business need to know"),
    ),
    "encryption": (
        FrameworkControl("ISO 27001", "A.8.24", "Use of cryptography"),
        FrameworkControl("NIST CSF", "PR.DS", "Data Security"),
        FrameworkControl("SOC 2", "CC6.7", "Encryption of data in transit"),
        FrameworkControl("PCI DSS", "Req 3/4", "Protect stored data & encrypt in transit"),
        FrameworkControl("GDPR", "Art 32", "Security of processing"),
    ),
    "logging": (
        FrameworkControl("ISO 27001", "A.8.15", "Logging"),
        FrameworkControl("NIST CSF", "DE.CM", "Continuous Monitoring"),
        FrameworkControl("SOC 2", "CC7.2", "System monitoring"),
        FrameworkControl("PCI DSS", "Req 10", "Log and monitor all access"),
    ),
    "incident": (
        FrameworkControl("ISO 27001", "A.5.24", "Incident management planning"),
        FrameworkControl("NIST CSF", "RS.MA", "Incident Management"),
        FrameworkControl("SOC 2", "CC7.4", "Incident response"),
        FrameworkControl("GDPR", "Art 33", "Breach notification"),
    ),
    "privacy": (
        FrameworkControl("GDPR", "Art 5", "Principles of processing personal data"),
        FrameworkControl("GDPR", "Art 30", "Records of processing activities"),
        FrameworkControl("ISO 27001", "A.5.34", "Privacy and protection of PII"),
    ),
    "vendor": (
        FrameworkControl("ISO 27001", "A.5.19", "Supplier relationships"),
        FrameworkControl("NIST CSF", "GV.SC", "Cybersecurity Supply Chain Risk Management"),
        FrameworkControl("SOC 2", "CC9.2", "Vendor and business-partner management"),
        FrameworkControl("GDPR", "Art 28", "Processor obligations"),
    ),
}

# When a mission raises no specific theme, these baseline governance controls still apply.
_BASELINE: tuple[FrameworkControl, ...] = (
    FrameworkControl("ISO 27001", "A.5.1", "Policies for information security"),
    FrameworkControl("NIST CSF", "GV.OC", "Organizational Context"),
    FrameworkControl("SOC 2", "CC1.1", "Control environment"),
)

# The words that raise each theme. Real keyword analysis over the mission goal.
_THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "access": ("access", "auth", "login", "permission", "rbac", "identity", "mfa", "privilege"),
    "encryption": ("encrypt", "crypto", "tls", "cipher", "secret", "key", "confidential"),
    "logging": ("log", "audit", "monitor", "observability", "trace", "alert"),
    "incident": ("incident", "breach", "response", "outage", "recovery", "disaster"),
    "privacy": ("privacy", "personal data", "pii", "pdpl", "gdpr", "consent", "data subject"),
    "vendor": ("vendor", "supplier", "third party", "third-party", "processor", "supply chain"),
}


def default_framework_knowledge(goal: str) -> tuple[FrameworkControl, ...]:
    """Map a goal to the real controls it touches by keyword analysis over the catalog. Falls
    back to the baseline governance controls when the goal raises no specific theme — never empty,
    never invented."""
    lowered = goal.lower()
    matched: list[FrameworkControl] = []
    for theme, keywords in _THEME_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            matched.extend(_THEMES[theme])
    return tuple(matched) if matched else _BASELINE
