from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from .http_client import HttpClient, HttpResponse
from .registry import DatasetRecord, normalize_record, parse_csv_records


ODCLOUD_CATALOG_BASE = "https://api.odcloud.kr/api/15077093/v1"


@dataclass(frozen=True)
class RegistryBatch:
    records: list[DatasetRecord]
    source_url: str
    query_params: dict[str, object]
    raw_payload: bytes
    mime_type: str


def fetch_odcloud_catalog(
    *,
    service_key: str,
    endpoint: str = "dataset",
    page: int = 1,
    per_page: int = 1000,
    client: HttpClient | None = None,
) -> RegistryBatch:
    if endpoint not in {"dataset", "file-data-list", "open-data-list", "standard-data-list"}:
        raise ValueError(f"unsupported ODCloud catalog endpoint: {endpoint}")
    params = {"page": page, "perPage": per_page, "serviceKey": service_key}
    url = f"{ODCLOUD_CATALOG_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    response = (client or HttpClient()).request(url)
    payload = json.loads(response.body.decode("utf-8"))
    raw_records = payload.get("data") or payload.get("items") or []
    records = [normalize_record(dict(row), default_status="OPEN") for row in raw_records]
    safe_params = {"page": page, "perPage": per_page, "serviceKey": "REDACTED"}
    return RegistryBatch(records, f"{ODCLOUD_CATALOG_BASE}/{endpoint}", safe_params, response.body, response.content_type)


def fetch_csv_registry(
    *,
    source: str | Path,
    default_status: str,
    client: HttpClient | None = None,
) -> RegistryBatch:
    if isinstance(source, Path) or not str(source).startswith(("http://", "https://")):
        path = Path(source)
        raw = path.read_bytes()
        source_url = path.resolve().as_uri()
        mime_type = "text/csv"
    else:
        response: HttpResponse = (client or HttpClient()).request(str(source))
        raw = response.body
        source_url = str(source)
        mime_type = response.content_type
    records = parse_csv_records(raw, default_status=default_status)
    return RegistryBatch(records, source_url, {}, raw, mime_type)
