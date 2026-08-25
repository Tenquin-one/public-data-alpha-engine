from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .storage import store_raw_payload
from .utils import canonical_json, sha256_json, slug, utc_now


MONITORED_FIELDS: dict[str, str] = {
    "modified_at": "MODIFIED_AT_CHANGED",
    "public_status": "PUBLIC_STATUS_CHANGED",
    "api_available": "API_AVAILABILITY_CHANGED",
    "file_available": "FILE_AVAILABILITY_CHANGED",
    "update_frequency": "UPDATE_FREQUENCY_CHANGED",
    "license": "LICENSE_CHANGED",
    "terms": "TERMS_CHANGED",
    "provider": "PROVIDER_CHANGED",
}


ALIASES: dict[str, tuple[str, ...]] = {
    "external_id": ("external_id", "목록키", "목록ID", "데이터ID", "publicDataPk", "id"),
    "title": ("title", "목록명", "공공데이터명", "파일데이터명", "데이터명", "서비스명"),
    "description": ("description", "설명", "공공데이터설명", "데이터설명"),
    "provider": ("provider", "제공기관", "기관명", "제공기관명"),
    "category": ("category", "분류체계", "분류"),
    "public_status": ("public_status", "공개상태", "개방상태", "개방여부"),
    "expected_release_year": ("expected_release_year", "개방예정년도", "개방예정연도", "예정년도"),
    "data_type": ("data_type", "목록유형", "데이터유형", "데이터구분", "제공형태"),
    "update_frequency": ("update_frequency", "업데이트주기", "갱신주기", "업데이트 주기"),
    "license": ("license", "이용허락범위", "라이선스"),
    "terms": ("terms", "이용조건", "기타유의사항", "기타 유의사항"),
    "registered_at": ("registered_at", "등록일", "공개일자"),
    "modified_at": ("modified_at", "수정일", "데이터갱신일", "데이터 갱신일"),
    "source_url": ("source_url", "목록URL", "URL", "데이터URL", "url"),
    "keywords": ("keywords", "키워드", "관련태그", "관련 태그"),
    "machine_format": ("machine_format", "확장자", "데이터포맷", "API유형", "API 유형"),
    "cost_status": ("cost_status", "비용부과유무", "비용"),
    "rights_status": ("rights_status", "권리상태"),
    "historical_availability": ("historical_availability", "과거이력", "역사데이터"),
}


@dataclass
class DatasetRecord:
    external_id: str
    title: str
    source_url: str
    description: str = ""
    provider: str = ""
    category: str = ""
    public_status: str = "OPEN"
    expected_release_year: int | None = None
    api_available: bool = False
    file_available: bool = False
    update_frequency: str = ""
    license: str = ""
    terms: str = ""
    registered_at: str | None = None
    modified_at: str | None = None
    keywords: list[str] = field(default_factory=list)
    machine_format: str = ""
    cost_status: str = "UNKNOWN"
    rights_status: str = "UNKNOWN"
    historical_availability: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_stable_dict(self) -> dict[str, Any]:
        value = self.__dict__.copy()
        value["keywords"] = sorted(self.keywords)
        return value


def _pick(raw: dict[str, Any], key: str, default: Any = "") -> Any:
    for alias in ALIASES[key]:
        value = raw.get(alias)
        if value is not None and str(value).strip() != "":
            return value
    return default


def _bool_availability(data_type: str, target: str) -> bool:
    value = data_type.casefold()
    if target == "api":
        return any(token in value for token in ("api", "rest", "soap", "xml", "json"))
    return any(token in value for token in ("file", "파일", "다운로드", "csv", "xlsx", "sheet"))


def _normalize_status(value: str, default: str) -> str:
    lowered = value.strip().casefold()
    if default == "PLANNED":
        return "PLANNED"
    if lowered in {"n", "미개방", "비공개", "planned", "예정"}:
        return "PLANNED"
    if lowered in {"y", "공개", "개방", "open", "available"}:
        return "OPEN"
    return value.strip().upper().replace(" ", "_") or default


