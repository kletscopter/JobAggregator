"""VDAB (Vind een job) — Profiel A. Via Playwright (headless browser).

VDAB heeft geen bruikbare publieke API en de interne endpoint
(`/rest/vindeenjob/v4/vacatureLight/zoek`) zit achter een gateway die elke
non-browser request met 403 weigert. De SPA voegt bovendien per sessie een
anti-bot header `vej-key-monitor` toe.

Aanpak: we laden de zoekpagina één keer in een echte (headless) browser, vangen
die `vej-key-monitor`-token op uit de eigen request van de SPA, en roepen daarna
de JSON-API rechtstreeks aan via `fetch()` binnen de browsercontext (zelfde
origin → passeert de gateway). Zo halen we gestructureerde JSON op met volledige
controle over filters (deeltijds, provincie) en paginatie.

Vereist Playwright + Chromium:  python -m playwright install chromium
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from ..models import PROFILE_A, RawJob, normalize_key
from .base import Source

log = logging.getLogger(__name__)

SEARCH_PAGE = "https://www.vdab.be/vindeenjob/vacatures"
API_PATH = "/rest/vindeenjob/v4/vacatureLight/zoek"
DETAIL_URL = "https://www.vdab.be/vindeenjob/vacatures/{id}"
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# JS dat vanuit de browsercontext de zoek-API aanroept met de opgevangen token.
_FETCH_JS = """
async ([criteria, key]) => {
  const r = await fetch('%s', {
    method: 'POST',
    headers: {'content-type': 'application/json', 'accept': 'application/json',
              'vej-key-monitor': key},
    body: JSON.stringify(criteria),
  });
  const txt = await r.text();
  return { status: r.status, data: txt ? JSON.parse(txt) : null };
}
""" % API_PATH


class VdabSource(Source):
    name = "vdab"
    profile = PROFILE_A

    def __init__(
        self,
        trefwoorden: tuple[str, ...] = ("ICT-coördinator",),
        locatie_code: str = "BE21",  # provincie Antwerpen
        locatie_naam: str = "Antwerpen (Provincie)",
        deeltijds: bool = True,
        page_size: int = 50,
        max_results: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.trefwoorden = trefwoorden
        self.locatie_code = locatie_code
        self.locatie_naam = locatie_naam
        self.deeltijds = deeltijds
        self.page_size = page_size
        self.max_results = max_results

    def fetch(self) -> list[RawJob]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.warning("[vdab] Playwright niet geïnstalleerd — bron overgeslagen "
                        "(pip install playwright && python -m playwright install chromium)")
            return []

        by_id: dict[int, RawJob] = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=CHROME_UA)
                token = self._capture_token(page)
                if not token:
                    log.warning("[vdab] geen vej-key-monitor token opgevangen")
                    return []
                for trefwoord in self.trefwoorden:
                    for item in self._search_all(page, token, trefwoord):
                        vid = item.get("id", {}).get("id")
                        if vid is not None and vid not in by_id:
                            by_id[vid] = self._to_raw(vid, item)
            finally:
                browser.close()

        jobs = list(by_id.values())
        log.info("[vdab] %d deeltijdse vacatures (trefwoorden: %s)",
                 len(jobs), ", ".join(self.trefwoorden))
        return jobs

    def _capture_token(self, page) -> str | None:
        """Laad de zoekpagina en vang de anti-bot header uit de SPA-request."""
        token: dict[str, str] = {}

        def on_request(req):
            if API_PATH in req.url and "vej-key-monitor" in req.headers:
                token["k"] = req.headers["vej-key-monitor"]

        page.on("request", on_request)
        url = f"{SEARCH_PAGE}?trefwoord={quote(self.trefwoorden[0])}&locatie=Antwerpen"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)  # SPA laat de eerste zoek-call afvuren
        except Exception as exc:  # noqa: BLE001
            log.warning("[vdab] laden zoekpagina mislukt: %s", exc)
        return token.get("k")

    def _search_all(self, page, token: str, trefwoord: str) -> list[dict]:
        """Paginageer door alle resultaten voor één trefwoord."""
        results: list[dict] = []
        pagina = 0
        while True:
            criteria = self._build_criteria(trefwoord, pagina)
            res = page.evaluate(_FETCH_JS, [criteria, token])
            if res.get("status") != 200 or not res.get("data"):
                log.warning("[vdab] zoek-call gaf status %s (pagina %d)",
                            res.get("status"), pagina)
                break
            data = res["data"]
            batch = data.get("resultaten", [])
            results.extend(batch)
            total = data.get("totaalAantal", 0)
            if self.max_results and len(results) >= self.max_results:
                return results[: self.max_results]
            if len(results) >= total or not batch:
                break
            pagina += 1
        return results

    def _build_criteria(self, trefwoord: str, pagina: int) -> dict:
        return {
            "criteria": {
                "trefwoord": trefwoord,
                "diplomaCodes": [],
                "onlineSindsCode": "9000",
                "arbeidsduurCodes": ["D"] if self.deeltijds else [],
                "arbeidsregimeCodes": [],
                "contractTypeCodes": [],
                "jobdomeinCodes": [],
                "internationaalCodes": [],
                "beroepCodes": [],
                "ervaringCodes": [],
                "rijbewijsCodes": [],
                "locatieCriteria": {
                    "locatiePostcodeGemeente": self.locatie_naam,
                    "locatieCode": self.locatie_code,
                    "straalInKilometer": None,
                    "geoLocatie": {"latitude": None, "longitude": None},
                },
                "attestCodes": [],
                "taalCriteria": {"taalSelecties": []},
                "sorteerVeld": "STANDAARD",
            },
            "pagina": pagina,
            "zoekmodus": "C2",
            "paginaGrootte": self.page_size,
        }

    def _to_raw(self, vid: int, item: dict) -> RawJob:
        functie = item.get("vacaturefunctie", {})
        title = functie.get("naam", "").strip()
        circuit = functie.get("arbeidscircuitLijn", "") or ""
        location = (item.get("tewerkstellingsLocatieRegioOfAdres") or "").title()
        ervaring = item.get("ervaring", "") or ""

        return RawJob(
            title=title,
            url=DETAIL_URL.format(id=vid),
            source=self.name,
            profile=self.profile,
            employer=item.get("vacatureBedrijfsnaam"),
            location=location,
            volume="deeltijds" if self.deeltijds else None,
            contract=_normalize_contract(circuit),
            posted_at=item.get("eerstePublicatieDatum"),
            raw_text=f"{title}. {circuit}. {ervaring}.",
            extra={"knelpuntberoep": item.get("knelpuntberoep")},
        )


class VdabOverheidSource(VdabSource):
    """VDAB-variant voor IT-jobs bij de overheid (vdab.be/.../it-jobs-overheid).

    Zelfde Playwright-machinerie als de basis-VDAB-bron, maar zoekt op
    'ICT overheid' (levert POLITIE, De Lijn, OVAM, lokale besturen…) en niet
    enkel deeltijds — voltijdse overheids-IT blijft zo zichtbaar in Profiel A.
    """

    name = "vdab-overheid"

    def __init__(self, **kwargs):
        kwargs.setdefault("trefwoorden", ("ICT overheid",))
        kwargs.setdefault("deeltijds", False)
        super().__init__(**kwargs)


# Titel-trefwoorden voor de uit te sluiten sectoren (genormaliseerd: lowercase,
# accenten/leestekens weg). Bewust ruim — de bron wil enkel "unieke" rollen
# overhouden, geen mainstream kantoor-/zorg-/verkoop-functies.
_DIVERSE_BLOCK = (
    # aankoop
    "aankoop", "aankoper", "inkoop", "inkoper", "purchaser", "buyer",
    # administratie
    "administrat", "secretari", "bediende", "onthaal", "receptie", "receptionist",
    "data entry", "office manager", "office assistant", "management assistant",
    "dossierbeheer", "klassement", "back office", "administration",
    # communicatie
    "communicatie", "communications", "woordvoerder",
    # dienstverlening
    "dienstverlening", "klantendienst", "klantenservice", "customer", "helpdesk",
    "servicedesk", "callcenter", "call center", "baliemedewerker", "telefonist",
    # financieel
    "financ", "boekhoud", "accountant", "comptab", "payroll", "controller",
    "fiscaal", "fiscalist", "krediet", "treasury",
    # gezondheid
    "gezondheid", "verpleeg", "arts", "apotheek", "apotheker", "medisch",
    "medical", "tandarts", "radiolog", "kinesi", "kine ", "ergotherap",
    "audiolo", "audicien", "mondhygien", "psycholoog", "psycholog", "psychiatr",
    "psychotherap", "logoped", "dietist", "podolog", "optometr", "opticien",
    "vroedvrouw", "mondzorg", "orthopedagoog",
    # horeca
    "horeca", "kok ", "kelner", "barman", "barvrouw", "keuken", "afwas",
    "zaalmedewerker", "barista", "frituur", "catering", "fastfood", "restaurant",
    "brasserie", "pizzeria", "buffet", "tearoom",
    # human resources
    "human resources", "rekruter", "recruit", "talent acquisition",
    "personeelsdienst", "personeelsmedewerker", "hr business", "hr officer",
    "hr medewerker",
    # juridisch
    "juridisch", "jurist", "legal", "advocaat", "notaris", "paralegal",
    # management
    "manager", "management", "directeur", "afdelingshoofd", "diensthoofd",
    "teamleider", "teamleader", "shiftleader", "shift leader", "leidinggevend",
    "afdelingsverantwoordelijk", "floor manager", "store manager",
    # marketing
    "marketing", "seo ", "social media", "campagne", "copywriter",
    # onderhoud
    "onderhoud", "schoonmaak", "schoonmak", "poets", "cleaning", "huishoud",
    "klusjes", "ramenwasser", "ruitenwasser", "glazenwasser",
    # verkoop
    "verkoop", "verkoper", "verkoopster", "sales", "winkel", "retail", "shop",
    "kassa", "vertegenwoordig", "accountmanager", "account manager", "vendor",
    "showroom",
    # zorg / welzijn
    "zorg", "verzorg", "begeleid", "opvoeder", "kinderbegeleid", "onthaalouder",
    "animator", "maatschappelijk werk", "thuishulp", "poetshulp", "welzijn",
    "woonassistent", "ondersteun", "inclusiecoach", "palliatie", "leefgroep",
    "zorgkundige",
)


class VdabDeeltijdsSource(VdabSource):
    """VDAB-bron voor *algemene* deeltijdse jobs — enkel de 'unieke' soorten.

    Haalt een begrensd aantal deeltijdse vacatures (regio Antwerpen) en filtert
    de mainstream sectoren weg (aankoop, administratie, communicatie,
    dienstverlening, financieel, gezondheid, horeca, HR, juridisch, management,
    marketing, onderhoud, verkoop, zorg) zodat enkel distinctieve rollen
    overblijven (bv. lesgever, technieker, labo, creatief, productie…).

    Opmerking: de VDAB-respons bevat geen remote/telewerk-indicatie, dus de
    'liefst remote'-voorkeur kan hier niet hard worden afgedwongen; remote wordt
    al gedekt door de Profiel-B-bronnen. Telewerk-titels worden wel getagd.
    """

    name = "vdab-deeltijds"

    def __init__(self, **kwargs):
        kwargs.setdefault("trefwoorden", ("",))
        kwargs.setdefault("deeltijds", True)
        kwargs.setdefault("max_results", 250)
        super().__init__(**kwargs)

    def fetch(self) -> list[RawJob]:
        jobs = super().fetch()
        kept = [
            job for job in jobs
            if not any(term in normalize_key(f"{job.title} {job.raw_text}")
                       for term in _DIVERSE_BLOCK)
        ]
        log.info("[vdab-deeltijds] %d unieke deeltijdse jobs (van %d na sector-filter)",
                 len(kept), len(jobs))
        return kept


def _normalize_contract(circuit: str) -> str | None:
    """Map VDAB-arbeidscircuit naar een term die de scoring herkent."""
    c = circuit.lower()
    if not c:
        return None
    if "optie vast" in c:
        return "tijdelijk met optie vast"
    if "vast" in c:  # "Vaste job"
        return "onbepaalde duur"
    if "tijdelijk" in c or "bepaalde duur" in c:
        return "tijdelijk"
    return circuit
