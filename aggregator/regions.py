"""Gedeelde regio-filter voor Profiel-A-bronnen die niet zelf server-side op
provincie Antwerpen filteren (landelijke recruiters, overheid-breed).

Eén plek om de target-regio rond Kontich te tunen.
"""

from __future__ import annotations

# Gemeenten in/rond provincie Antwerpen (lowercase).
ANTWERP_REGION = (
    "antwerpen", "antwerp", "edegem", "kontich", "mortsel", "hove", "boechout",
    "aartselaar", "wilrijk", "borsbeek", "wommelgem", "lint", "duffel", "rumst",
    "niel", "boom", "schelle", "hemiksem", "berchem", "mechelen", "lier",
    "willebroek", "geel", "turnhout", "kempen", "mol", "herentals", "brasschaat",
    "schoten", "kapellen", "brecht", "malle", "zandhoven", "heist-op-den-berg",
    "puurs", "bornem", "kalmthout", "wijnegem", "ranst", "zoersel", "essen",
)


def in_antwerp_region(text: str | None) -> bool:
    """True als de locatietekst een gemeente in de target-regio bevat."""
    loc = (text or "").lower()
    return bool(loc) and any(town in loc for town in ANTWERP_REGION)
