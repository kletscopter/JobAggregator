"""werkenbijdeoverheid.be — centrale jobboard lokale besturen. Profiel A.

Dekt provincie Antwerpen + lokale besturen + intercommunales (Pidpa, IGEAN)
in één bron. Aanpak: de geavanceerde zoekopdracht (regio = Antwerpen) wordt
server-side bewaard in de sessie en als RSS geëxporteerd (request2rss) —
schoon te parsen, net als WWR.

De detailpagina's renderen werkgever/contract/regime via JavaScript, dus die
halen we niet op; de RSS-summary is rijk genoeg om contracttype, front-facing
en stack-gap door de scoring-engine te laten detecteren.
"""

from __future__ import annotations

import logging
import re

import feedparser

from ..models import PROFILE_A, RawJob
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.werkenbijdeoverheid.be"
HOME_URL = f"{BASE}/"
SEARCH_URL = f"{BASE}/index.php/page/advsearchvacs/bb/1"
RSS_URL = f"{SEARCH_URL}/command/request2rss"

# matchcriteria_regio-id per provincie (uit het zoekformulier).
REGIO_IDS = {
    "antwerpen": "107915",
    "limburg": "107911",
    "oost-vlaanderen": "107905",
    "vlaams-brabant": "107907",
    "west-vlaanderen": "107906",
    "brussel": "107910",
}

# Titel-formaat in de RSS: "Functietitel @ Locatie".
TITLE_AT = re.compile(r"^(?P<title>.+?)\s*@\s*(?P<location>.+)$")


class WerkenBijDeOverheidSource(Source):
    name = "werkenbijdeoverheid"
    profile = PROFILE_A

    def __init__(self, regios: tuple[str, ...] = ("antwerpen",), **kwargs):
        super().__init__(**kwargs)
        self.regios = regios

    def fetch(self) -> list[RawJob]:
        # 1) Sessie warm maken (cookies) + 2) zoekopdracht opslaan server-side.
        if self.get(HOME_URL) is None:
            return []
        regio_ids = [REGIO_IDS[r] for r in self.regios if r in REGIO_IDS]
        form = [
            ("main_keywords", ""),
            ("command", "submitrequest"),
            ("origin", "hook"),
            ("bApplSubmit", "Zoek"),
        ] + [("matchcriteria_regio[]", rid) for rid in regio_ids]
        if self.post(SEARCH_URL, data=form) is None:
            return []

        # 3) Resultaat als RSS ophalen.
        resp = self.get(RSS_URL)
        if resp is None:
            return []
        parsed = feedparser.parse(resp.content)
        jobs = [self._to_raw(e) for e in parsed.entries]
        log.info("[werkenbijdeoverheid] %d vacatures (regio: %s)",
                 len(jobs), ", ".join(self.regios))
        return jobs

    def _to_raw(self, entry) -> RawJob:
        title, location = _split_title(entry.get("title", ""))
        return RawJob(
            title=title,
            url=entry.get("link", "").strip(),
            source=self.name,
            profile=self.profile,
            employer=None,  # niet betrouwbaar zonder JS-detailpagina
            location=location,
            volume=None,  # overheid vermeldt regime enkel op detailpagina
            contract=None,  # scoring leidt contracttype af uit raw_text
            posted_at=entry.get("published"),
            raw_text=_strip_html(entry.get("summary", "")),
            extra={"id": entry.get("id")},
        )


def _split_title(raw_title: str) -> tuple[str, str | None]:
    m = TITLE_AT.match(raw_title or "")
    if m:
        return m.group("title").strip(), m.group("location").strip()
    return (raw_title or "").strip(), None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
