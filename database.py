"""SQLite storage for PartFinder.

SQLite is used as the local store for the bundled seed dataset. It is
intentionally isolated behind this small module so it can later be swapped for
Postgres or another store without touching the rest of the application.

Seed listings store a ``days_ago`` offset rather than an absolute date, so the
data always looks fresh (within the two-week window) no matter when the database
was built.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from typing import List, Optional

from models import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seed_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    company         TEXT    NOT NULL,
    location        TEXT    NOT NULL,
    latitude        REAL,
    longitude       REAL,
    pay             TEXT,
    salary_min      REAL,
    salary_max      REAL,
    employment_type TEXT    NOT NULL,
    days_ago        INTEGER NOT NULL,
    source          TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    description     TEXT,
    category        TEXT
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str, seed_path: str, force: bool = False) -> None:
    """Create the schema and load seed data if the table is empty.

    Args:
        db_path: Path to the SQLite database file.
        seed_path: Path to the JSON seed dataset.
        force: When True, existing seed rows are cleared and reloaded.
    """
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        if force:
            conn.execute("DELETE FROM seed_jobs")
            conn.commit()

        (count,) = conn.execute("SELECT COUNT(*) FROM seed_jobs").fetchone()
        if count == 0:
            _load_seed(conn, seed_path)
    finally:
        conn.close()


def _load_seed(conn: sqlite3.Connection, seed_path: str) -> None:
    """Populate ``seed_jobs`` from the JSON seed file (if present)."""
    if not os.path.exists(seed_path):
        return
    with open(seed_path, "r", encoding="utf-8") as handle:
        rows = json.load(handle)

    conn.executemany(
        """
        INSERT INTO seed_jobs (
            title, company, location, latitude, longitude, pay, salary_min,
            salary_max, employment_type, days_ago, source, url, description, category
        ) VALUES (
            :title, :company, :location, :latitude, :longitude, :pay, :salary_min,
            :salary_max, :employment_type, :days_ago, :source, :url, :description, :category
        )
        """,
        [_seed_defaults(row) for row in rows],
    )
    conn.commit()


def _seed_defaults(row: dict) -> dict:
    """Ensure every optional seed key exists so executemany binds cleanly."""
    defaults = {
        "latitude": None,
        "longitude": None,
        "pay": None,
        "salary_min": None,
        "salary_max": None,
        "description": "",
        "category": None,
    }
    defaults.update(row)
    return defaults


def _row_to_job(row: sqlite3.Row, reference: Optional[date] = None) -> Job:
    """Convert a seed row into a :class:`Job`, computing the posted date."""
    reference = reference or date.today()
    posted = reference - timedelta(days=int(row["days_ago"]))
    return Job(
        title=row["title"],
        company=row["company"],
        location=row["location"],
        pay=row["pay"] or "Not specified",
        employment_type=row["employment_type"],
        posted=posted,
        source=row["source"],
        url=row["url"],
        description=row["description"] or "",
        latitude=row["latitude"],
        longitude=row["longitude"],
        category=row["category"],
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
    )


def fetch_seed_jobs(
    db_path: str,
    source: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Job]:
    """Return seed jobs, optionally filtered by source and/or category.

    Distance and source reliability are left for the calling provider/pipeline
    to populate, keeping this module purely about storage.
    """
    conn = get_connection(db_path)
    try:
        clauses = []
        params: list = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(f"SELECT * FROM seed_jobs{where}", params).fetchall()
        return [_row_to_job(row) for row in rows]
    finally:
        conn.close()
