"""Launch the Operations Dashboard: ``python -m devteam_dashboard`` (optionally overriding what to
observe). With no arguments it reads the live LaunchAgent plist, so on the deployed machine it just
works. Localhost only, no auth — an operator tool bound to 127.0.0.1.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from devteam_dashboard.app import create_app
from devteam_dashboard.config import load_config


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - launches a live server
    parser = argparse.ArgumentParser(
        description="Local, presentation-only Operations Dashboard for the dev-team monitor."
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address; localhost only")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--repo", default=None, help="owner/name to observe (default: from plist)")
    parser.add_argument("--repo-root", default=None, help="checkout (default: plist/git root)")
    parser.add_argument("--log-file", default=None, help="monitor log (default: from plist)")
    parser.add_argument("--plist", default=None, help="LaunchAgent plist (default: known)")
    parser.add_argument("--label", default=None, help="LaunchAgent label (default: known)")
    args = parser.parse_args(argv)

    config = load_config(
        plist_path=args.plist,
        label=args.label,
        repo=args.repo,
        repo_root=args.repo_root,
        log_path=args.log_file,
        host=args.host,
        port=args.port,
    )
    app = create_app(config)
    print(
        f"Operations Dashboard → http://{config.host}:{config.port}  "
        f"(repo={config.repo or 'unconfigured'}, log={config.log_path})"
    )
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
