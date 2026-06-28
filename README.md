# Job Aggregator

Dagelijkse vacature-digest voor twee parallelle zoekprofielen:

- **Profiel A** — Belgische deeltijdse loondienst (regio Antwerpen). ✅ halftijds.be + werkenbijdeoverheid.be (lokale besturen / Pidpa / IGEAN) + VDAB (deeltijdse ICT-coördinator).
- **Profiel B** — Remote tech / crypto. ✅ Remotive (JSON) + We Work Remotely (RSS).

## Status (MVP-voortgang)

| Stap | Onderdeel | Status |
|------|-----------|--------|
| 1 | `Job`/`RawJob` dataclasses + SQLite + dedup | ✅ |
| 2 | Remotive (JSON) + WWR (RSS) | ✅ |
| 3 | halftijds.be scraper | ✅ |
| 5 | werkenbijdeoverheid.be (lokale besturen) | ✅ |
| 6 | Scoring + flags + digest-output | ✅ |
| 4 | VDAB scraper (Playwright) | ✅ |
| + | Webpagina (filterbare HTML) | ✅ |
| 7 | (optioneel) Telegram-notificatie | ⬜ (niet gewenst) |

## Installatie

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium   # nodig voor de VDAB-bron
```

## Gebruik

```powershell
.venv\Scripts\python.exe aggregator.py              # alle profielen
.venv\Scripts\python.exe aggregator.py --profile b  # enkel remote tech
.venv\Scripts\python.exe aggregator.py --new-only   # enkel nieuw sinds vorige run
.venv\Scripts\python.exe aggregator.py -v           # debug-logging
```

Output:
- **`digest.html`** — zelfstandige, **filterbare webpagina** (open in je browser;
  geen server nodig). Filter op profiel, bron, min. score, enkel-nieuw,
  verberg front-facing; zoek en sorteer client-side.
- `digest.md` — gesorteerde digest per profiel, met score + reden + flags + link
  (nieuwe vacatures gemarkeerd met 🆕).
- `jobs.json` — genormaliseerde vacatures (debug/export).
- `jobs.db` — SQLite, voor idempotentie + "nieuw sinds vorige run".

Extra vlaggen: `--keep-small` (filter kleine/voltijdse Profiel-A-rollen niet weg,
enkel taggen), `--no-fuzzy`, `--digest PAD`, `--json PAD`, `--html PAD`.

### VDAB (Playwright)

VDAB laadt vacatures client-side en de interne API
(`/rest/vindeenjob/v4/vacatureLight/zoek`) zit achter een gateway die elke
non-browser request met 403 weigert; de SPA voegt per sessie een anti-bot header
`vej-key-monitor` toe. De bron laadt daarom de zoekpagina één keer in een
headless Chromium, vangt die token op en roept de JSON-API aan via `fetch()`
binnen de browsercontext. Standaard zoekt hij op **"ICT-coördinator" + deeltijds
+ provincie Antwerpen** (configureerbaar in [vdab.py](aggregator/sources/vdab.py)).
Zonder Playwright/Chromium wordt de bron netjes overgeslagen (de rest blijft werken).

## Architectuur

```
aggregator.py            CLI-entry
aggregator/
  models.py              RawJob (ruw) + Job (genormaliseerd) + id/dedup-helpers
  db.py                  SQLite-persistentie, idempotente upsert, run-historiek
  dedup.py               exacte (id) + optionele fuzzy dedup (rapidfuzz)
  scoring.py             volume-parsing, flags + gewogen score met reden
  digest.py              markdown-digest (per profiel, gesorteerd op score)
  webpage.py             zelfstandige filterbare HTML-pagina (client-side JS)
  pipeline.py            fetch → dedup → score/filter → persist (robuust per bron)
  sources/
    base.py              Source-basisklasse (UA, throttle, get/post-helper)
    halftijds.py         halftijds.be (Squarespace events)   (profiel A)
    werkenbijdeoverheid.py  lokale besturen via RSS-export    (profiel A)
    vdab.py              VDAB via Playwright (headless browser)  (profiel A)
    remotive.py          Remotive JSON API   (profiel B)
    wwr.py               We Work Remotely RSS (profiel B)
```

Elke bron levert `RawJob`'s via `fetch()`; één kapotte bron stopt de run niet.
Jobs krijgen een stabiele `id` uit `(titel + werkgever + locatie)` zodat
meermaals draaien op een dag geen duplicaten oplevert.

## Cron (later)

1× 's ochtends, bv. via Windows Task Scheduler of cron op een VPS.
