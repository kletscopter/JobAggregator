"""RemoteOK — publieke JSON API. Profiel B (remote tech/crypto).

Eén GET op /api levert alle actieve remote-jobs. Het eerste array-element is
API-metadata (legal/last_updated), geen vacature. We filteren op relevante
tech/crypto-trefwoorden en EU-vriendelijke locaties, net als de Remotive-bron.
"""

from __future__ import annotations

import logging
import re

from ..models import PROFILE_B, RawJob
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"

EU_FRIENDLY = re.compile(
    r"\b(europe|eu|emea|worldwide|anywhere|belgium|netherlands|germany|"
    r"benelux|uk|united kingdom|ireland|france|cet|gmt)\b",
    re.IGNORECASE,
)

RELEVANT_KEYWORDS = (
    "dev", "engineer", "devops", "sysadmin", "backend", "fullstack",
    "full stack", "python", "software", "blockchain", "crypto", "web3",
    "solidity", "smart contract",
)


class RemoteOKSource(Source):
    name = "remoteok"
    profile = PROFILE_B

    def fetch(self) -> list[RawJob]:
        resp = self.get(API_URL)
        if resp is None:
            return []
        try:
            data = resp.json()
        except ValueError as exc:
            log.warning("[remoteok] JSON parse mislukt: %s", exc)
            return []
        if not isinstance(data, list):
            log.warning("[remoteok] onverwachte response (geen lijst)")
            return []

        # Eerste element is metadata; echte jobs hebben een 'position'.
        items = [d for d in data if isinstance(d, dict) and d.get("position")]
        jobs = [self._to_raw(it) for it in items if self._is_relevant(it)]
        log.info("[remoteok] %d relevante vacatures van %d totaal", len(jobs), len(items))
        return jobs

    def _is_relevant(self, item: dict) -> bool:
        hay = f"{item.get('position', '')} {' '.join(item.get('tags', []) or [])}".lower()
        if not any(kw in hay for kw in RELEVANT_KEYWORDS):
            return False
        loc = item.get("location", "") or ""
        return not loc or "remote" in loc.lower() or bool(EU_FRIENDLY.search(loc))

    def _to_raw(self, item: dict) -> RawJob:
        url = (item.get("url") or item.get("apply_url") or "").strip()
        if url and not url.startswith("http"):
            url = "https://remoteok.com" + url
        return RawJob(
            title=(item.get("position") or "").strip(),
            url=url,
            source=self.name,
            profile=self.profile,
            employer=item.get("company"),
            location=item.get("location") or "Remote",
            volume=None,
            contract=None,
            posted_at=item.get("date"),
            raw_text=_strip_html(item.get("description", "")),
            extra={"tags": item.get("tags"), "salary_min": item.get("salary_min")},
        )


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
