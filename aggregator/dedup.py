"""Deduplicatie van jobs binnen één run.

Primair: exacte match op job-id ((titel+werkgever+locatie)-hash).
Optioneel: fuzzy match via rapidfuzz om bijna-identieke titels samen te voegen
(bv. dezelfde vacature op twee bronnen met licht andere bewoording).
"""

from __future__ import annotations

from .models import Job, normalize_key

try:
    from rapidfuzz import fuzz

    _HAS_RAPIDFUZZ = True
except ImportError:  # rapidfuzz is optioneel
    _HAS_RAPIDFUZZ = False


def dedupe(jobs: list[Job], fuzzy: bool = True, threshold: int = 92) -> list[Job]:
    """Geef een gededupliceerde lijst terug, eerste voorkomen wint.

    - Exacte dedup op `id` is altijd actief.
    - Fuzzy dedup (optioneel) voegt bijna-identieke (titel @ werkgever) samen.
    """
    seen_ids: set[str] = set()
    kept: list[Job] = []
    for job in jobs:
        if job.id in seen_ids:
            continue
        if fuzzy and _HAS_RAPIDFUZZ and _is_fuzzy_dup(job, kept, threshold):
            continue
        seen_ids.add(job.id)
        kept.append(job)
    return kept


def _is_fuzzy_dup(job: Job, kept: list[Job], threshold: int) -> bool:
    """True als `job` quasi-identiek is aan een reeds bewaarde job."""
    title_key = normalize_key(job.title)
    emp_key = normalize_key(job.employer)
    for other in kept:
        if normalize_key(other.employer) != emp_key:
            continue  # zelfde werkgever vereist voor fuzzy merge
        if fuzz.token_sort_ratio(title_key, normalize_key(other.title)) >= threshold:
            return True
    return False
