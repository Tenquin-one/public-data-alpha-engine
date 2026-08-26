from __future__ import annotations

import json
import os
import sqlite3
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from ..http_client import HttpClient, HttpResponse
from ..registry import finish_run, start_run
from ..storage import store_raw_payload
from ..utils import canonical_json, redact_secret, sha256_bytes, slug, utc_now


COLLECTOR_ID = "seoul_realtime_city_seed_v1"
SOURCE_ID = "seoul_open_data_realtime_city"
DATASET_ID = "seoul-open-data:oa-21285"
BASE_URL = "http://openapi.seoul.go.kr:8088"
INTEGRATED_SERVICE = "citydata"
EXPECTED_SECTIONS = (
    "LIVE_PPLTN_STTS",
    "LIVE_CMRCL_STTS",
    "ROAD_TRAFFIC_STTS",
    "PRK_STTS",
    "SUB_STTS",
    "BUS_STN_STTS",
    "WEATHER_STTS",
    "EVENT_STTS",
)
CURRENT_TIMESTAMP_FIELDS = {
    "PPLTN_TIME",
    "CMRCL_TIME",
    "ROAD_TRAFFIC_TIME",
    "WEATHER_TIME",
    "ACDNT_TIME",
    "CUR_PRK_TIME",
}

SEED_PLACES = (
    ("hongdae-tourism", None, "홍대 관광특구", "nightlife-tourism", "Nightlife, tourism, festivals, and launch events."),
    ("seongsu-cafe", None, "성수카페거리", "retail-popups", "Pop-ups, fashion/beauty launches, and fast retail turnover."),
    ("itaewon-tourism", None, "이태원 관광특구", "nightlife-tourism", "High event, tourism, and nightlife variance."),
    ("myeongdong-tourism", None, "명동 관광특구", "tourism-retail", "Tourist retail and currency/seasonality exposure."),
    ("gangnam-station", None, "강남역", "office-nightlife", "Large commuter-to-nightlife state transitions."),
    ("jamsil-tourism", None, "잠실 관광특구", "sports-events", "Stadium, arena, theme park, and large event effects."),
    ("gwanghwamun-deoksugung", None, "광화문·덕수궁", "civic-events", "Rallies, festivals, tourism, and public events; sample-key area."),
    ("yeouido", None, "여의도", "office-events", "Office cycles, festivals, finance, and river-park events."),
)


@dataclass(frozen=True)
class CollectionResult:
    area_name: str
    status: str
    snapshot_id: int | None
    duplicate: bool
    missing_sections: list[str]
    source_timestamp: str | None
    byte_count: int
    retries: int
    latency_ms: int
    http_status: int | None
    error: str | None = None


