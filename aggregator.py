#!/usr/bin/env python3
"""CLI-entry voor de Job Aggregator.

Voorbeelden:
    python aggregator.py                 # alle profielen, schrijf jobs.json
    python aggregator.py --profile b     # enkel Profiel B (remote tech)
    python aggregator.py --new-only      # enkel vacatures nieuw sinds vorige run
"""

from __future__ import annotations

import argparse
import logging
import sys

from aggregator.db import DEFAULT_DB_PATH, Database
from aggregator.digest import write_digest
from aggregator.pipeline import run, write_json
from aggregator.webpage import write_html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dagelijkse vacature-aggregator.")
    p.add_argument(
        "--profile", choices=["a", "b"], default=None,
        help="Draai enkel dit profiel (a=BE deeltijds, b=remote tech). Default: beide.",
    )
    p.add_argument(
        "--new-only", action="store_true",
        help="Toon/exporteer enkel vacatures nieuw sinds de vorige run.",
    )
    p.add_argument("--db", default=DEFAULT_DB_PATH, help="Pad naar SQLite-db.")
    p.add_argument("--json", default="jobs.json", help="Pad voor JSON-output.")
    p.add_argument("--digest", default="digest.md", help="Pad voor markdown-digest.")
    p.add_argument("--html", default="digest.html", help="Pad voor HTML-pagina.")
    p.add_argument("--no-fuzzy", action="store_true", help="Schakel fuzzy dedup uit.")
    p.add_argument(
        "--keep-small", action="store_true",
        help="Filter te kleine/voltijdse Profiel-A-rollen niet weg (enkel taggen).",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Debug-logging.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    db = Database(args.db)
    since = db.last_run_at(args.profile) if args.new_only else None

    jobs, new_ids = run(
        db,
        profile=args.profile,
        fuzzy=not args.no_fuzzy,
        drop_hard=not args.keep_small,
    )

    # Voor output: ofwel enkel nieuwe (sinds since), ofwel alles uit db.
    output_jobs = db.get_jobs(profile=args.profile, since=since)
    write_json(output_jobs, args.json)
    write_digest(output_jobs, args.digest, new_ids=new_ids)
    write_html(output_jobs, args.html, new_ids=new_ids)

    print(f"\nKlaar. {len(jobs)} vacatures verwerkt deze run, {len(new_ids)} nieuw.")
    print(f"Output: {args.html} · {args.digest} · {args.json} ({len(output_jobs)} jobs"
          f"{' — enkel nieuw sinds vorige run' if args.new_only else ''}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
