from __future__ import annotations

import gzip
import io
import json
import tarfile
import urllib.parse
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .collectors.seoul_city import (
    BASE_URL,
    EXPECTED_SECTIONS,
    INTEGRATED_SERVICE,
    SEED_PLACES,
    _source_timestamp,
    _unwrap_citydata,
    _validate_api,
    parse_payload,
)
from .http_client import HttpClient, HttpResponse
from .utils import canonical_json, redact_secret, sha256_bytes, slug


CLOUD_CADENCE_SECONDS = 900
CLOUD_GAP_THRESHOLD_MULTIPLIER = 2.5


@dataclass(frozen=True)
class CloudArchiveRecord:
    area_name: str
    status: str
    collected_at: str
    source_timestamp: str | None
    source_url: str
    query_params: dict[str, str]
    content_hash: str | None
    raw_member: str | None
    raw_uncompressed_bytes: int
    raw_gzip_bytes: int
    missing_sections: list[str]
    http_status: int | None
    latency_ms: int
    retries: int
    error: str | None = None


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "areas": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _schedule_health(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    previous_value = state.get("updated_at")
    if not isinstance(previous_value, str):
        return {
            "status": "NO_BASELINE",
            "cadence_seconds": CLOUD_CADENCE_SECONDS,
            "previous_run_at": None,
            "elapsed_seconds": None,
            "late_by_seconds": 0,
            "missed_intervals": 0,
        }
    try:
        previous = datetime.fromisoformat(previous_value)
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=UTC)
        previous = previous.astimezone(UTC)
    except ValueError:
        return {
            "status": "INVALID_BASELINE",
            "cadence_seconds": CLOUD_CADENCE_SECONDS,
            "previous_run_at": previous_value,
            "elapsed_seconds": None,
            "late_by_seconds": 0,
            "missed_intervals": 0,
        }
    elapsed = max(0, round((now - previous).total_seconds()))
    missed_intervals = max(0, elapsed // CLOUD_CADENCE_SECONDS - 1)
    threshold = CLOUD_CADENCE_SECONDS * CLOUD_GAP_THRESHOLD_MULTIPLIER
    return {
        "status": "WARNING" if elapsed > threshold else "OK",
        "cadence_seconds": CLOUD_CADENCE_SECONDS,
        "previous_run_at": previous.isoformat(),
        "elapsed_seconds": elapsed,
        "late_by_seconds": max(0, elapsed - CLOUD_CADENCE_SECONDS),
        "missed_intervals": missed_intervals,
    }


def _request_area(
    client: HttpClient,
    *,
    api_key: str,
    area_name: str,
) -> tuple[HttpResponse, dict[str, Any], str, str]:
    first_error: Exception | None = None
    for response_type in ("json", "xml"):
        area = urllib.parse.quote(area_name, safe="")
        encoded_key = urllib.parse.quote(api_key, safe="")
        url = f"{BASE_URL}/{encoded_key}/{response_type}/{INTEGRATED_SERVICE}/1/5/{area}"
        safe_url = redact_secret(url, encoded_key)
        try:
            response = client.request(url)
            normalized, mime_type = parse_payload(response.body)
            _validate_api(normalized)
            return response, _unwrap_citydata(normalized), mime_type, safe_url
        except Exception as exc:
            if first_error is None:
                first_error = exc
    raise RuntimeError(f"JSON and XML collection failed: {first_error}")


def _add_bytes(archive: tarfile.TarFile, name: str, content: bytes, mtime: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mtime = mtime
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(content))


def collect_cloud_archive(
    output_root: Path,
    *,
    api_key: str,
    client: HttpClient | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("api_key is required; use 'sample' for the official single-place mode")
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)
    collected_at = now.isoformat()
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    state_path = output_root / "state" / "latest_hashes.json"
    state = _read_state(state_path)
    schedule_health = _schedule_health(state, now)
    areas_state = state.setdefault("areas", {})
    areas = ["광화문·덕수궁"] if api_key == "sample" else [place[2] for place in SEED_PLACES]
    http = client or HttpClient(timeout=25, max_retries=2)
    records: list[CloudArchiveRecord] = []
    payloads: dict[str, bytes] = {}

    for area_name in areas:
        try:
            response, city, mime_type, safe_url = _request_area(
                http,
                api_key=api_key,
                area_name=area_name,
            )
            content_hash = sha256_bytes(response.body)
            duplicate = areas_state.get(area_name, {}).get("content_hash") == content_hash
            missing = [section for section in EXPECTED_SECTIONS if section not in city]
            source_timestamp = _source_timestamp(city)
            raw_member = None
            compressed_bytes = 0
            if not duplicate:
                suffix = "json" if "json" in mime_type else "xml"
                raw_member = f"payloads/{slug(area_name, 45)}-{content_hash}.{suffix}.gz"
                compressed = gzip.compress(response.body, compresslevel=6, mtime=0)
                payloads[raw_member] = compressed
                compressed_bytes = len(compressed)
            status = "DUPLICATE" if duplicate else "PARTIAL" if missing else "OK"
            records.append(
                CloudArchiveRecord(
                    area_name=area_name,
                    status=status,
                    collected_at=collected_at,
                    source_timestamp=source_timestamp,
                    source_url=safe_url,
                    query_params={"service": INTEGRATED_SERVICE, "area_name": area_name, "mime_type": mime_type},
                    content_hash=content_hash,
                    raw_member=raw_member,
                    raw_uncompressed_bytes=len(response.body),
                    raw_gzip_bytes=compressed_bytes,
                    missing_sections=missing,
                    http_status=response.status,
                    latency_ms=response.elapsed_ms,
                    retries=response.retries,
                )
            )
            areas_state[area_name] = {
                "content_hash": content_hash,
                "source_timestamp": source_timestamp,
                "collected_at": collected_at,
                "status": status,
            }
        except Exception as exc:
            records.append(
                CloudArchiveRecord(
                    area_name=area_name,
                    status="ERROR",
                    collected_at=collected_at,
                    source_timestamp=None,
                    source_url=f"{BASE_URL}/REDACTED/...",
                    query_params={"service": INTEGRATED_SERVICE, "area_name": area_name},
                    content_hash=None,
                    raw_member=None,
                    raw_uncompressed_bytes=0,
                    raw_gzip_bytes=0,
                    missing_sections=list(EXPECTED_SECTIONS),
                    http_status=None,
                    latency_ms=0,
                    retries=0,
                    error=str(exc),
                )
            )

    succeeded = sum(record.status != "ERROR" for record in records)
    new_payloads = sum(record.raw_member is not None for record in records)
    errors = len(records) - succeeded
    overall = "SUCCESS" if errors == 0 else "PARTIAL" if succeeded else "FAILED"
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "status": overall,
        "mode": "SAMPLE" if api_key == "sample" else "SEED_COHORT",
        "collected_at": collected_at,
        "source": "Seoul Open Data realtime city API",
        "records": [asdict(record) for record in records],
        "summary": {
            "areas_requested": len(areas),
            "areas_succeeded": succeeded,
            "new_payloads": new_payloads,
            "duplicates": sum(record.status == "DUPLICATE" for record in records),
            "errors": errors,
            "gzip_bytes": sum(record.raw_gzip_bytes for record in records),
        },
        "health": {
            "schedule": schedule_health,
            "requests": {
                "total_retries": sum(record.retries for record in records),
                "max_latency_ms": max((record.latency_ms for record in records), default=0),
                "missing_sections": sum(len(record.missing_sections) for record in records if record.status != "ERROR"),
            },
        },
    }
    date_path = Path(now.strftime("%Y/%m/%d"))
    run_path = output_root / "runs" / date_path / f"{run_id}.json"
    _write_json_atomic(run_path, manifest)
    bundle_path: Path | None = None
    if payloads:
        bundle_path = output_root / "bundles" / date_path / f"{run_id}.tar"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(bundle_path, "w") as archive:
            _add_bytes(
                archive,
                "manifest.json",
                (canonical_json(manifest) + "\n").encode("utf-8"),
                int(now.timestamp()),
            )
            for member_name, content in sorted(payloads.items()):
                _add_bytes(archive, member_name, content, int(now.timestamp()))
    state.update(
        {
            "version": 1,
            "updated_at": collected_at,
            "last_run_id": run_id,
            "last_status": overall,
            "last_health": manifest["health"],
        }
    )
    _write_json_atomic(state_path, state)
    return {
        "status": overall,
        "mode": manifest["mode"],
        "run_id": run_id,
        "run_path": str(run_path),
        "bundle_path": str(bundle_path) if bundle_path else None,
        "health_status": schedule_health["status"],
        "missed_intervals": schedule_health["missed_intervals"],
        **manifest["summary"],
    }
