from __future__ import annotations

import sqlite3
from pathlib import Path

from .utils import utc_now


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "alpha_engine.sqlite"
SCHEMA_PATH = PROJECT_ROOT / "schema.sql"


class ManagedConnection(sqlite3.Connection):
    """Transaction context manager that also releases the database handle."""

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc_value, traceback))
        finally:
            self.close()


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, factory=ManagedConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def upsert_source(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    name: str,
    source_type: str,
    base_url: str,
    cadence_seconds: int | None,
    rights_status: str,
    terms_memo: str,
    active: bool = True,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO sources(
            source_id, name, source_type, base_url, cadence_seconds,
            rights_status, terms_memo, active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            name=excluded.name,
            source_type=excluded.source_type,
            base_url=excluded.base_url,
            cadence_seconds=excluded.cadence_seconds,
            rights_status=excluded.rights_status,
            terms_memo=excluded.terms_memo,
            active=excluded.active,
            updated_at=excluded.updated_at
        """,
        (
            source_id,
            name,
            source_type,
            base_url,
            cadence_seconds,
            rights_status,
            terms_memo,
            int(active),
            now,
            now,
        ),
    )


def integrity(conn: sqlite3.Connection) -> tuple[str, int]:
    check = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk_count = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    return check, fk_count
