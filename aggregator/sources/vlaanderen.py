"""vlaanderen.be — vacatures Vlaamse overheid via de overview-search JSON-API.
Profiel A (regio-gefilterd op Antwerpen).

De publieke zoek-API (POST /api/overview-search) levert gestructureerde JSON met
paginatie — geen browser nodig. We filteren de resultaten op de Antwerpse regio,
zodat de Profiel-A-scoring (die provincie Antwerpen veronderstelt) blijft kloppen.
Veel items zijn VDAB-afkomstig → dedup vangt overlap met de VDAB-bron op.
"""

from __future__ import annotations

import html as html_mod
import logging
import re

from ..models import PROFILE_A, RawJob
from ..regions import in_antwerp_region
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://www.vlaanderen.be/api/overview-search"
BASE = "https://www.vlaanderen.be"
# Collectie-id 'werken voor vlaanderen / vacatures' (uit de SPA-request).
HUB = "cc0f4502-9afd-42cf-b71f-31e43937d855"
# De API geeft 400 bij offset>0; één pagina (nieuwste 50, gesorteerd op datum)
# volstaat voor een dagelijkse digest. Veel items zijn VDAB-afkomstig (dedup
# vangt overlap met de VDAB-bron op).
PAGE_SIZE = 50
MAX_PAGES = 1


class VlaanderenSource(Source):
    name = "vlaanderen"
    profile = PROFILE_A

    def fetch(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen = 0
        offset = 0
        for _ in range(MAX_PAGES):
            resp = self.post(API_URL, json=self._body(offset))
            if resp is None:
                break
            try:
                data = resp.json()
            except ValueError as exc:
                log.warning("[vlaanderen] JSON parse mislukt: %s", exc)
                break
            items = data.get("items", [])
            if not items:
                break
            seen += len(items)
            for it in items:
                raw = self._to_raw(it)
                if raw is not None:
                    jobs.append(raw)
            offset += len(items)
            if offset >= data.get("totalItems", 0):
                break
        log.info("[vlaanderen] %d in regio van %d gezien", len(jobs), seen)
        return jobs

    def _body(self, offset: int) -> dict:
        return {
            "page": {"offset": offset, "limit": PAGE_SIZE},
            "filter": {
                "contentType": {"IN": ["Job"]},
                "contentTypeSubtypeRelatedFiltersOperator": "OR",
                "visibility": {"hub": HUB},
                "collectionFilters": {"contentSubtypeData__sources": {"IN": ["VO"]}},
            },
            "orderBy": {"publicationDate": "DESC"},
            "resolverContext": {"language": "nl", "revision": "default"},
        }

    def _to_raw(self, item: dict) -> RawJob | None:
        loc_text = _locations_text(item.get("locations") or [])
        if not in_antwerp_region(loc_text):
            return None
        link = (item.get("link") or "").strip()
        url = link if link.startswith("http") else BASE + link
        if not url or not link:
            return None
        return RawJob(
            title=_clean(_as_text(item.get("title")) or _as_text(item.get("displayTitle"))),
            url=url,
            source=self.name,
            profile=self.profile,
            employer=item.get("hiringOrganization"),
            location=loc_text or None,
            volume=None,
            contract=None,
            posted_at=None,
            raw_text=_clean(_as_text(item.get("description"))),
            extra={"domain": item.get("domain"), "identifier": item.get("identifier")},
        )


def _as_text(value) -> str:
    """Vlaanderen.be levert sommige velden als {'htmlEncoded': ...}-dict."""
    if isinstance(value, dict):
        return value.get("htmlEncoded") or value.get("value") or value.get("text") or ""
    return value or ""


def _locations_text(locations: list) -> str:
    """Trek een leesbare stad/locatie-string uit de (geneste) locations-lijst."""
    out: list[str] = []
    for loc in locations:
        if isinstance(loc, str):
            out.append(loc)
        elif isinstance(loc, dict):
            for key in ("city", "name", "label", "municipality"):
                val = loc.get(key)
                if isinstance(val, str):
                    out.append(val)
            addr = loc.get("address")
            if isinstance(addr, dict):
                city = addr.get("city") or addr.get("municipality")
                if city:
                    out.append(city)
    return ", ".join(dict.fromkeys(out))  # uniek, volgorde behouden


def _clean(value: str) -> str:
    text = html_mod.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
