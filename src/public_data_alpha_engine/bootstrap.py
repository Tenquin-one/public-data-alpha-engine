from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from .collectors.seoul_city import register as register_seoul_collector
from .db import PROJECT_ROOT, init_db, upsert_source
from .prerelease import PreReleaseSignal, link_signals_to_datasets, upsert_signals
from .registry import mirror_records, normalize_record
from .scoring import score_all, set_override


SEED_ROOT = PROJECT_ROOT / "data" / "seed"


SOURCES = (
    {
        "source_id": "data_go_registry",
        "name": "공공데이터포털 현재 개방목록",
        "source_type": "REGISTRY",
        "base_url": "https://api.odcloud.kr/api/15077093/v1/dataset",
        "cadence_seconds": 86400,
        "rights_status": "ALLOW",
        "terms_memo": "목록조회서비스는 무료이며 이용허락범위 제한 없음. 실시간 메타데이터지만 일 1회면 충분.",
    },
    {
        "source_id": "data_go_planned",
        "name": "범정부 미제공·개방예정 데이터 목록",
        "source_type": "PLANNED_REGISTRY",
        "base_url": "https://www.data.go.kr/data/15127106/fileData.do",
        "cadence_seconds": 604800,
        "rights_status": "ALLOW",
        "terms_memo": "연간 갱신·이용허락범위 제한 없음. 계획은 기관 사정에 따라 변경될 수 있음.",
    },
    {
        "source_id": "nia_procurement",
        "name": "NIA 입찰공고·사전규격",
        "source_type": "PRE_RELEASE_WATCHER",
        "base_url": "https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=78336",
        "cadence_seconds": 86400,
        "rights_status": "METADATA_ONLY",
        "terms_memo": "공개 게시물의 제목·기관·일자·URL만 변화 탐지용 메타데이터로 저장. 첨부 RFP 전체는 기본 수집하지 않음.",
    },
    {
        "source_id": "seoul_open_data",
        "name": "서울 열린데이터광장 메타데이터",
        "source_type": "OFFICIAL_REGISTRY",
        "base_url": "https://data.seoul.go.kr/",
        "cadence_seconds": 86400,
        "rights_status": "ALLOW",
        "terms_memo": "서울 실시간 도시·상권 데이터는 공공누리 1유형(출처표시, 상업 이용·변경 가능).",
    },
    {
        "source_id": "seoul_open_data_realtime_city",
        "name": "서울 실시간 도시데이터 API",
        "source_type": "SNAPSHOT_COLLECTOR",
        "base_url": "http://openapi.seoul.go.kr:8088",
        "cadence_seconds": 900,
        "rights_status": "ALLOW",
        "terms_memo": "15분 cadence, 8곳 cohort, 하루 768회. API 키는 저장하지 않고 환경변수만 사용.",
    },
)


def _read_json(name: str) -> Any:
    return json.loads((SEED_ROOT / name).read_text(encoding="utf-8"))


def bootstrap(conn: sqlite3.Connection) -> dict[str, int]:
    init_db(conn)
    for source in SOURCES:
        upsert_source(conn, **source)

    registry_rows = _read_json("initial_registry.json")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in registry_rows:
        grouped[row["source_id"]].append(row)
    dataset_count = 0
    for source_id, rows in grouped.items():
        records = [normalize_record(row, default_status="OPEN") for row in rows]
        source_url = conn.execute("SELECT base_url FROM sources WHERE source_id=?", (source_id,)).fetchone()[0]
        counts = mirror_records(
            conn,
            source_id=source_id,
            records=records,
            source_url=source_url,
            raw_payload=rows,
        )
        dataset_count += counts["new"] + counts["updated"] + counts["unchanged"]

    signal_rows = _read_json("initial_signals.json")
    signals = [PreReleaseSignal(**row) for row in signal_rows]
    upsert_signals(conn, source_id="nia_procurement", signals=signals, raw_payload=signal_rows)
    register_seoul_collector(conn)

    for override in _read_json("initial_overrides.json"):
        dataset = conn.execute(
            "SELECT dataset_id FROM datasets WHERE source_id=? AND external_id=?",
            (override.pop("source_id"), override.pop("external_id")),
        ).fetchone()
        if dataset is None:
            continue
        set_override(conn, candidate_id=dataset["dataset_id"], **override)

    linked = link_signals_to_datasets(conn)
    scored = score_all(conn)
    conn.commit()
    return {
        "datasets": dataset_count,
        "signals": len(signals),
        "links": linked,
        "scored_datasets": scored["datasets"],
        "scored_signals": scored["signals"],
    }
