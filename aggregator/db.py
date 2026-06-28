"""SQLite-persistentie voor jobs. Idempotent upsert + "nieuw sinds vorige run"."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .models import Job, now_iso

DEFAULT_DB_PATH = "jobs.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    source      TEXT NOT NULL,
    profile     TEXT NOT NULL,
    employer    TEXT,
    location    TEXT,
    volume      TEXT,
    contract    TEXT,
    posted_at   TEXT,
    raw_text    TEXT,
    flags       TEXT,          -- JSON array
    score       INTEGER DEFAULT 0,
    score_reason TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    profile   TEXT,
    n_seen    INTEGER DEFAULT 0,
    n_new     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_profile ON jobs(profile);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen);
"""


class Database:
    def __init__(self, path: str = DEFAULT_DB_PATH):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True) if Path(path).parent != Path("") else None
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def upsert_job(self, job: Job) -> bool:
        """Schrijf job weg. Geeft True terug als hij nieuw is (eerste keer gezien)."""
        with self._conn() as conn:
            return self._upsert_on_conn(conn, job, now_iso())

    def upsert_jobs(self, jobs: list[Job]) -> set[str]:
        """Upsert een batch in één transactie. Geeft de ids van nieuwe jobs terug.

        Veel sneller dan per job `upsert_job` aanroepen: één connectie/commit
        i.p.v. open/commit/close per vacature.
        """
        ts = now_iso()
        new_ids: set[str] = set()
        with self._conn() as conn:
            for job in jobs:
                if self._upsert_on_conn(conn, job, ts):
                    new_ids.add(job.id)
        return new_ids

    @staticmethod
    def _upsert_on_conn(conn: sqlite3.Connection, job: Job, ts: str) -> bool:
        """Upsert één job op een bestaande connectie. True als hij nieuw is."""
        row = conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,)).fetchone()
        is_new = row is None
        if is_new:
            job.first_seen = ts
            job.last_seen = ts
            conn.execute(
                """INSERT INTO jobs
                   (id, title, url, source, profile, employer, location, volume,
                    contract, posted_at, raw_text, flags, score, score_reason,
                    first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job.id, job.title, job.url, job.source, job.profile,
                    job.employer, job.location, job.volume, job.contract,
                    job.posted_at, job.raw_text, json.dumps(job.flags),
                    job.score, job.score_reason, job.first_seen, job.last_seen,
                ),
            )
        else:
            # Bestaande job: refresh last_seen + velden die kunnen wijzigen.
            job.last_seen = ts
            conn.execute(
                """UPDATE jobs SET title=?, url=?, employer=?, location=?, volume=?,
                   contract=?, posted_at=?, raw_text=?, flags=?, score=?,
                   score_reason=?, last_seen=? WHERE id=?""",
                (
                    job.title, job.url, job.employer, job.location, job.volume,
                    job.contract, job.posted_at, job.raw_text, json.dumps(job.flags),
                    job.score, job.score_reason, job.last_seen, job.id,
                ),
            )
        return is_new

    def record_run(self, profile: Optional[str], n_seen: int, n_new: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO runs (started_at, profile, n_seen, n_new) VALUES (?,?,?,?)",
                (now_iso(), profile, n_seen, n_new),
            )

    def last_run_at(self, profile: Optional[str] = None) -> Optional[str]:
        """Tijdstip van de vorige run (vóór degene die nu loopt), evt. per profiel."""
        with self._conn() as conn:
            if profile:
                row = conn.execute(
                    "SELECT started_at FROM runs WHERE profile = ? OR profile IS NULL "
                    "ORDER BY id DESC LIMIT 1",
                    (profile,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT started_at FROM runs ORDER BY id DESC LIMIT 1"
                ).fetchone()
            return row["started_at"] if row else None

    def get_jobs(
        self, profile: Optional[str] = None, since: Optional[str] = None
    ) -> list[Job]:
        """Haal jobs op, optioneel per profiel en/of voor het eerst gezien sinds `since`."""
        clauses, params = [], []
        if profile:
            clauses.append("profile = ?")
            params.append(profile)
        if since:
            clauses.append("first_seen >= ?")
            params.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs{where} ORDER BY score DESC, last_seen DESC", params
            ).fetchall()
        return [_row_to_job(r) for r in rows]


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        source=row["source"],
        profile=row["profile"],
        employer=row["employer"],
        location=row["location"],
        volume=row["volume"],
        contract=row["contract"],
        posted_at=row["posted_at"],
        raw_text=row["raw_text"] or "",
        flags=json.loads(row["flags"]) if row["flags"] else [],
        score=row["score"],
        score_reason=row["score_reason"] or "",
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
    )
