"""Source-basisklasse + gedeelde HTTP-helper met UA + rate limiting."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from ..models import RawJob

log = logging.getLogger(__name__)

USER_AGENT = (
    "JobAggregator/0.1 (persoonlijk project; contact ron.verhaege@gmail.com)"
)
DEFAULT_TIMEOUT = 20
DEFAULT_RATE_LIMIT = 1.0  # seconden tussen requests per bron


class Source:
    """Basisklasse voor een vacaturebron.

    Subklassen zetten `name`/`profile` en implementeren `fetch()`.
    """

    name: str = "base"
    profile: str = ""

    def __init__(self, rate_limit: float = DEFAULT_RATE_LIMIT):
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request_at: float = 0.0

    def fetch(self) -> list[RawJob]:  # pragma: no cover - interface
        raise NotImplementedError

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """GET met UA, throttle en timeout. Geeft None terug bij fout (logt)."""
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> Optional[requests.Response]:
        """POST met UA, throttle en timeout. Geeft None terug bij fout (logt)."""
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        self._throttle()
        try:
            resp = self.session.request(method, url, timeout=DEFAULT_TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            log.warning("[%s] %s mislukt voor %s: %s", self.name, method, url, exc)
            return None