def register(conn: sqlite3.Connection) -> None:
    now = utc_now()
    # First official sample snapshot (2026-08-26 review) stored as 31,875 gzip bytes.
    storage_estimate = 8 * 96 * 31_875
    conn.execute(
        """
        INSERT INTO collector_registry(
            collector_id, dataset_id, source_id, name, module, endpoint_template,
            schedule_cron, cadence_seconds, entity_key, snapshot_strategy,
            storage_estimate_bytes_day, legal_memo, terms_checked_at, enabled,
            auth_env, config_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ON CONFLICT(collector_id) DO UPDATE SET
            dataset_id=excluded.dataset_id, source_id=excluded.source_id, name=excluded.name,
            module=excluded.module, endpoint_template=excluded.endpoint_template,
            schedule_cron=excluded.schedule_cron, cadence_seconds=excluded.cadence_seconds,
            entity_key=excluded.entity_key, snapshot_strategy=excluded.snapshot_strategy,
            storage_estimate_bytes_day=excluded.storage_estimate_bytes_day,
            legal_memo=excluded.legal_memo, terms_checked_at=excluded.terms_checked_at,
            auth_env=excluded.auth_env, config_json=excluded.config_json,
            updated_at=excluded.updated_at
        """,
        (
            COLLECTOR_ID,
            DATASET_ID,
            SOURCE_ID,
            "Seoul realtime commercial/city seed cohort",
            "public_data_alpha_engine.collectors.seoul_city:SeoulCityCollector",
            f"{BASE_URL}/{{KEY}}/{{TYPE}}/{INTEGRATED_SERVICE}/1/5/{{AREA_NM}}",
            "7,22,37,52 * * * *",
            900,
            "AREA_NM/AREA_CD",
            "15-minute integrated snapshots; gzip raw only on unseen content hash; normalized sections and source timestamps in SQLite",
            storage_estimate,
            "Official Seoul Open Data metadata: Korea Open Government License Type 1; attribution required; commercial use and modification allowed; no third-party copyright holder shown. Re-check if terms change.",
            "2026-08-26",
            "SEOUL_OPEN_DATA_KEY",
            canonical_json(
                {
                    "response_type": "json",
                    "fallback_response_type": "xml",
                    "expected_sections": list(EXPECTED_SECTIONS),
                    "sample_key_area": "광화문·덕수궁",
                    "raw_compression": "gzip",
                }
            ),
            now,
            now,
        ),
    )
    source_url = "https://data.seoul.go.kr/dataList/OA-22385/F/1/datasetView.do"
    for place_id, area_code, area_name, cohort, rationale in SEED_PLACES:
        conn.execute(
            """
            INSERT INTO place_registry(
                place_id, area_code, area_name, cohort, enabled, commercial_available,
                rationale, source_url, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, ?)
            ON CONFLICT(place_id) DO UPDATE SET
                area_code=excluded.area_code, area_name=excluded.area_name,
                cohort=excluded.cohort, enabled=excluded.enabled,
                commercial_available=excluded.commercial_available,
                rationale=excluded.rationale, source_url=excluded.source_url,
                updated_at=excluded.updated_at
            """,
            (place_id, area_code, area_name, cohort, rationale, source_url, now, now),
        )


def _xml_to_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    grouped: dict[str, list[Any]] = {}
    for child in children:
        grouped.setdefault(child.tag, []).append(_xml_to_value(child))
    return {key: values[0] if len(values) == 1 else values for key, values in grouped.items()}


def parse_payload(raw: bytes) -> tuple[dict[str, Any], str]:
    stripped = raw.lstrip()
    if stripped.startswith((b"{", b"[")):
        value = json.loads(raw.decode("utf-8"))
        mime_type = "application/json"
    else:
        value = {ET.fromstring(raw).tag: _xml_to_value(ET.fromstring(raw))}
        mime_type = "application/xml"
    if isinstance(value, list):
        normalized: dict[str, Any] = {"CITYDATA": value}
    else:
        normalized = value
    return normalized, mime_type


def _unwrap_citydata(value: dict[str, Any]) -> dict[str, Any]:
    for key in ("CITYDATA", "SeoulRtd.citydata", "citydata"):
        candidate = value.get(key)
        if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
            return candidate[0]
        if isinstance(candidate, dict):
            return candidate
    if len(value) == 1:
        candidate = next(iter(value.values()))
        if isinstance(candidate, dict):
            return _unwrap_citydata(candidate)
    return value


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _source_timestamp(value: dict[str, Any]) -> str | None:
    candidates: list[datetime] = []
    for key, child in _walk(value):
        if key in CURRENT_TIMESTAMP_FIELDS and isinstance(child, str):
            parsed = _parse_source_datetime(child)
            if parsed:
                candidates.append(parsed)
    return max(candidates).isoformat() if candidates else None


def _parse_source_datetime(value: str) -> datetime | None:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) < 12 or not digits.startswith("20"):
        return None
    digits = digits[:14].ljust(14, "0")
    try:
        return datetime.strptime(digits, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("Asia/Seoul"))
    except ValueError:
        return None


def _validate_api(value: dict[str, Any]) -> None:
    for key, child in _walk(value):
        if key in {"CODE", "code", "resultCode"} and isinstance(child, str):
            if child not in {"INFO-000", "00", "0", "NORMAL_SERVICE"}:
                raise RuntimeError(f"Seoul API returned {child}")


