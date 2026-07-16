"""OpenAI embedding provider. Talks to the `/v1/embeddings` endpoint over stdlib
`urllib` — no vendor SDK dependency, so the package stays light and nothing in the
codebase imports an LLM SDK directly (CLAUDE.md §5).

The API key is read from the environment (`OPENAI_API_KEY`) at call time and is never
stored on the provider, in a manifest, or in an embedding record. It is never hardcoded.

Defaults to `text-embedding-3-large` truncated to 1536 dimensions via the API's
`dimensions` parameter — the exact choice the Knowledge Library architecture doc (§6)
made so vectors fit under pgvector's HNSW index cap.

The HTTP transport is injectable (`transport=`) so tests exercise the request/response
handling without a network or a key. Retry and batching are the engine's job, not this
provider's."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

# A transport takes (url, json_payload, headers) and returns the parsed JSON response.
Transport = Callable[[str, dict[str, object], dict[str, str]], dict[str, object]]


def _urllib_transport(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed OpenAI https endpoint
        return json.loads(response.read().decode("utf-8"))


class OpenAIConfigError(RuntimeError):
    """Raised when the provider is selected but no API key is configured. This is a
    configuration error surfaced clearly — never a silent fallback that would send data
    somewhere unintended."""


@dataclass
class OpenAIEmbeddingProvider:
    name: str = "openai"
    model: str = "text-embedding-3-large"
    dimension: int = 1536
    api_key_env: str = "OPENAI_API_KEY"
    transport: Transport = field(default=_urllib_transport)

    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise OpenAIConfigError(
                f"{self.api_key_env} is not set. Set it in the environment to use the OpenAI "
                f"embedding provider; it is never read from code or config files."
            )
        return key

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": list(texts),
            "dimensions": self.dimension,
        }
        headers = {"Authorization": f"Bearer {self._api_key()}"}
        response = self.transport(OPENAI_EMBEDDINGS_URL, payload, headers)

        data = response.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise ValueError(f"OpenAI response returned {len(data) if isinstance(data, list) else 'no'} vectors for {len(texts)} inputs")
        # The API may return items out of order; each carries its input index.
        ordered = sorted(data, key=lambda item: item["index"])  # type: ignore[index]
        return [list(item["embedding"]) for item in ordered]  # type: ignore[index]
