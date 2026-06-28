"""Bronnen (Source-classes). Elke bron levert RawJob's via fetch()."""

from .arbeitnow import ArbeitnowSource
from .base import Source
from .brunel import BrunelSource
from .experis import ExperisSource
from .halftijds import HalftijdsSource
from .ictjob import IctjobSource
from .remoteok import RemoteOKSource
from .remotive import RemotiveSource
from .vdab import VdabOverheidSource, VdabSource
from .vlaanderen import VlaanderenSource
from .web3career import Web3CareerSource
from .werkenbijdeoverheid import WerkenBijDeOverheidSource
from .wwr import WeWorkRemotelySource

__all__ = [
    "Source",
    "HalftijdsSource",
    "WerkenBijDeOverheidSource",
    "VdabSource",
    "VdabOverheidSource",
    "IctjobSource",
    "VlaanderenSource",
    "ExperisSource",
    "BrunelSource",
    "RemotiveSource",
    "WeWorkRemotelySource",
    "RemoteOKSource",
    "ArbeitnowSource",
    "Web3CareerSource",
    "ALL_SOURCES",
]

# Geregistreerde bronnen per profiel.
ALL_SOURCES: list[type[Source]] = [
    HalftijdsSource,            # profiel A
    WerkenBijDeOverheidSource,  # profiel A
    VdabSource,                 # profiel A (Playwright)
    VdabOverheidSource,         # profiel A (Playwright, IT-overheid)
    IctjobSource,               # profiel A (RSS, regio-gefilterd)
    VlaanderenSource,           # profiel A (overheid-API, regio-gefilterd)
    ExperisSource,              # profiel A (WordPress/Matador, regio-gefilterd)
    BrunelSource,               # profiel A (staffing-API, regio-gefilterd)
    RemotiveSource,             # profiel B
    WeWorkRemotelySource,       # profiel B
    RemoteOKSource,             # profiel B
    ArbeitnowSource,            # profiel B
    Web3CareerSource,           # profiel B (optionele token)
]
