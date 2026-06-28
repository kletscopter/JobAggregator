"""ictjob.be — Belgische IT-vacaturesite via RSS. Profiel A (regio-gefilterd).

De publieke RSS (/nl/rss) levert alle recente IT-vacatures in België. Titel-
formaat: "Functietitel - Werkgever - Locatie". We filteren op de Antwerpse regio
zodat de Profiel-A-scoring (die provincie Antwerpen veronderstelt) blijft kloppen.

Let op: ICTjob-rollen zijn doorgaans voltijds en de RSS vermeldt geen regime.
Ze krijgen dus geen volume-bonus (flag 'volume:onbekend') en ranken lager dan de
echte deeltijdse bronnen — wat past bij Profiel A's deeltijds-focus.
"""

from __future__ import annotations

import logging
import re

import feedparser

from ..models import PROFILE_A, RawJob
from .base import Source

log = logging.getLogger(__name__)

RSS_URL = "https://www.ictjob.be/nl/rss"

# Gemeenten in/rond provincie Antwerpen (lowercase) waarop we de locatie matchen.
ANTWERP_REGION = (
    "antwerpen", "antwerp", "edegem", "kontich", "mortsel", "hove", "boechout",
    "aartselaar", "wilrijk", "borsbeek", "wommelgem", "lint", "duffel", "rumst",
    "niel", "boom", "schelle", "hemiksem", "berchem", "mechelen", "lier",
    "willebroek", "geel", "turnhout", "kempen", "mol", "herentals", "brasschaat",
    "schoten", "kapellen", "brecht", "malle", "zandhoven", "heist-op-den-berg",
)

# Titel-formaat: "Functietitel - Werkgever - Locatie".
TITLE_SPLIT = re.compile(r"\s+-\s+")


class IctjobSource(Source):
    name = "ictjob"
    profile = PROFILE_A

    def __init__(self, region: tuple[str, ...] = ANTWERP_REGION, **kwargs):
        super().__init__(**kwargs)
        self.region = tuple(r.lower() for r in region)

    def fetch(self) -> list[RawJob]:
        resp = self.get(RSS_URL)
        if resp is None:
            return []
        parsed = feedparser.parse(resp.content)
        if parsed.bozo:
            log.warning("[ictjob] feed niet schoon geparsed: %s",
                        parsed.get("bozo_exception"))
        jobs: list[RawJob] = []
        for entry in parsed.entries:
            raw = self._to_raw(entry)
            if raw is not None:
                jobs.append(raw)
        log.info("[ictjob] %d in regio van %d totaal", len(jobs), len(parsed.entries))
        return jobs

    def _to_raw(self, entry) -> RawJob | None:
        title, employer, location = _split_title(entry.get("title", ""))
        if not _in_region(location, self.region):
            return None
        return RawJob(
            title=title,
            url=entry.get("link", "").strip(),
            source=self.name,
            profile=self.profile,
            employer=employer,
            location=location,
            volume=None,   # RSS vermeldt regime niet (meestal voltijds)
            contract=None,
            posted_at=entry.get("published"),
            raw_text=_strip_html(entry.get("summary", "")),
            extra={"guid": entry.get("id")},
        )


def _split_title(raw_title: str) -> tuple[str, str | None, str | None]:
    """'Titel - Werkgever - Locatie' → (titel, werkgever, locatie)."""
    parts = [p.strip() for p in TITLE_SPLIT.split(raw_title or "") if p.strip()]
    if len(parts) >= 3:
        return " - ".join(parts[:-2]), parts[-2] or None, parts[-1] or None
    if len(parts) == 2:
        return parts[0], None, parts[1] or None
    return (raw_title or "").strip(), None, None


def _in_region(location: str | None, region: tuple[str, ...]) -> bool:
    loc = (location or "").lower()
    return bool(loc) and any(town in loc for town in region)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
