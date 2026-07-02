"""Generate the committed OpenAPI specification from the live app.

Run from the repo with the package source roots on PYTHONPATH:

    PYTHONPATH=apps/api/src:packages/domain:packages/services:packages/agents:\
packages/rag:packages/llm:packages/framework-engine:packages/knowledge-graph \
        python apps/api/openapi/generate.py

The committed ``openapi.json`` is the contract source the frontend SDK and partner integrations
generate against (ADR-0013 shared contracts).
"""

from __future__ import annotations

import json
from pathlib import Path

from grc_api.app import create_app
from grc_api.settings import Settings


def main() -> None:
    app = create_app(Settings(app_env="local", llm_provider="fake", auth_seed_dev_principal=False))
    spec = app.openapi()
    output = Path(__file__).parent / "openapi.json"
    output.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    operations = sum(
        1 for item in spec["paths"].values() for method in item if method in {"get", "post", "put", "delete", "patch"}
    )
    print(f"wrote {output} ({len(spec['paths'])} paths, {operations} operations)")


if __name__ == "__main__":
    main()
