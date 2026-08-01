"""One configuration file for the whole organization — connector sources, cadences, thresholds.

The single source of truth (YAML, per the spec; JSON also accepted). Every source defaults to empty,
so an unconfigured connector is Unavailable and its job stays idle. String values
support ``${ENV_VAR}`` overrides, and secrets (a GitHub token) are read from the environment, never
the file.

Example (``org-connectors.yaml``)::

    website:
      endpoints: [https://example.com]
    github:
      owner: my-org
      repo: ai-grc
    reports:
      junit: reports/junit.xml
      sarif: reports/results.sarif
    runtime:
      launchagent: com.rasheed.devteam-organization
    cache:
      ttl_seconds: 60
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeGuard

import yaml

CADENCE_10_MIN = 600.0
CADENCE_1_HOUR = 3600.0
CADENCE_6_HOUR = 21600.0

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass(frozen=True)
class Endpoint:
    name: str
    url: str


@dataclass(frozen=True)
class ConnectorConfig:
    """All connector inputs + cadences + thresholds. Empty sources ⇒ Unavailable connectors."""

    # website + http-security
    endpoints: tuple[Endpoint, ...] = ()
    # tls
    tls_hosts: tuple[str, ...] = ()
    # github (owner/repo)
    github_repo: str = ""
    # playwright
    playwright_config: str = ""
    # test / vulnerability / secret reports
    junit_report: str = ""
    pytest_report: str = ""
    coverage_report: str = ""
    regression_report: str = ""
    vulnerability_report: str = ""
    secret_report: str = ""
    # compliance
    compliance_report: str = ""
    policy_dir: str = ""
    # runtime
    runtime_workers: tuple[str, ...] = ()
    # filesystem
    filesystem_folders: tuple[str, ...] = ()
    # cache
    cache_ttl_seconds: float = 60.0
    # thresholds
    tls_expiry_warn_days: int = 21
    website_failure_threshold: int = 3
    response_time_warn_ms: float = 3000.0
    ceo_open_missions_threshold: int = 10
    ceo_incident_threshold: int = 1
    # cadences
    cadence_default: float = CADENCE_10_MIN
    cadence_hourly: float = CADENCE_1_HOUR
    cadence_slow: float = CADENCE_6_HOUR
    cadence_overrides: Mapping[str, float] = field(default_factory=dict)

    def cadence_for(self, job_id: str, default: float) -> float:
        return float(self.cadence_overrides.get(job_id, default))

    @classmethod
    def load(cls, path: Path | str | None) -> ConnectorConfig:
        """Load YAML/JSON, apply ``${ENV}`` substitution, and merge over the safe defaults. A
        missing/unreadable/blank file yields the all-idle default — the service runs with no
        fabrication out of the box."""
        if path is None:
            return cls()
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            raw = _load_document(p)
        except (yaml.YAMLError, json.JSONDecodeError, OSError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        substituted = _env_substitute(raw)
        return cls._from_mapping(substituted if isinstance(substituted, dict) else {})

    @classmethod
    def _from_mapping(cls, raw: Mapping[str, object]) -> ConnectorConfig:
        website = _section(raw, "website")
        http_sec = _section(raw, "http_security")
        tls = _section(raw, "tls")
        github = _section(raw, "github")
        playwright = _section(raw, "playwright")
        reports = _section(raw, "reports")
        compliance = _section(raw, "compliance")
        runtime = _section(raw, "runtime")
        filesystem = _section(raw, "filesystem")
        cache = _section(raw, "cache")
        cadences = _section(raw, "cadences")
        thresholds = _section(raw, "thresholds")

        endpoints = _endpoints(http_sec.get("endpoints") or website.get("endpoints"))
        repo = _github_repo(github)
        workers = _str_tuple(runtime.get("workers"))
        launchagent = _str(runtime.get("launchagent"), "")
        if launchagent:
            workers = (launchagent, *workers)

        return cls(
            endpoints=endpoints,
            tls_hosts=_str_tuple(tls.get("hosts")),
            github_repo=repo,
            playwright_config=_str(playwright.get("config"), ""),
            junit_report=_str(reports.get("junit"), ""),
            pytest_report=_str(reports.get("pytest"), ""),
            coverage_report=_str(reports.get("coverage"), ""),
            regression_report=_str(reports.get("regression"), ""),
            vulnerability_report=_str(reports.get("sarif") or reports.get("vulnerability"), ""),
            secret_report=_str(reports.get("secrets"), ""),
            compliance_report=_str(compliance.get("report"), ""),
            policy_dir=_str(compliance.get("policies"), ""),
            runtime_workers=workers,
            filesystem_folders=_str_tuple(filesystem.get("folders")),
            cache_ttl_seconds=_float(cache.get("ttl_seconds"), 60.0),
            tls_expiry_warn_days=_int(thresholds.get("tls_expiry_warn_days"), 21),
            website_failure_threshold=_int(thresholds.get("website_failure_threshold"), 3),
            response_time_warn_ms=_float(thresholds.get("response_time_warn_ms"), 3000.0),
            ceo_open_missions_threshold=_int(thresholds.get("ceo_open_missions_threshold"), 10),
            ceo_incident_threshold=_int(thresholds.get("ceo_incident_threshold"), 1),
            cadence_default=_float(cadences.get("default"), CADENCE_10_MIN),
            cadence_hourly=_float(cadences.get("hourly"), CADENCE_1_HOUR),
            cadence_slow=_float(cadences.get("slow"), CADENCE_6_HOUR),
            cadence_overrides=_float_map(cadences.get("overrides")),
        )


def _load_document(path: Path) -> object:
    text = path.read_text()
    if path.suffix == ".json":
        return json.loads(text)
    # YAML is a superset of JSON, so safe_load handles both; explicit .json above is just clarity.
    return yaml.safe_load(text)


def _env_substitute(value: object) -> object:
    """Replace ``${ENV_VAR}`` in every string, recursively. An unset var becomes "" (no crash)."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _env_substitute(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_env_substitute(v) for v in value]
    return value


def _section(raw: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _github_repo(github: Mapping[str, object]) -> str:
    repo = github.get("repo")
    if isinstance(repo, str) and "/" in repo:
        return repo
    owner = _str(github.get("owner"), "")
    name = _str(repo, "")
    return f"{owner}/{name}" if owner and name else ""


def _endpoints(value: object) -> tuple[Endpoint, ...]:
    if not isinstance(value, list):
        return ()
    out: list[Endpoint] = []
    for item in value:
        if isinstance(item, str) and item:
            out.append(Endpoint(name=item, url=item))
        elif isinstance(item, dict):
            url = item.get("url")
            if isinstance(url, str) and url:
                name = item.get("name")
                out.append(Endpoint(name=name if isinstance(name, str) and name else url, url=url))
    return tuple(out)


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str) and v)


def _float_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {k: float(v) for k, v in value.items() if isinstance(k, str) and _is_num(v)}


def _is_num(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _str(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _int(value: object, default: int) -> int:
    return int(value) if _is_num(value) else default


def _float(value: object, default: float) -> float:
    return float(value) if _is_num(value) else default
