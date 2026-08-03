"""The HTTP surface — drives the running `apps/web` app over real HTTP.

Stdlib `urllib` on purpose: the harness stays dependency-free and runnable anywhere, and this
needs nothing a browser-grade client would give.

**Unreachability is a reported outcome, never a silent skip.** `apps/web`'s existing eval scripts
print SKIP and exit 0 when their dependencies are missing, and CI never sets those dependencies —
so `pnpm test` passes today while verifying nothing. That false confidence is precisely what this
harness exists to remove, so "the app was not running" is surfaced as a distinct, visible result
that a release gate can refuse to treat as success.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any

DEFAULT_BASE_URL = "http://localhost:3000"
DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class Response:
    status: int
    body: str
    # Set when the request could not be made at all (app down, DNS, timeout) — distinct from a
    # request that reached the app and got an error status back.
    transport_error: str | None = None

    @property
    def reached_app(self) -> bool:
        return self.transport_error is None

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except json.JSONDecodeError:
            return None


@dataclass
class HttpSurface:
    """A cookie-aware HTTP client pointed at a running app."""

    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    _jar: CookieJar = field(default_factory=CookieJar, init=False, repr=False)

    def __post_init__(self) -> None:
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            _NoRedirect(),
        )

    def request(
        self, method: str, path: str, *, body: dict[str, Any] | None = None
    ) -> Response:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return Response(status=response.status, body=response.read().decode(errors="replace"))
        except urllib.error.HTTPError as exc:
            # A 4xx/5xx still REACHED the app — that is a result, not a transport failure.
            return Response(status=exc.code, body=exc.read().decode(errors="replace"))
        except Exception as exc:  # noqa: BLE001 — connection refused, DNS, timeout, TLS…
            return Response(status=0, body="", transport_error=f"{type(exc).__name__}: {exc}")

    def available(self) -> bool:
        """Whether the app is actually up. Callers must report a False result, never hide it."""
        return self.request("GET", "/en/login").reached_app

    def login(self, email: str, password: str) -> Response:
        """Authenticate; the cookie jar carries the session for subsequent calls."""
        return self.request("POST", "/api/auth/login", body={"email": email, "password": password})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are answers, not detours.

    A protected page answering 307 to /login is the security control working; following it would
    turn that into a 200 and hide exactly what we came to measure.
    """

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None
