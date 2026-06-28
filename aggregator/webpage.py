"""Genereer een zelfstandige, filterbare HTML-pagina met alle vacatures.

De pagina bevat de data embedded als JSON en filtert/sorteert client-side
(geen server nodig — gewoon `digest.html` openen in de browser). Wordt elke
run mee gegenereerd, net als digest.md.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from .models import Job, now_iso

log = logging.getLogger(__name__)

PROFILE_LABELS = {"a": "Profiel A — BE deeltijds", "b": "Profiel B — Remote tech"}


def write_html(
    jobs: list[Job],
    path: str = "digest.html",
    new_ids: set[str] | None = None,
) -> None:
    new_ids = new_ids or set()
    payload = []
    for j in jobs:
        d = asdict(j)
        d["is_new"] = j.id in new_ids
        d.pop("raw_text", None)  # te lang voor de UI
        payload.append(d)

    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    sources = sorted({j.source for j in jobs})
    html = _TEMPLATE.format(
        generated=now_iso(),
        total=len(jobs),
        n_new=len(new_ids),
        data=data_json,
        source_options="".join(f'<option value="{s}">{s}</option>' for s in sources),
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    log.info("HTML-pagina geschreven naar %s (%d jobs)", path, len(jobs))


_TEMPLATE = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vacature-digest</title>
<style>
  :root {{ --bg:#0f1117; --card:#1a1d27; --muted:#8b93a7; --line:#2a2e3a;
           --good:#3fb950; --bad:#f85149; --accent:#58a6ff; --chip:#262b38; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
          background:var(--bg); color:#e6edf3; }}
  header {{ padding:18px 24px; border-bottom:1px solid var(--line); position:sticky; top:0;
            background:var(--bg); z-index:10; }}
  h1 {{ margin:0 0 4px; font-size:20px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .bar {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; align-items:center; }}
  .bar input, .bar select {{ background:var(--card); color:#e6edf3; border:1px solid var(--line);
            border-radius:8px; padding:7px 10px; font-size:13px; }}
  .bar input[type=search] {{ min-width:220px; }}
  .bar label {{ font-size:13px; color:var(--muted); display:flex; align-items:center; gap:6px; }}
  main {{ padding:18px 24px; max-width:1000px; margin:0 auto; }}
  .count {{ color:var(--muted); font-size:13px; margin-bottom:12px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:14px 16px; margin-bottom:12px; }}
  .card.new {{ border-color:var(--accent); }}
  .row1 {{ display:flex; align-items:baseline; gap:10px; }}
  .score {{ font-weight:700; font-size:15px; min-width:34px; }}
  .score.pos {{ color:var(--good); }} .score.neg {{ color:var(--bad); }}
  .title {{ font-size:15px; font-weight:600; }}
  .title a {{ color:#e6edf3; text-decoration:none; }}
  .title a:hover {{ color:var(--accent); text-decoration:underline; }}
  .new-badge {{ background:var(--accent); color:#0b1020; font-size:11px; font-weight:700;
               border-radius:6px; padding:1px 6px; }}
  .meta {{ color:var(--muted); font-size:13px; margin:6px 0 0; }}
  .meta b {{ color:#c9d1d9; font-weight:600; }}
  .reason {{ color:var(--muted); font-size:12px; margin-top:6px; font-style:italic; }}
  .chips {{ margin-top:8px; display:flex; flex-wrap:wrap; gap:6px; }}
  .chip {{ background:var(--chip); border:1px solid var(--line); color:#c9d1d9; font-size:11px;
           border-radius:20px; padding:2px 9px; }}
  .chip.front_facing {{ color:var(--bad); border-color:var(--bad); }}
  .chip.autonomous {{ color:var(--good); border-color:var(--good); }}
  .chip.stack {{ color:#d29922; border-color:#d29922; }}
  .empty {{ color:var(--muted); text-align:center; padding:40px; }}
</style>
</head>
<body>
<header>
  <h1>Vacature-digest</h1>
  <div class="sub">Gegenereerd {generated} · {total} vacatures · {n_new} nieuw sinds vorige run</div>
  <div class="bar">
    <input type="search" id="q" placeholder="Zoek titel / werkgever / locatie…">
    <select id="profile">
      <option value="">Alle profielen</option>
      <option value="a">Profiel A — BE deeltijds</option>
      <option value="b">Profiel B — Remote tech</option>
    </select>
    <select id="source"><option value="">Alle bronnen</option>{source_options}</select>
    <label>min. score <input type="number" id="minscore" value="" style="width:64px"></label>
    <label><input type="checkbox" id="newonly"> enkel nieuw</label>
    <label><input type="checkbox" id="nofront"> verberg front-facing</label>
    <select id="sort">
      <option value="score">Sorteer: score</option>
      <option value="new">Sorteer: nieuw eerst</option>
      <option value="title">Sorteer: titel</option>
    </select>
  </div>
</header>
<main>
  <div class="count" id="count"></div>
  <div id="list"></div>
</main>
<script>
const JOBS = {data};
const PROFILE_LABELS = {{a:"Profiel A", b:"Profiel B"}};
const $ = id => document.getElementById(id);

function chipClass(f) {{
  if (f.startsWith("front_facing")) return "chip front_facing";
  if (f.startsWith("autonomous")) return "chip autonomous";
  if (f.startsWith("stack_gap")) return "chip stack";
  return "chip";
}}

function render() {{
  const q = $("q").value.toLowerCase().trim();
  const prof = $("profile").value, src = $("source").value;
  const minScore = $("minscore").value === "" ? null : Number($("minscore").value);
  const newOnly = $("newonly").checked, noFront = $("nofront").checked;
  const sort = $("sort").value;

  let rows = JOBS.filter(j => {{
    if (prof && j.profile !== prof) return false;
    if (src && j.source !== src) return false;
    if (minScore !== null && j.score < minScore) return false;
    if (newOnly && !j.is_new) return false;
    if (noFront && j.flags.some(f => f.startsWith("front_facing"))) return false;
    if (q) {{
      const hay = (j.title+" "+(j.employer||"")+" "+(j.location||"")).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});

  rows.sort((a,b) => {{
    if (sort === "title") return a.title.localeCompare(b.title);
    if (sort === "new") return (b.is_new-a.is_new) || (b.score-a.score);
    return b.score - a.score;
  }});

  $("count").textContent = rows.length + " van " + JOBS.length + " vacatures";
  $("list").innerHTML = rows.length ? rows.map(card).join("") :
    '<div class="empty">Geen vacatures voor deze filters.</div>';
}}

function card(j) {{
  const cls = j.score >= 0 ? "pos" : "neg";
  const meta = [j.employer, j.location, j.volume, j.contract].filter(Boolean)
    .map(x => "<b>"+esc(x)+"</b>").join(" · ");
  const chips = j.flags.map(f => '<span class="'+chipClass(f)+'">'+esc(f)+'</span>').join("");
  return `<div class="card ${{j.is_new?'new':''}}">
    <div class="row1">
      <span class="score ${{cls}}">${{j.score>=0?'+':''}}${{j.score}}</span>
      <span class="title"><a href="${{esc(j.url)}}" target="_blank" rel="noopener">${{esc(j.title)}}</a></span>
      ${{j.is_new?'<span class="new-badge">NIEUW</span>':''}}
    </div>
    <div class="meta">${{meta}} · <span style="color:var(--accent)">${{esc(j.source)}}</span>
      · ${{PROFILE_LABELS[j.profile]||j.profile}}</div>
    ${{j.score_reason?'<div class="reason">'+esc(j.score_reason)+'</div>':''}}
    ${{chips?'<div class="chips">'+chips+'</div>':''}}
  </div>`;
}}

function esc(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
}}

["q","profile","source","minscore","newonly","nofront","sort"].forEach(id =>
  $(id).addEventListener("input", render));
render();
</script>
</body>
</html>
"""
