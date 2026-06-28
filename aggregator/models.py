"""Datamodellen: RawJob (ruw per bron) en Job (genormaliseerd)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# Profielen
PROFILE_A = "a"  # Belgische deeltijdse loondienst
PROFILE_B = "b"  # Remote tech / crypto


@dataclass
class RawJob:
    """Ruwe vacature zoals een Source ze oplevert, vóór normalisatie.

    Velden zijn bewust losjes getypeerd: elke bron levert aan wat ze heeft,
    normalisatie naar `Job` gebeurt centraal via `Job.from_raw`.
    """

    title: str
    url: str
    source: str
    profile: str
    employer: Optional[str] = None
    location: Optional[str] = None
    volume: Optional[str] = None  # bv. "18/36", "50%", "fulltime"
    contract: Optional[str] = None  # bv. "onbepaalde duur", "tijdelijk"
    posted_at: Optional[str] = None  # ISO-string indien beschikbaar
    raw_text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    """Genormaliseerde vacature, uniek per `id`, persistent in SQLite."""

    id: str
    title: str
    url: str
    source: str
    profile: str
    employer: Optional[str] = None
    location: Optional[str] = None
    volume: Optional[str] = None
    contract: Optional[str] = None
    posted_at: Optional[str] = None
    raw_text: str = ""
    flags: list[str] = field(default_factory=list)
    score: int = 0
    score_reason: str = ""
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    @classmethod
    def from_raw(cls, raw: RawJob) -> "Job":
        return cls(
            id=make_job_id(raw.title, raw.employer, raw.location),
            title=clean_text(raw.title),
            url=raw.url.strip(),
            source=raw.source,
            profile=raw.profile,
            employer=clean_text(raw.employer) if raw.employer else None,
            location=clean_text(raw.location) if raw.location else None,
            volume=raw.volume,
            contract=raw.contract,
            posted_at=raw.posted_at,
            raw_text=raw.raw_text or "",
        )


def clean_text(value: Optional[str]) -> str:
    """Trim + squash interne whitespace; geeft "" terug voor None."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_key(value: Optional[str]) -> str:
    """Lowercase, accenten weg, niet-alfanumeriek weg — voor dedup-sleutels."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


def make_job_id(title: Optional[str], employer: Optional[str], location: Optional[str]) -> str:
    """Stabiele id uit (titel + werkgever + locatie).

    Identiek voor dezelfde vacature over meerdere runs → idempotent.
    """
    key = "|".join(normalize_key(p) for p in (title, employer, location))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
