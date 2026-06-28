"""brunel.net — technisch/engineering staffing via de PublicationsSearch JSON-API.
Profiel A (regio-gefilterd op Antwerpen).

POST /api/search/PublicationsSearch/Get levert Belgische vacatures als JSON; de
detailpagina is https://www.brunel.net/nl-be/vacatures/{publicationId}. Bevat
`hoursPerWeek`, wat we naar een volume-percentage vertalen voor de scoring.
"""

from __future__ import annotations

import html as html_mod
import logging
import re

from ..models import PROFILE_A, RawJob
from ..regions import in_antwerp_region
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://www.brunel.net/api/search/PublicationsSearch/Get"
DETAIL_URL = "https://www.brunel.net/nl-be/vacatures/{id}"
PAGE_SIZE = 50
MAX_PAGES = 4
FULLTIME_HOURS = 38.0  # ~voltijds in BE


class BrunelSource(Source):
    name = "brunel"
    profile = PROFILE_A

    def fetch(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen = 0
        for page in range(1, MAX_PAGES + 1):
            resp = self.post(API_URL, json=self._body(page))
            if resp is None:
                break
            try:
                data = resp.json()
            except ValueError as exc:
                log.warning("[brunel] JSON parse mislukt: %s", exc)
                break
            pubs = data.get("publications") or []
            if not pubs:
                break
            seen += len(pubs)
            for p in pubs:
                raw = self._to_raw(p)
                if raw is not None:
                    jobs.append(raw)
            if page * PAGE_SIZE >= data.get("totalCount", 0):
                break
        log.info("[brunel] %d in regio van %d gezien", len(jobs), seen)
        return jobs

    def _body(self, page: int) -> dict:
        return {
            "page": page,
            "pageSize": PAGE_SIZE,
            "language": "nl-BE",
            "countryPreset": ["BEL"],
            "businessUnitPreset": [],
            "businessLineFilter": [],
            "sortOrder": "2",
            "locationFilter": {},
        }

    def _to_raw(self, p: dict) -> RawJob | None:
        loc = " ".join(x for x in (p.get("city"), p.get("region"),
                                   p.get("locationDetail")) if x)
        if not in_antwerp_region(loc):
            return None
        pid = p.get("publicationId")
        if not pid:
            return None
        text = _clean(" ".join(x for x in (
            p.get("introduction"), p.get("description"),
            p.get("jobrequirements"), p.get("vacancySummary")) if x))
        return RawJob(
            title=_clean(p.get("title")),
            url=DETAIL_URL.format(id=pid),
            source=self.name,
            profile=self.profile,
            employer="Brunel",
            location=loc or None,
            volume=_volume(p.get("hoursPerWeek")),
            contract=None,
            posted_at=p.get("startDate"),
            raw_text=text,
            extra={"area": p.get("areaOfExpertise"), "hours": p.get("hoursPerWeek")},
        )


def _volume(hours) -> str | None:
    """Geef enkel een volume terug bij deeltijds (<37u); voltijds → None zodat de
    Profiel-A voltijds-drop deze recruiter-jobs niet wegfiltert."""
    try:
        h = float(hours)
    except (TypeError, ValueError):
        return None
    if h <= 0 or h >= 37:
        return None
    return f"{round(h / FULLTIME_HOURS * 100)}%"


def _clean(value) -> str:
    text = html_mod.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
