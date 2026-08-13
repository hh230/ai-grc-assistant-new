"""`python -m grc_api.translate_import_cli` — the repeatable, auditable English import.

DRY RUN IS THE DEFAULT. Writing requires `--apply`, and even then only what the plan said, and
only after the plan came back clean. Reading a database and telling you what would happen is a
safe operation to run in any environment; changing it is not, so the flag is the line between.

    python -m grc_api.translate_import_cli                 # dry run, prints the plan
    python -m grc_api.translate_import_cli --apply         # writes, after a clean plan
    python -m grc_api.translate_import_cli --sector retail # one sector

Reads its DSN from `GOVERNANCE_STORE_DSN`, the same variable every other store caller uses.
"""

from __future__ import annotations

import argparse
import sys

from grc_api.translation_import import apply_import, format_report, plan_import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the plan (default: dry run, no writes)")
    parser.add_argument("--sector", action="append", default=None,
                        help="limit to one sector slug; repeatable")
    parser.add_argument("--dsn", default=None, help="override GOVERNANCE_STORE_DSN")
    args = parser.parse_args(argv)

    import psycopg
    from governance_store.config import dsn as default_dsn
    from governance_store.knowledge_store import PostgresKnowledgeStore

    from grc_api.knowledge_seed import available_packs, load_pack

    slugs = args.sector or sorted(available_packs())
    packs = {slug: load_pack(slug) for slug in slugs}

    with psycopg.connect(args.dsn or default_dsn(), autocommit=True) as conn:
        store = PostgresKnowledgeStore(connection=conn)
        report = plan_import(store, packs)
        print(format_report(report))
        if not report.ok:
            print("\nDRY RUN FAILED — nothing would be written.")
            return 1
        if not args.apply:
            print("\nDRY RUN ONLY — no rows written. Re-run with --apply to write.")
            return 0
        written = apply_import(store, report)
        print(f"\nWROTE {written} row(s) at status 'generated'. "
              f"Review and publish are separate, deliberate steps.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
