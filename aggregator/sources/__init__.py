"""Bronnen (Source-classes). Elke bron levert RawJob's via fetch()."""

from .base import Source
from .halftijds import HalftijdsSource
from .remotive import RemotiveSource
from .vdab import VdabSource
from .werkenbijdeoverheid import WerkenBijDeOverheidSource
from .wwr import WeWorkRemotelySource

__all__ = [
    "Source",
    "HalftijdsSource",
    "WerkenBijDeOverheidSource",
    "VdabSource",
    "RemotiveSource",
    "WeWorkRemotelySource",
    "ALL_SOURCES",
]

# Geregistreerde bronnen per profiel (uitbreidbaar in latere MVP-stappen).
ALL_SOURCES: list[type[Source]] = [
    HalftijdsSource,          # profiel A
    WerkenBijDeOverheidSource,  # profiel A
    VdabSource,               # profiel A (Playwright)
    RemotiveSource,           # profiel B
    WeWorkRemotelySource,     # profiel B
]
