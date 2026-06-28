"""Arbeitnow — gratis job-board JSON API (EU/remote). Profiel B.

De publieke API (/api/job-board-api) levert {"data": [...]} met o.a. remote-flag,
tags en job_types. We houden enkel remote + tech/crypto-relevante rollen over.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from ..models import PROFILE_B, RawJob
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"

RELEVANT_KEYWORDS = (
    "dev", "engineer", "devops", "sysadmin", "backend", "fullstack",
    "full stack", "python", "software", "blockchain", "crypto", "web3",
    "solidity", "data",
)


class ArbeitnowSource(Source):
    name = "arbeitnow"
    profile = PROFILE_B

    def fetch(self) -> list[RawJob]:
        resp = self.get(API_URL)
        if resp is None:
            return []
        try:
            data = resp.json()
        except ValueError as exc:
            log.warning("[arbeitnow] JSON parse mislukt: %s", exc)
            return []
        items = data.get("data", []) if isinstance(data, dict) else []
        jobs = [self._to_raw(it) for it in items if self._is_relevant(it)]
        log.info("[arbeitnow] %d relevante vacatures van %d totaal", len(jobs), len(items))
        return jobs

    def _is_relevant(self, item: dict) -> bool:
        if not item.get("remote"):
            return False
        hay = f"{item.get('title', '')} {' '.join(item.get('tags', []) or [])}".lower()
        return any(kw in hay for kw in RELEVANT_KEYWORDS)

    def _to_raw(self, item: dict) -> RawJob:
        job_types = item.get("job_types", []) or []
        return RawJob(
            title=(item.get("title") or "").strip(),
            url=(item.get("url") or "").strip(),
            source=self.name,
            profile=self.profile,
            employer=item.get("company_name"),
            location=item.get("location") or "Remote",
            volume=None,
            contract=", ".join(job_types) or None,
            posted_at=_epoch_to_iso(item.get("created_at")),
            raw_text=_strip_html(item.get("description", "")),
            extra={"tags": item.get("tags"), "slug": item.get("slug")},
        )


def _epoch_to_iso(epoch) -> str | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OSError, TypeError):
        return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