def _normalize_cost(value: str) -> str:
    lowered = value.strip().casefold()
    if any(token in lowered for token in ("무료", "free", "없음")):
        return "FREE"
    if any(token in lowered for token in ("유료", "paid")):
        return "PAID"
    return value.strip().upper() or "UNKNOWN"


def _normalize_rights(value: str, explicit: str) -> str:
    if explicit and explicit.upper() != "UNKNOWN":
        return explicit.upper()
    lowered = value.casefold()
    if any(token in lowered for token in ("제한 없음", "제한없음", "제1유형", "상업적 이용")):
        return "ALLOW"
    if any(token in lowered for token in ("상업적 이용금지", "제2유형", "제4유형", "금지")):
        return "RESTRICTED"
    return "UNKNOWN"


def _extract_external_id(raw: dict[str, Any], source_url: str, title: str, provider: str) -> str:
    explicit = str(_pick(raw, "external_id", "")).strip()
    if explicit:
        return explicit
    match = re.search(r"(?:/data/|publicDataPk=)(\d+)", source_url)
    if match:
        return match.group(1)
    return sha256_json([provider, title])[:20]


def normalize_record(raw: dict[str, Any], *, default_status: str = "OPEN") -> DatasetRecord:
    title = str(_pick(raw, "title", "")).strip()
    provider = str(_pick(raw, "provider", "")).strip()
    source_url = str(_pick(raw, "source_url", "")).strip() or "https://www.data.go.kr/"
    if not title:
        raise ValueError("registry record has no title")
    data_type = str(_pick(raw, "data_type", ""))
    machine_format = str(_pick(raw, "machine_format", ""))
    combined_type = f"{data_type} {machine_format}"
    keyword_value = _pick(raw, "keywords", [])
    if isinstance(keyword_value, str):
        keywords = [part.strip() for part in re.split(r"[,|]", keyword_value) if part.strip()]
    else:
        keywords = [str(part).strip() for part in keyword_value if str(part).strip()]
    year_value = str(_pick(raw, "expected_release_year", "")).strip()
    year_match = re.search(r"20\d{2}", year_value)
    license_value = str(_pick(raw, "license", "")).strip()
    explicit_rights = str(_pick(raw, "rights_status", "UNKNOWN"))
    record = DatasetRecord(
        external_id="",
        title=title,
        source_url=source_url,
        description=str(_pick(raw, "description", "")).strip(),
        provider=provider,
        category=str(_pick(raw, "category", "")).strip(),
        public_status=_normalize_status(str(_pick(raw, "public_status", default_status)), default_status),
        expected_release_year=int(year_match.group()) if year_match else None,
        api_available=bool(raw.get("api_available", _bool_availability(combined_type, "api"))),
        file_available=bool(raw.get("file_available", _bool_availability(combined_type, "file"))),
        update_frequency=str(_pick(raw, "update_frequency", "")).strip(),
        license=license_value,
        terms=str(_pick(raw, "terms", "")).strip(),
        registered_at=str(_pick(raw, "registered_at", "")).strip() or None,
        modified_at=str(_pick(raw, "modified_at", "")).strip() or None,
        keywords=keywords,
        machine_format=machine_format or data_type,
        cost_status=_normalize_cost(str(_pick(raw, "cost_status", "UNKNOWN"))),
        rights_status=_normalize_rights(license_value, explicit_rights),
        historical_availability=str(_pick(raw, "historical_availability", "UNKNOWN")).upper(),
        metadata={key: value for key, value in raw.items() if key not in {"raw_payload"}},
    )
    record.external_id = _extract_external_id(raw, source_url, title, provider)
    return record


def parse_csv_records(value: bytes | str | Path, *, default_status: str = "OPEN") -> list[DatasetRecord]:
    if isinstance(value, Path):
        raw = value.read_bytes()
    elif isinstance(value, bytes):
        raw = value
    else:
        raw = value.encode("utf-8")
    text = None
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise UnicodeDecodeError("registry", raw, 0, len(raw), "unsupported encoding")
    return [normalize_record(dict(row), default_status=default_status) for row in csv.DictReader(io.StringIO(text))]


