"""Run-pipeline: fetch alle bronnen → normaliseer → dedup → persist.

Scoring/flags/digest komen in latere MVP-stappen; deze module levert nu de
robuuste kern: één kapotte bron stopt de run niet.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Optional

from .db import Database
from .dedup import dedupe
from .models import Job
from .scoring import apply_scoring
from .sources import ALL_SOURCES
from .sources.base import Source

log = logging.getLogger(__name__)


def collect_raw(profile: Optional[str] = None) -> list[Job]:
    """Instantieer en draai alle (relevante) bronnen; geef genormaliseerde Jobs terug."""
    jobs: list[Job] = []
    for source_cls in ALL_SOURCES:
        if profile and source_cls.profile != profile:
            continue
        source: Source = source_cls()
        try:
            raws = source.fetch()
        except Exception as exc:  # noqa: BLE001 — één bron mag de run niet breken
            log.exception("[%s] onverwachte fout, bron overgeslagen: %s",
                          source_cls.name, exc)
            continue
        for raw in raws:
            if not raw.title or not raw.url:
                continue
            jobs.append(Job.from_raw(raw))
    return jobs


def run(
    db: Database,
    profile: Optional[str] = None,
    fuzzy: bool = True,
    drop_hard: bool = True,
) -> tuple[list[Job], set[str]]:
    """Voer een volledige run uit.

    fetch → dedup → score/flag/filter → persist.
    Geeft (gescoorde+gesorteerde jobs, set met ids die nieuw zijn) terug.
    """
    jobs = collect_raw(profile)
    jobs = dedupe(jobs, fuzzy=fuzzy)
    log.info("Na dedup: %d unieke vacatures", len(jobs))

    before = len(jobs)
    jobs = apply_scoring(jobs, drop_hard=drop_hard)
    if before != len(jobs):
        log.info("Na harde filters: %d (%d gedropt)", len(jobs), before - len(jobs))

    new_ids = db.upsert_jobs(jobs)
    db.record_run(profile, n_seen=len(jobs), n_new=len(new_ids))
    log.info("Run klaar: %d gezien, %d nieuw", len(jobs), len(new_ids))
    return jobs, new_ids


def write_json(jobs: list[Job], path: str = "jobs.json") -> None:
    """Schrijf jobs naar JSON (debug/tussenoutput tot digest-stap klaar is)."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([asdict(j) for j in jobs], fh, ensure_ascii=False, indent=2)
    log.info("JSON geschreven naar %s (%d jobs)", path, len(jobs))
