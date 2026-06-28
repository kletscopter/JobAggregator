"""web3.career — Web3/crypto jobs API. Profiel B.

De API vereist een gratis token. Registreer op
https://web3.career/web3-jobs-api en zet de token in de omgevingsvariabele
WEB3CAREER_TOKEN. Zonder token wordt de bron netjes overgeslagen (net zoals
VDAB zonder Playwright) — de rest van de run blijft werken.

De response-vorm is defensief afgehandeld: web3.career geeft historisch
[status, message, [jobs]] terug, maar we vangen ook {"jobs": [...]} en een
kale lijst van job-dicts op.
"""

from __future__ import annotations

import logging
import os
import re

from ..models import PROFILE_B, RawJob
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://web3.career/api/v1"
TOKEN_ENV = "WEB3CAREER_TOKEN"


class Web3CareerSource(Source):
    name = "web3career"
    profile = PROFILE_B

    def fetch(self) -> list[RawJob]:
        token = os.environ.get(TOKEN_ENV)
        if not token:
            log.info("[web3career] geen %s gezet — bron overgeslagen", TOKEN_ENV)
            return []
        resp = self.get(API_URL, params={"token": token, "limit": 100, "remote": "true"})
        if resp is None:
            return []
        try:
            data = resp.json()
        except ValueError as exc:
            log.warning("[web3career] JSON parse mislukt: %s", exc)
            return []
        items = _extract_jobs(data)
        jobs = [self._to_raw(it) for it in items if isinstance(it, dict) and it.get("title")]
        log.info("[web3career] %d vacatures", len(jobs))
        return jobs

    def _to_raw(self, item: dict) -> RawJob:
        return RawJob(
            title=(item.get("title") or "").strip(),
            url=(item.get("apply_url") or item.get("url") or "").strip(),
            source=self.name,
            profile=self.profile,
            employer=item.get("company"),
            location=item.get("location") or "Remote",
            volume=None,
            contract=None,
            posted_at=item.get("date") or item.get("date_epoch"),
            raw_text=_strip_html(item.get("description", "")),
            extra={"tags": item.get("tags")},
        )


def _extract_jobs(data) -> list:
    """Haal de jobs-lijst uit de diverse mogelijke response-vormen."""
    if isinstance(data, dict):
        return data.get("jobs") or data.get("data") or []
    if isinstance(data, list):
        # Vorm [status, message, [ {..}, .. ]]: pak het laatste geneste lijst-element.
        for el in reversed(data):
            if isinstance(el, list):
                return el
        # Of gewoon een kale lijst van job-dicts.
        if data and all(isinstance(el, dict) for el in data):
            return data
    return []


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
