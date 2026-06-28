"""halftijds.be — Belgische site voor deeltijdse loondienst. Profiel A.

De vacatures staan als Squarespace-events op /vacatures-all. Per event:
  - .eventlist-title-link  → titel + detail-URL
  - .eventlist-excerpt     → "WERKGEVER ° LOCATIE ° VOLUME"
  - .eventlist-cats        → o.a. "PROV: ANTWERPEN" (provincie-tag)
  - time[datetime]         → start/eind (eind = sollicitatiedeadline)

Alles staat in de listingpagina zelf, dus één request volstaat — geen
detailpagina's nodig.
"""

from __future__ import annotations

import logging

from selectolax.parser import HTMLParser

from ..models import PROFILE_A, RawJob
from .base import Source

log = logging.getLogger(__name__)

BASE_URL = "https://www.halftijds.be"
LIST_URL = f"{BASE_URL}/vacatures-all"

# Gemeenten in de target-regio (rond Kontich). Match op locatietekst als de
# provincie-tag ontbreekt of breder is.
ANTWERP_REGION = (
    "antwerpen", "edegem", "kontich", "mortsel", "hove", "boechout",
    "lier", "geel", "turnhout", "mechelen", "kempen",
)


class HalftijdsSource(Source):
    name = "halftijds"
    profile = PROFILE_A

    def __init__(self, provinces: tuple[str, ...] = ("antwerpen",), **kwargs):
        super().__init__(**kwargs)
        # Provincienamen (lowercase) waarop we filteren via de PROV-tag.
        self.provinces = tuple(p.lower() for p in provinces)

    def fetch(self) -> list[RawJob]:
        resp = self.get(LIST_URL)
        if resp is None:
            return []
        tree = HTMLParser(resp.text)
        articles = tree.css("article.eventlist-event")

        jobs: list[RawJob] = []
        for art in articles:
            raw = self._parse_article(art)
            if raw is None:
                continue
            if not self._in_region(raw):
                continue
            jobs.append(raw)
        log.info("[halftijds] %d in regio van %d totaal", len(jobs), len(articles))
        return jobs

    def _parse_article(self, art) -> RawJob | None:
        link = art.css_first(".eventlist-title-link")
        if link is None:
            return None
        href = (link.attributes.get("href") or "").strip()
        if not href:
            return None
        url = href if href.startswith("http") else BASE_URL + href

        title = link.text(strip=True)
        excerpt_node = art.css_first(".eventlist-excerpt")
        excerpt = excerpt_node.text(strip=True) if excerpt_node else ""
        employer, location, volume = _split_excerpt(excerpt)

        cats_node = art.css_first(".eventlist-cats")
        cats = cats_node.text(strip=True) if cats_node else ""

        deadline = _last_datetime(art)

        return RawJob(
            title=title,
            url=url,
            source=self.name,
            profile=self.profile,
            employer=employer,
            location=location,
            volume=volume,
            contract=None,  # contracttype staat enkel op de detailpagina
            posted_at=None,  # halftijds toont geen publicatiedatum
            raw_text=excerpt,
            extra={"categories": cats, "deadline": deadline},
        )

    def _in_region(self, raw: RawJob) -> bool:
        cats = (raw.extra.get("categories") or "").lower()
        if any(f"prov: {prov}" in cats for prov in self.provinces):
            return True
        # Fallback: locatietekst matcht een gemeente in de regio.
        loc = (raw.location or "").lower()
        return any(town in loc for town in ANTWERP_REGION)


def _split_excerpt(excerpt: str) -> tuple[str | None, str | None, str | None]:
    """'WERKGEVER ° LOCATIE ° VOLUME' → (werkgever, locatie, volume)."""
    if not excerpt or "°" not in excerpt:
        return (excerpt or None), None, None
    parts = [p.strip() for p in excerpt.split("°")]
    employer = parts[0] or None
    location = parts[1] if len(parts) > 1 and parts[1] else None
    volume = parts[2] if len(parts) > 2 and parts[2] else None
    return employer, location, volume


def _last_datetime(art) -> str | None:
    """Laatste time[datetime] = eind-/deadlinedatum van het event."""
    times = [t.attributes.get("datetime") for t in art.css("time[datetime]")]
    times = [t for t in times if t]
    return times[-1] if times else None