class SeoulCityCollector:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        api_key: str | None = None,
        client: HttpClient | None = None,
        response_type: str = "json",
    ) -> None:
        self.conn = conn
        self.api_key = api_key or os.getenv("SEOUL_OPEN_DATA_KEY")
        self.client = client or HttpClient(timeout=25, max_retries=2)
        self.response_type = response_type

    def _url(self, area_name: str, response_type: str | None = None) -> tuple[str, str]:
        if not self.api_key:
            raise RuntimeError("SEOUL_OPEN_DATA_KEY is required; use api_key='sample' for 광화문·덕수궁 only")
        kind = response_type or self.response_type
        area = urllib.parse.quote(area_name, safe="")
        url = f"{BASE_URL}/{urllib.parse.quote(self.api_key, safe='')}/{kind}/{INTEGRATED_SERVICE}/1/5/{area}"
        return url, redact_secret(url, urllib.parse.quote(self.api_key, safe=""))

    def collect_area(self, area_name: str, *, run_id: int | None = None) -> CollectionResult:
        url, safe_url = self._url(area_name)
        response: HttpResponse | None = None
        try:
            response = self.client.request(url)
            normalized, mime_type = parse_payload(response.body)
            _validate_api(normalized)
        except Exception as first_error:
            if self.response_type != "xml":
                try:
                    url, safe_url = self._url(area_name, "xml")
                    response = self.client.request(url)
                    normalized, mime_type = parse_payload(response.body)
                    _validate_api(normalized)
                except Exception as fallback_error:
                    raise RuntimeError(f"JSON and XML collection failed: {first_error}; {fallback_error}") from fallback_error
            else:
                raise
        assert response is not None
        city = _unwrap_citydata(normalized)
        source_timestamp = _source_timestamp(city)
        missing = [section for section in EXPECTED_SECTIONS if section not in city]
        content_hash = sha256_bytes(response.body)
        latest = self.conn.execute(
            """
            SELECT snapshot_id, payload_hash FROM snapshots
            WHERE collector_id=? AND entity_key=?
            ORDER BY collected_at DESC LIMIT 1
            """,
            (COLLECTOR_ID, area_name),
        ).fetchone()
        duplicate = bool(latest and latest["payload_hash"] == content_hash)
        stored = store_raw_payload(
            self.conn,
            source_id=SOURCE_ID,
            source_url=safe_url,
            payload=response.body,
            query_params={"service": INTEGRATED_SERVICE, "type": mime_type, "area_name": area_name},
            source_timestamp=source_timestamp,
            mime_type=mime_type,
            run_id=run_id,
        )
        if duplicate:
            return CollectionResult(
                area_name,
                "DUPLICATE",
                None,
                True,
                missing,
                source_timestamp,
                stored.byte_count,
                response.retries,
                response.elapsed_ms,
                response.status,
            )
        collected_at = utc_now()
        cursor = self.conn.execute(
            """
            INSERT INTO snapshots(
                collector_id, entity_type, entity_key, observed_at, collected_at,
                source_timestamp, source_url, query_params_json, payload_hash, raw_path,
                raw_payload_id, normalized_json, missing_sections_json, quality_status
            ) VALUES (?, 'SEOUL_HOTSPOT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                COLLECTOR_ID,
                area_name,
                source_timestamp or collected_at,
                collected_at,
                source_timestamp,
                safe_url,
                canonical_json({"service": INTEGRATED_SERVICE, "area_name": area_name}),
                content_hash,
                stored.raw_path,
                stored.payload_id,
                canonical_json(city),
                canonical_json(missing),
                "PARTIAL" if missing else "OK",
            ),
        )
        return CollectionResult(
            area_name,
            "PARTIAL" if missing else "OK",
            cursor.lastrowid,
            False,
            missing,
            source_timestamp,
            stored.byte_count,
            response.retries,
            response.elapsed_ms,
            response.status,
        )

    def collect(self, *, sample_only: bool = False) -> list[CollectionResult]:
        places = ["광화문·덕수궁"] if sample_only else [
            row["area_name"]
            for row in self.conn.execute(
                "SELECT area_name FROM place_registry WHERE enabled=1 ORDER BY place_id"
            )
        ]
        if self.api_key == "sample" and places != ["광화문·덕수궁"]:
            raise RuntimeError("The official sample key only supports 광화문·덕수궁; pass sample_only=True")
        run_id = start_run(self.conn, SOURCE_ID, COLLECTOR_ID)
        results: list[CollectionResult] = []
        for area_name in places:
            try:
                results.append(self.collect_area(area_name, run_id=run_id))
            except Exception as exc:
                results.append(CollectionResult(area_name, "ERROR", None, False, list(EXPECTED_SECTIONS), None, 0, 0, 0, None, str(exc)))
        successes = [result for result in results if result.status != "ERROR"]
        duplicates = sum(result.duplicate for result in successes)
        inserted = sum(result.snapshot_id is not None for result in successes)
        errors = len(results) - len(successes)
        status = "SUCCESS" if not errors else "PARTIAL" if successes else "FAILED"
        measured = [result.byte_count for result in successes if not result.duplicate and result.byte_count > 0]
        if measured:
            bytes_per_snapshot = sum(measured) / len(measured)
            estimated_daily = round(bytes_per_snapshot * len(SEED_PLACES) * (86400 / 900))
            self.conn.execute(
                "UPDATE collector_registry SET storage_estimate_bytes_day=?, updated_at=? WHERE collector_id=?",
                (estimated_daily, utc_now(), COLLECTOR_ID),
            )
        finish_run(
            self.conn,
            run_id,
            status=status,
            requested=len(places),
            received=len(successes),
            inserted=inserted,
            duplicates=duplicates,
            errors=errors,
            error_message="; ".join(result.error or "" for result in results if result.error) or None,
        )
        self.conn.execute(
            """
            INSERT INTO collector_health_logs(
                collector_id, run_id, checked_at, status, latency_ms, http_status,
                retry_count, entities_expected, entities_succeeded, new_snapshots,
                duplicates, missing_count, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                COLLECTOR_ID,
                run_id,
                utc_now(),
                status,
                sum(result.latency_ms for result in results),
                max((result.http_status or 0 for result in results), default=0) or None,
                sum(result.retries for result in results),
                len(places),
                len(successes),
                inserted,
                duplicates,
                sum(len(result.missing_sections) for result in successes),
                "; ".join(f"{result.area_name}:{result.status}" for result in results),
            ),
        )
        detect_gaps(self.conn)
        self.conn.commit()
        return results


