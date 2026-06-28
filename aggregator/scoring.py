"""Scoring + flags + harde filters.

Transparante gewogen som (zie build-spec):
  +3 onbepaalde duur, +1 tijdelijk-met-optie-vast
  +2 volume in [18/36, 24/36] (~50-67%), +1 daarboven
  +2 regio binnen ~20 km van Kontich, +1 elders in prov. Antwerpen
  +2 autonome/solo-rol, -2 front_facing
  -1 per stack_gap-item (capped)

Flags taggen i.p.v. droppen: stack_gap, contract, front_facing, autonomous.
Harde filters (enkel Profiel A): volume < ~50% droppen, voltijds-only droppen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import PROFILE_A, Job, normalize_key

# --- Trefwoorden -----------------------------------------------------------

# Moderne cloud-tooling buiten het huidige sysadmin/networking/Python-profiel.
STACK_GAP_TERMS = [
    "kubernetes", "k8s", "terraform", "ansible", "gitops", "argocd",
    "ci/cd", "ci / cd", "cicd", "helm", "pulumi",
]

# Support-/klantgerichte signalen → downrank.
FRONT_FACING_TERMS = [
    "helpdesk", "support", "klantencontact", "klantgericht", "klantendienst",
    "onthaal", "receptie", "balie", "front office", "customer service",
    "customer support", "servicedesk", "1ste lijn", "eerste lijn",
]

# Autonome/solo-rol.
AUTONOMOUS_TERMS = [
    "autonoom", "zelfstandig", "in alle autonomie", "eigen verantwoordelijk",
    "solo", "eigen initiatief", "zelfsturend", "coordinator", "coordinatie",
]

# Contracttype.
PERMANENT_TERMS = ["onbepaalde duur", "vast contract", "vaste benoeming", "statutair"]
TEMP_OPTION_TERMS = [
    "optie vast", "uitzicht op vast", "met optie op een vast", "kan leiden tot vast",
]
TEMP_TERMS = ["bepaalde duur", "tijdelijk", "vervangingscontract", "interim", "contract"]

# Gemeenten binnen ~20 km van Kontich.
NEAR_KONTICH = {
    "kontich", "edegem", "mortsel", "hove", "boechout", "aartselaar",
    "wilrijk", "antwerpen", "borsbeek", "wommelgem", "lint", "duffel",
    "rumst", "niel", "boom", "schelle", "hemiksem", "berchem", "mechelen",
    "lier", "kontich-kazerne",
}

# Stack-gap-aftrek wordt afgetopt.
STACK_GAP_CAP = 3

# Voorberekende normalized varianten (normalize_key is duur; deze lijsten zijn
# constant, dus 1× normaliseren i.p.v. per job opnieuw).
AUTONOMOUS_KEYS = [normalize_key(t) for t in AUTONOMOUS_TERMS]
FRONT_FACING_KEYS = [normalize_key(t) for t in FRONT_FACING_TERMS]
PERMANENT_KEYS = [normalize_key(t) for t in PERMANENT_TERMS]
TEMP_OPTION_KEYS = [normalize_key(t) for t in TEMP_OPTION_TERMS]
TEMP_KEYS = [normalize_key(t) for t in TEMP_TERMS]


@dataclass
class ScoreResult:
    score: int
    flags: list[str]
    reason: str
    dropped: bool = False
    drop_reason: str = ""


def parse_volume(volume: str | None) -> float | None:
    """Normaliseer een volume naar een fractie (0..1). None als onbekend.

    Herkent "80%", "MIN.60%", "18/36", "halftijds", "voltijds".
    """
    if not volume:
        return None
    v = volume.lower().strip()
    if "voltijd" in v or "fulltime" in v or "full_time" in v or "full time" in v:
        return 1.0
    if "halftijds" in v or "halftime" in v:
        return 0.5
    # X/Y vorm (bv. 18/36)
    m = re.search(r"(\d+)\s*/\s*(\d+)", v)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den:
            return num / den
    # percentage
    m = re.search(r"(\d{1,3})\s*%", v)
    if m:
        return int(m.group(1)) / 100
    return None


def _has_term(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t in text]


def score_job(job: Job, min_volume: float = 0.47) -> ScoreResult:
    """Bereken score + flags + reden voor één job.

    `min_volume`: harde ondergrens voor Profiel A (≈18/36). Iets onder 0.5
    om afrondingsruis (bv. "MIN.50%") niet weg te filteren.
    """
    text = normalize_key(f"{job.title} {job.raw_text} {job.contract or ''} {job.volume or ''}")
    # normalize_key strip leestekens; voor "ci/cd" e.d. ook op ruwe lower matchen.
    raw = f"{job.title} {job.raw_text} {job.contract or ''} {job.volume or ''}".lower()

    flags: list[str] = []
    reasons: list[str] = []
    score = 0

    # --- Contract ---
    contract_kind = _classify_contract(text, raw, job)
    if contract_kind == "permanent":
        score += 3
        flags.append("contract:onbepaald")
        reasons.append("+3 onbepaalde duur")
    elif contract_kind == "temp_option":
        score += 1
        flags.append("contract:tijdelijk-optie-vast")
        reasons.append("+1 tijdelijk met optie vast")
    elif contract_kind == "temp":
        flags.append("contract:tijdelijk")
        reasons.append("0 tijdelijk")

    # --- Volume ---
    frac = parse_volume(job.volume)
    if frac is not None:
        if 0.5 <= frac <= 0.67:
            score += 2
            reasons.append(f"+2 volume {round(frac*100)}% (ideaal halftijds)")
        elif frac > 0.67:
            score += 1
            reasons.append(f"+1 volume {round(frac*100)}%")
        # < 0.5 wordt door de harde filter afgehandeld (Profiel A)
    else:
        flags.append("volume:onbekend")
        reasons.append("0 volume onbekend")

    # --- Regio ---
    region_pts, region_reason = _score_region(job)
    score += region_pts
    if region_reason:
        reasons.append(region_reason)

    # --- Autonoom / front-facing ---
    if _has_term(text, AUTONOMOUS_KEYS):
        score += 2
        flags.append("autonomous")
        reasons.append("+2 autonome/solo-rol")
    front = _has_term(text, FRONT_FACING_KEYS)
    if front:
        score -= 2
        flags.append("front_facing")
        reasons.append("-2 front-facing/support")

    # --- Stack gap ---
    gaps = [t for t in STACK_GAP_TERMS if t in raw]
    if gaps:
        penalty = min(len(gaps), STACK_GAP_CAP)
        score -= penalty
        flags.append("stack_gap:" + ",".join(sorted(set(gaps))))
        reasons.append(f"-{penalty} stack-gap ({', '.join(sorted(set(gaps)))})")

    result = ScoreResult(score=score, flags=flags, reason="; ".join(reasons))

    # --- Harde filters (enkel Profiel A) ---
    if job.profile == PROFILE_A:
        if frac is not None and frac < min_volume:
            result.dropped = True
            result.drop_reason = f"volume {round(frac*100)}% < {round(min_volume*100)}%"
        elif frac is not None and frac >= 0.99:
            result.dropped = True
            result.drop_reason = "voltijds-only rol in Profiel A"

    return result


def _classify_contract(text: str, raw: str, job: Job) -> str | None:
    """Geef 'permanent' | 'temp_option' | 'temp' | None terug."""
    if any(t in text for t in PERMANENT_KEYS):
        return "permanent"
    if any(t in text for t in TEMP_OPTION_KEYS):
        return "temp_option"
    # Remotive 'contract' job_type = freelance/tijdelijk
    if (job.contract or "").lower() in {"contract", "freelance", "temporary"}:
        return "temp"
    if any(t in text for t in TEMP_KEYS):
        return "temp"
    return None


def _score_region(job: Job) -> tuple[int, str]:
    loc = normalize_key(job.location)
    if loc and any(town in loc for town in NEAR_KONTICH):
        return 2, "+2 regio binnen ~20 km van Kontich"
    # Profiel-A-bronnen filteren al op provincie Antwerpen → elke job ligt
    # minstens in de provincie, ook gemeenten buiten onze NEAR-lijst (bv. Olen).
    if job.profile == PROFILE_A:
        return 1, "+1 elders in prov. Antwerpen"
    # Profiel B: enkel punten als de locatie expliciet Antwerps is.
    if loc and ("antwerpen" in loc or "turnhout" in loc or "geel" in loc or "kempen" in loc):
        return 1, "+1 elders in prov. Antwerpen"
    return 0, ""


def apply_scoring(jobs: list[Job], drop_hard: bool = True) -> list[Job]:
    """Score alle jobs in-place; verwijder optioneel hard-gefilterde (Profiel A)."""
    kept: list[Job] = []
    for job in jobs:
        res = score_job(job)
        job.score = res.score
        job.flags = res.flags
        job.score_reason = res.reason
        if res.dropped and drop_hard:
            continue
        kept.append(job)
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept
