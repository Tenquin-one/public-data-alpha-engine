from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .db import PROJECT_ROOT
from .utils import utc_now


DEFAULT_EXPORT_ROOT = PROJECT_ROOT / "data" / "exports"


def _write_csv(path: Path, rows: Iterable[sqlite3.Row]) -> int:
    materialized = [dict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(materialized[0]) if materialized else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(materialized)
    return len(materialized)


def export_initial_results(
    conn: sqlite3.Connection,
    output_root: Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    queries = {
        "initial_scores.csv": """
            SELECT d.dataset_id, d.title, d.provider, d.public_status,
                   d.update_frequency, d.license, d.rights_status,
                   a.pra_score, a.ephemeral_score, a.seed_score,
                   a.recommendation, a.calculated_at, d.source_url
            FROM datasets d
            JOIN alpha_scores a
              ON a.candidate_type='DATASET' AND a.candidate_id=d.dataset_id
            ORDER BY a.seed_score DESC, a.pra_score DESC
        """,
        "seed_queue.csv": """
            SELECT q.queue_id, q.dataset_id, d.title, q.seed_score,
                   q.rights_ok, q.low_cost, q.decision, q.reason,
                   q.collector_id, q.updated_at
            FROM seed_queue q
            JOIN datasets d ON d.dataset_id=q.dataset_id
            ORDER BY q.seed_score DESC
        """,
        "pre_release_signals.csv": """
            SELECT p.signal_id, p.title, p.buyer_org, p.notice_type,
                   p.posted_at, a.pra_score, a.recommendation,
                   p.first_seen_at, p.last_seen_at, p.source_url
            FROM pre_release_signals p
            LEFT JOIN alpha_scores a
              ON a.candidate_type='SIGNAL' AND a.candidate_id=p.signal_id
            ORDER BY a.pra_score DESC, p.posted_at DESC
        """,
        "seoul_seed_places.csv": """
            SELECT place_id, area_code, area_name, cohort, enabled,
                   commercial_available, rationale, source_url
            FROM place_registry
            ORDER BY place_id
        """,
    }
    counts: dict[str, int] = {}
    for filename, query in queries.items():
        counts[filename] = _write_csv(output_root / filename, conn.execute(query))
    manifest = {
        "exported_at": utc_now(),
        "database": str(conn.execute("PRAGMA database_list").fetchone()[2]),
        "files": counts,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
