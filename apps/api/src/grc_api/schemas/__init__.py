"""HTTP schema layer — Pydantic request/response models and Result→HTTP helpers.

The API validates every inbound payload and shapes every response with Pydantic models
(ADR-0013): the boundary is typed and self-documenting (OpenAPI), and application DTOs never
leak their internal representation directly. Response models read from the frozen application
DTOs by attribute (``from_attributes``); request models translate into application Commands.
"""

from __future__ import annotations

from .common import ApiModel, ProblemDetail, problem_responses, unwrap

__all__ = ["ApiModel", "ProblemDetail", "problem_responses", "unwrap"]
