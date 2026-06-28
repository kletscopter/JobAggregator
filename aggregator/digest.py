"""Digest-output: gesorteerde markdown met score + reden + link."""

from __future__ import annotations

import logging
from collections import defaultdict

from .models import PROFILE_A, PROFILE_B, Job, now_iso

log = logging.getLogger(__name__)

PROFILE_TITLES = {
    PROFILE_A: "Profiel A — Belgische deeltijdse loondienst (Antwerpen)",
    PROFILE_B: "Profiel B — Remote tech / crypto",
}


def write_digest(
    jobs: list[Job],
    path: str = "digest.md",
    new_ids: set[str] | None = None,
) -> None:
    """Schrijf een markdown-digest, gegroepeerd per profiel, gesorteerd op score.

    `new_ids`: ids van vacatures die nieuw zijn deze run → krijgen een 🆕-markering.
    """
    new_ids = new_ids or set()
    by_profile: dict[str, list[Job]] = defaultdict(list)
    for job in jobs:
        by_profile[job.profile].append(job)

    lines: list[str] = [
        "# Vacature-digest",
        "",
        f"_Gegenereerd: {now_iso()} — {len(jobs)} vacatures, "
        f"{len(new_ids)} nieuw sinds vorige run._",
        "",
    ]

    for profile in (PROFILE_A, PROFILE_B):
        group = sorted(by_profile.get(profile, []), key=lambda j: j.score, reverse=True)
        if not group:
            continue
        n_new = sum(1 for j in group if j.id in new_ids)
        lines.append(f"## {PROFILE_TITLES.get(profile, profile)} ({len(group)}, {n_new} nieuw)")
        lines.append("")
        for job in group:
            lines.extend(_render_job(job, is_new=job.id in new_ids))
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    log.info("Digest geschreven naar %s (%d jobs)", path, len(jobs))


def _render_job(job: Job, is_new: bool) -> list[str]:
    new_marker = "🆕 " if is_new else ""
    title = job.title.strip() or "(geen titel)"
    header = f"### {new_marker}[{job.score:+d}] {title}"

    meta_bits = [b for b in (
        job.employer,
        job.location,
        job.volume,
    ) if b]
    meta = " · ".join(meta_bits)

    flag_str = " ".join(f"`{f}`" for f in job.flags) if job.flags else ""

    lines = [header, ""]
    if meta:
        lines.append(f"- {meta}")
    lines.append(f"- Bron: {job.source}" + (f" · {job.posted_at}" if job.posted_at else ""))
    if job.score_reason:
        lines.append(f"- Score: {job.score_reason}")
    if flag_str:
        lines.append(f"- Flags: {flag_str}")
    lines.append(f"- [Bekijk vacature]({job.url})")
    lines.append("")
    return lines