def _dataset_id(source_id: str, external_id: str) -> str:
    return f"{slug(source_id, 30)}:{slug(external_id, 80)}"


def start_run(conn: sqlite3.Connection, source_id: str, collector_id: str | None = None) -> int:
    cursor = conn.execute(
        "INSERT INTO collection_runs(source_id, collector_id, started_at, status) VALUES (?, ?, ?, 'RUNNING')",
        (source_id, collector_id, utc_now()),
    )
    return cursor.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    requested: int = 0,
    received: int = 0,
    inserted: int = 0,
    duplicates: int = 0,
    errors: int = 0,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE collection_runs SET finished_at=?, status=?, requested_count=?, received_count=?,
            inserted_count=?, duplicate_count=?, error_count=?, error_message=?
        WHERE run_id=?
        """,
        (utc_now(), status, requested, received, inserted, duplicates, errors, error_message, run_id),
    )


def mirror_records(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    records: Iterable[DatasetRecord],
    source_url: str,
    query_params: dict[str, Any] | None = None,
    raw_payload: bytes | str | dict[str, Any] | list[Any] | None = None,
    run_id: int | None = None,
    observed_at: str | None = None,
) -> dict[str, int]:
    observed_at = observed_at or utc_now()
    rows = list(records)
    payload = raw_payload if raw_payload is not None else [row.as_stable_dict() for row in rows]
    stored = store_raw_payload(
        conn,
        source_id=source_id,
        source_url=source_url,
        payload=payload,
        query_params=query_params,
        run_id=run_id,
        collected_at=observed_at,
    )
    counts = {"new": 0, "updated": 0, "unchanged": 0, "events": 0}
    for record in rows:
        dataset_id = _dataset_id(source_id, record.external_id)
        current_hash = sha256_json(record.as_stable_dict())
        existing = conn.execute("SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
        values = (
            record.external_id,
            source_id,
            record.title,
            record.description,
            record.provider,
            record.category,
            record.public_status,
            record.expected_release_year,
            int(record.api_available),
            int(record.file_available),
            record.update_frequency,
            record.license,
            record.terms,
            record.registered_at,
            record.modified_at,
            record.source_url,
            canonical_json(record.keywords),
            record.machine_format,
            record.cost_status,
            record.rights_status,
            record.historical_availability,
            current_hash,
            observed_at,
            stored.payload_id,
            canonical_json(record.metadata),
        )
        if existing is None:
            conn.execute(
                """
                INSERT INTO datasets(
                    dataset_id, external_id, source_id, title, description, provider, category,
                    public_status, expected_release_year, api_available, file_available,
                    update_frequency, license, terms, registered_at, modified_at, source_url,
                    keywords_json, machine_format, cost_status, rights_status,
                    historical_availability, current_hash, first_seen_at, last_seen_at,
                    raw_payload_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (dataset_id, *values[:23], observed_at, *values[23:]),
            )
            conn.execute(
                """
                INSERT INTO dataset_events(dataset_id, event_at, event_type, new_value, observed_run_id, raw_payload_id)
                VALUES (?, ?, 'NEW_DATASET', ?, ?, ?)
                """,
                (dataset_id, observed_at, record.title, run_id, stored.payload_id),
            )
            counts["new"] += 1
            counts["events"] += 1
            continue
        if existing["current_hash"] == current_hash:
            conn.execute(
                "UPDATE datasets SET last_seen_at=?, raw_payload_id=? WHERE dataset_id=?",
                (observed_at, stored.payload_id, dataset_id),
            )
            counts["unchanged"] += 1
            continue
        record_values = record.__dict__
        for field_name, event_type in MONITORED_FIELDS.items():
            old_value = existing[field_name]
            new_value = record_values[field_name]
            if isinstance(new_value, bool):
                new_value = int(new_value)
            if old_value != new_value:
                if field_name == "api_available" and not old_value and new_value:
                    event_type = "API_ADDED"
                elif field_name == "file_available" and not old_value and new_value:
                    event_type = "FILE_ADDED"
                conn.execute(
                    """
                    INSERT INTO dataset_events(
                        dataset_id, event_at, event_type, field_name, old_value, new_value,
                        observed_run_id, raw_payload_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (dataset_id, observed_at, event_type, field_name, str(old_value), str(new_value), run_id, stored.payload_id),
                )
                counts["events"] += 1
        conn.execute(
            """
            UPDATE datasets SET
                title=?, description=?, provider=?, category=?, public_status=?,
                expected_release_year=?, api_available=?, file_available=?, update_frequency=?,
                license=?, terms=?, registered_at=?, modified_at=?, source_url=?, keywords_json=?,
                machine_format=?, cost_status=?, rights_status=?, historical_availability=?,
                current_hash=?, last_seen_at=?, raw_payload_id=?, metadata_json=?
            WHERE dataset_id=?
            """,
            (
                record.title,
                record.description,
                record.provider,
                record.category,
                record.public_status,
                record.expected_release_year,
                int(record.api_available),
                int(record.file_available),
                record.update_frequency,
                record.license,
                record.terms,
                record.registered_at,
                record.modified_at,
                record.source_url,
                canonical_json(record.keywords),
                record.machine_format,
                record.cost_status,
                record.rights_status,
                record.historical_availability,
                current_hash,
                observed_at,
                stored.payload_id,
                canonical_json(record.metadata),
                dataset_id,
            ),
        )
        counts["updated"] += 1
    counts["raw_duplicate"] = int(stored.is_duplicate)
    return counts


def _title_tokens(value: str, provider: str = "") -> set[str]:
    value = value.replace(provider, " ") if provider else value
    return {
        token
        for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", value.casefold())
        if token not in {"데이터", "정보", "현황", "목록", "서비스", "공공데이터"}
    }


def reconcile_planned_to_open(conn: sqlite3.Connection, *, observed_at: str | None = None) -> int:
    observed_at = observed_at or utc_now()
    planned = conn.execute("SELECT * FROM datasets WHERE public_status='PLANNED'").fetchall()
    opened = conn.execute("SELECT * FROM datasets WHERE public_status='OPEN'").fetchall()
    linked = 0
    for plan in planned:
        plan_tokens = _title_tokens(plan["title"], plan["provider"] or "")
        if not plan_tokens:
            continue
        best: tuple[float, sqlite3.Row] | None = None
        for opened_row in opened:
            if plan["provider"] and opened_row["provider"] and plan["provider"] != opened_row["provider"]:
                continue
            open_tokens = _title_tokens(opened_row["title"], opened_row["provider"] or "")
            union = plan_tokens | open_tokens
            confidence = len(plan_tokens & open_tokens) / len(union) if union else 0
            if confidence >= 0.62 and (best is None or confidence > best[0]):
                best = (confidence, opened_row)
        if best is None:
            continue
        confidence, opened_row = best
        metadata = json.loads(plan["metadata_json"] or "{}")
        metadata["released_dataset_id"] = opened_row["dataset_id"]
        metadata["release_match_confidence"] = round(confidence, 4)
        conn.execute(
            "UPDATE datasets SET public_status='OPEN_LINKED', last_seen_at=?, metadata_json=? WHERE dataset_id=?",
            (observed_at, canonical_json(metadata), plan["dataset_id"]),
        )
        conn.execute(
            """
            INSERT INTO dataset_events(dataset_id, event_at, event_type, field_name, old_value, new_value)
            VALUES (?, ?, 'EXPECTED_TO_OPEN', 'public_status', 'PLANNED', ?)
            """,
            (plan["dataset_id"], observed_at, opened_row["dataset_id"]),
        )
        linked += 1
    return linked
