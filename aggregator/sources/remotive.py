"""Remotive — publieke JSON API. Profiel B (remote tech)."""

from __future__ import annotations

import logging
import re

from ..models import PROFILE_B, RawJob
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"

# EU-vriendelijke / wereldwijde regio's; Remotive geeft vrije tekst in
# candidate_required_location, dus we matchen breed.
EU_FRIENDLY = re.compile(
    r"\b(europe|eu|emea|worldwide|anywhere|belgium|netherlands|germany|"
    r"benelux|uk|united kingdom|ireland|france|cet|gmt)\b",
    re.IGNORECASE,
)

# Categorie is een display-naam ("Software Development", "DevOps & Sysadmin").
# We matchen op trefwoord i.p.v. exacte slug → robuust tegen hernoemingen.
RELEVANT_CATEGORY_KEYWORDS = ("software", "devops", "sysadmin")


class RemotiveSource(Source):
    name = "remotive"
    profile = PROFILE_B

    def fetch(self) -> list[RawJob]:
        resp = self.get(API_URL, params={"limit": 200})
        if resp is None:
            return []
        try:
            data = resp.json()
        except ValueError as exc:
            log.warning("[remotive] JSON parse mislukt: %s", exc)
            return []

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            if not self._is_relevant(item):
                continue
            jobs.append(self._to_raw(item))
        log.info("[remotive] %d relevante vacatures van %d totaal",
                 len(jobs), len(data.get("jobs", [])))
        return jobs

    def _is_relevant(self, item: dict) -> bool:
        category = (item.get("category") or "").lower()
        if not any(kw in category for kw in RELEVANT_CATEGORY_KEYWORDS):
            return False
        loc = item.get("candidate_required_location", "") or ""
        # Lege locatie behandelen we als "anywhere" → toelaten.
        return not loc or bool(EU_FRIENDLY.search(loc))

    def _to_raw(self, item: dict) -> RawJob:
        return RawJob(
            title=item.get("title", "").strip(),
            url=item.get("url", "").strip(),
            source=self.name,
            profile=self.profile,
            employer=item.get("company_name"),
            location=item.get("candidate_required_location") or "Remote",
            volume=item.get("job_type"),  # bv. "full_time", "contract"
            contract=item.get("job_type"),
            posted_at=item.get("publication_date"),
            raw_text=_strip_html(item.get("description", "")),
            extra={"category": item.get("category"), "salary": item.get("salary")},
        )


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
