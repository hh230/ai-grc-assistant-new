"""Value objects for the Audit bounded context."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AiCallTrace:
    """Captures the reproducibility metadata of a single model call (CLAUDE.md §19)."""

    provider: str
    model: str
    model_version: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        for amount in (self.input_tokens, self.output_tokens, self.latency_ms):
            if amount < 0:
                raise ValueError("AiCallTrace numeric fields must be non-negative")
