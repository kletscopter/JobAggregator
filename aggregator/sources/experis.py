"""experis.be — IT-staffing (ManpowerGroup). Profiel A (regio-gefilterd).

De zoekpagina /nl/jobs-zoeken/ draait op WordPress + Matador Jobs en rendert de
vacatures server-side (`article.matador-job`) — geen browser nodig. Rollen zijn
meestal voltijds/contract; ze krijgen geen volume-bonus en ranken dus lager.
"""

from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser

from ..models import PROFILE_A, RawJob
from ..regions import in_antwerp_region
from .base import Source

log = logging.getLogger(__name__)

LIST_URL = "https://experis.be/nl/jobs-zoeken/"
MAX_PAGES = 5

# Splitst een trailing "– Gent"/"- Gent" (locatie) van de titel.
LOC_SUFFIX = re.compile(r"\s+[–—-]\s+[^–—-]+$")


class ExperisSource(Source):
    name = "experis"
    profile = PROFILE_A

    def fetch(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        total = 0
        for page in range(1, MAX_PAGES + 1):
            url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
            resp = self.get(url)
            if resp is None:
                break
            cards = HTMLParser(resp.text).css("article.matador-job")
            if not cards:
                break
            total += len(cards)
            for art in cards:
                raw = self._parse(art)
                if raw is not None:
                    jobs.append(raw)
        log.info("[experis] %d in regio van %d gezien", len(jobs), total)
        return jobs

    def _parse(self, art) -> RawJob | None:
        link = art.css_first("h4 a") or art.css_first("a")
        if link is None:
            return None
        url = (link.attributes.get("href") or "").strip()
        if not url:
            return None
        loc_node = art.css_first('a[href*="/vacancies/location/"]')
        location = loc_node.text(strip=True) if loc_node else None
        if not in_antwerp_region(location):
            return None
        heading = art.css_first("h4")
        title = heading.text(strip=True) if heading else link.text(strip=True)
        title = LOC_SUFFIX.sub("", title).strip()
        return RawJob(
            title=title,
            url=url,
            source=self.name,
            profile=self.profile,
            employer="Experis",  # echte werkgever vaak verborgen ('onze klant')
            location=location,
            volume=None,
            contract=None,
            posted_at=None,
            raw_text=art.text(separator=" ", strip=True)[:1000],
            extra={},
        )
