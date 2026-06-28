"""We Work Remotely — RSS feeds per categorie. Profiel B (remote tech)."""

from __future__ import annotations

import logging
import re

import feedparser

from ..models import PROFILE_B, RawJob
from .base import Source

log = logging.getLogger(__name__)

# RSS-feeds per relevante categorie.
FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]

# WWR-titels hebben vaak de vorm "Werkgever: Functietitel".
TITLE_SPLIT = re.compile(r"^\s*(?P<employer>[^:]{2,60}?)\s*:\s*(?P<title>.+)$")


class WeWorkRemotelySource(Source):
    name = "weworkremotely"
    profile = PROFILE_B

    def fetch(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        for feed_url in FEEDS:
            resp = self.get(feed_url)
            if resp is None:
                continue
            parsed = feedparser.parse(resp.content)
            if parsed.bozo:
                log.warning("[wwr] feed niet schoon geparsed: %s (%s)",
                            feed_url, parsed.get("bozo_exception"))
            for entry in parsed.entries:
                jobs.append(self._to_raw(entry))
            log.info("[wwr] %d entries van %s", len(parsed.entries), feed_url)
        return jobs

    def _to_raw(self, entry) -> RawJob:
        employer, title = _split_title(entry.get("title", ""))
        # WWR zet locatie/regio soms in de 'region'-tag of in de title.
        location = entry.get("region") or _extract_location(entry) or "Remote"
        return RawJob(
            title=title,
            url=entry.get("link", "").strip(),
            source=self.name,
            profile=self.profile,
            employer=employer,
            location=location,
            volume=None,
            contract=None,
            posted_at=entry.get("published") or entry.get("updated"),
            raw_text=_strip_html(entry.get("summary", "")),
            extra={"id": entry.get("id")},
        )


def _split_title(raw_title: str) -> tuple[str | None, str]:
    m = TITLE_SPLIT.match(raw_title or "")
    if m:
        return m.group("employer").strip(), m.group("title").strip()
    return None, (raw_title or "").strip()


def _extract_location(entry) -> str | None:
    # Sommige feeds nemen regio op in een 'tags'-lijst.
    tags = entry.get("tags") or []
    for tag in tags:
        term = tag.get("term") if isinstance(tag, dict) else None
        if term:
            return term
    return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