def detect_gaps(conn: sqlite3.Connection, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    cadence = conn.execute(
        "SELECT cadence_seconds FROM collector_registry WHERE collector_id=?",
        (COLLECTOR_ID,),
    ).fetchone()
    cadence_seconds = cadence["cadence_seconds"] if cadence else 900
    threshold = now - timedelta(seconds=cadence_seconds * 2.5)
    inserted = 0
    for place in conn.execute("SELECT area_name FROM place_registry WHERE enabled=1"):
        latest = conn.execute(
            """
            SELECT collected_at FROM raw_payloads
            WHERE source_id=? AND json_extract(query_params_json, '$.area_name')=?
            ORDER BY collected_at DESC LIMIT 1
            """,
            (SOURCE_ID, place["area_name"]),
        ).fetchone()
        if latest and datetime.fromisoformat(latest["collected_at"]) >= threshold:
            conn.execute(
                """
                UPDATE data_gap_events SET resolved_at=?
                WHERE collector_id=? AND entity_key=? AND resolved_at IS NULL
                """,
                (now.replace(microsecond=0).isoformat(), COLLECTOR_ID, place["area_name"]),
            )
            continue
        open_gap = conn.execute(
            """
            SELECT 1 FROM data_gap_events
            WHERE collector_id=? AND entity_key=? AND resolved_at IS NULL LIMIT 1
            """,
            (COLLECTOR_ID, place["area_name"]),
        ).fetchone()
        if open_gap:
            continue
        expected_at = threshold.replace(microsecond=0).isoformat()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO data_gap_events(
                collector_id, entity_key, expected_at, detected_at, severity, reason
            ) VALUES (?, ?, ?, ?, 'WARNING', ?)
            """,
            (
                COLLECTOR_ID,
                place["area_name"],
                expected_at,
                now.replace(microsecond=0).isoformat(),
                "No snapshot within 2.5x configured cadence",
            ),
        )
        inserted += cursor.rowcount
    return inserted
