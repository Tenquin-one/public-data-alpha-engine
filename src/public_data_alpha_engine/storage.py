from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import PROJECT_ROOT
from .utils import canonical_json, sha256_bytes, slug, utc_now


@dataclass(frozen=True)
class StoredPayload:
    payload_id: int
    content_hash: str
    raw_path: str | None
    is_duplicate: bool
    byte_count: int


def store_raw_payload(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    source_url: str,
    payload: bytes | str | dict[str, Any] | list[Any],
    query_params: dict[str, Any] | None = None,
    source_timestamp: str | None = None,
    mime_type: str = "application/json",
    run_id: int | None = None,
    collected_at: str | None = None,
    raw_root: Path | None = None,
) -> StoredPayload:
    collected_at = collected_at or utc_now()
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = canonical_json(payload).encode("utf-8")
    content_hash = sha256_bytes(raw)
    previous = conn.execute(
        """
        SELECT payload_id, raw_path, byte_count FROM raw_payloads
        WHERE source_id=? AND content_hash=?
        ORDER BY payload_id DESC LIMIT 1
        """,
        (source_id, content_hash),
    ).fetchone()
    duplicate = previous is not None
    rel_path: str | None = previous["raw_path"] if duplicate else None
    byte_count = int(previous["byte_count"]) if duplicate else 0
    if not duplicate:
        root = raw_root or (PROJECT_ROOT / "data" / "raw")
        date_part = datetime.fromisoformat(collected_at).date().isoformat()
        suffix = ".json.gz" if "json" in mime_type else ".xml.gz" if "xml" in mime_type else ".bin.gz"
        path = root / slug(source_id) / date_part / f"{content_hash}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        stored_bytes = gzip.compress(raw, compresslevel=6, mtime=0)
        byte_count = len(stored_bytes)
        path.write_bytes(stored_bytes)
        try:
            rel_path = str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            rel_path = str(path)
    cursor = conn.execute(
        """
        INSERT INTO raw_payloads(
            source_id, run_id, collected_at, source_url, query_params_json,
            source_timestamp, content_hash, raw_path, byte_count, mime_type,
            is_duplicate, previous_payload_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            run_id,
            collected_at,
            source_url,
            canonical_json(query_params or {}),
            source_timestamp,
            content_hash,
            rel_path,
            byte_count,
            mime_type,
            int(duplicate),
            previous["payload_id"] if previous else None,
        ),
    )
    return StoredPayload(
        cursor.lastrowid,
        content_hash,
        rel_path,
        duplicate,
        byte_count,
    )


def load_normalized_json(row: sqlite3.Row, field: str = "metadata_json") -> dict[str, Any]:
    return json.loads(row[field] or "{}")
