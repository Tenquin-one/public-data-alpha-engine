from __future__ import annotations

import gzip
import json
import re
import tarfile
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .archive import add_bytes, namespace_path, read_json_state, schedule_health, write_json_atomic
from .calendar_kr import calendar_features
from .http_client import HttpClient, HttpResponse
from .utils import canonical_json, sha256_bytes, sha256_json, slug


NAMESPACE = "airport_friction"
COLLECTOR_ID = "airport_friction_v0_1"
CADENCE_SECONDS = 900
WEATHER_CADENCE_SECONDS = 1800
GAP_THRESHOLD_MULTIPLIER = 2.5
KST = timezone(timedelta(hours=9))
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "airport_friction_fixture.json"


@dataclass(frozen=True)
class Airport:
    iata: str
    icao: str
    name_ko: str
    name_en: str


AIRPORTS = (
    Airport("GMP", "RKSS", "김포", "Gimpo"),
    Airport("CJU", "RKPC", "제주", "Jeju"),
    Airport("PUS", "RKPK", "김해", "Gimhae"),
    Airport("CJJ", "RKTU", "청주", "Cheongju"),
    Airport("TAE", "RKTN", "대구", "Daegu"),
)
AIRPORT_BY_IATA = {airport.iata: airport for airport in AIRPORTS}
AIRPORT_BY_ICAO = {airport.icao: airport for airport in AIRPORTS}


@dataclass(frozen=True)
class RequestSpec:
    source_id: str
    provider: str
    base_url: str
    path: str
    params: dict[str, str]
    secret_param: str
    secret_env: str
    cadence_seconds: int
    airports: tuple[str, ...]
    expected_fields: tuple[str, ...]


@dataclass(frozen=True)
class SourceObservation:
    source_id: str
    provider: str
    status: str
    collected_at: str
    source_timestamp: str | None
    source_url: str
    query_params: dict[str, str]
    airports: list[str]
    content_hash: str | None
    raw_member: str | None
    raw_uncompressed_bytes: int
    raw_gzip_bytes: int
    missing_sections: list[str]
    http_status: int | None
    latency_ms: int
    retries: int
    error: str | None = None


def quota_budget(*, cadence_minutes: int = 15, weather_minutes: int = 30) -> dict[str, Any]:
    if cadence_minutes <= 0 or 1440 % cadence_minutes:
        raise ValueError("cadence_minutes must be a positive divisor of 1440")
    if weather_minutes <= 0 or 1440 % weather_minutes:
        raise ValueError("weather_minutes must be a positive divisor of 1440")
    runs = 1440 // cadence_minutes
    weather_runs = 1440 // weather_minutes
    services = {
        "kac_airport_process_time": {"requests_per_run": 2, "runs_per_day": runs, "quota": 5000},
        "kac_airport_congestion": {"requests_per_run": 2, "runs_per_day": runs, "quota": 5000},
        "kac_parking_realtime_status": {"requests_per_run": 1, "runs_per_day": runs, "quota": 5000},
        "kac_parking_congestion": {"requests_per_run": 1, "runs_per_day": runs, "quota": 5000},
        "kac_flight_status": {"requests_per_run": 5, "runs_per_day": runs, "quota": 5000},
        "kac_flight_schedule": {"requests_per_run": 5, "runs_per_day": runs, "quota": 5000},
        "kma_api_hub_combined": {"requests_per_run": 6, "runs_per_day": weather_runs, "quota": 20000},
    }
    for value in services.values():
        value["requests_per_day"] = value["requests_per_run"] * value["runs_per_day"]
        value["quota_utilization_pct"] = round(value["requests_per_day"] / value["quota"] * 100, 2)
        value["headroom"] = value["quota"] - value["requests_per_day"]
    kac_total = sum(value["requests_per_day"] for name, value in services.items() if name.startswith("kac_"))
    kma_total = services["kma_api_hub_combined"]["requests_per_day"]
    # During the temporary external+GitHub scheduler overlap, every KAC source
    # may be requested twice. KMA remains cadence-gated by shared data-branch
    # state unless an operator explicitly forces it.
    overlap_kac_total = kac_total * 2
    overlap_total = overlap_kac_total + kma_total
    return {
        "cadence_minutes": cadence_minutes,
        "weather_minutes": weather_minutes,
        "services": services,
        "totals": {
            "kac_requests_per_day": kac_total,
            "kma_requests_per_day": kma_total,
            "all_requests_per_day": kac_total + kma_total,
            "requests_60_days": (kac_total + kma_total) * 60,
            "requests_90_days": (kac_total + kma_total) * 90,
        },
        "temporary_dual_scheduler_overlap": {
            "assumption": "two 15-minute clocks; shared state; force_weather=false",
            "kac_requests_per_day": overlap_kac_total,
            "kma_requests_per_day": kma_total,
            "all_requests_per_day": overlap_total,
            "kac_shared_pool_utilization_pct": round(overlap_kac_total / 5000 * 100, 2),
            "all_services_within_published_limits": all(
                value["requests_per_day"] * (2 if name.startswith("kac_") else 1) <= value["quota"]
                for name, value in services.items()
            ),
        },
    }


def _request_specs(now: datetime) -> list[RequestSpec]:
    local = now.astimezone(KST)
    start_minutes = max(0, local.hour * 60 + local.minute - 60)
    end_minutes = min(23 * 60 + 59, local.hour * 60 + local.minute + 60)
    start = f"{start_minutes // 60:02d}{start_minutes % 60:02d}"
    end = f"{end_minutes // 60:02d}{end_minutes % 60:02d}"
    common_kac = {"pageNo": "1", "numOfRows": "1000", "type": "json"}
    specs = [
        RequestSpec(
            "kac_process_time_v1",
            "Korea Airports Corporation",
            "https://apis.data.go.kr/B551178/airport-process-time",
            "/v1",
            common_kac,
            "serviceKey",
            "DATA_GO_KR_SERVICE_KEY",
            CADENCE_SECONDS,
            ("GMP", "CJU"),
            ("IATA_APCD", "PRC_HR", "STY_TCT_AVG_ALL"),
        ),
        RequestSpec(
            "kac_process_time_v2",
            "Korea Airports Corporation",
            "https://apis.data.go.kr/B551178/airport-process-time",
            "/v2",
            common_kac,
            "serviceKey",
            "DATA_GO_KR_SERVICE_KEY",
            CADENCE_SECONDS,
            ("PUS", "CJJ", "TAE"),
            ("IATA_APCD", "PRC_HR", "STY_TCT_AVG_ALL"),
        ),
        RequestSpec(
            "kac_congestion_v1",
            "Korea Airports Corporation",
            "https://apis.data.go.kr/B551178/airport-congestion",
            "/v1",
            common_kac,
            "serviceKey",
            "DATA_GO_KR_SERVICE_KEY",
            CADENCE_SECONDS,
            ("GMP", "CJU"),
            (),  # The official v1 Swagger currently declares items as a string.
        ),
        RequestSpec(
            "kac_congestion_v2",
            "Korea Airports Corporation",
            "https://apis.data.go.kr/B551178/airport-congestion",
            "/v2",
            common_kac,
            "serviceKey",
            "DATA_GO_KR_SERVICE_KEY",
            CADENCE_SECONDS,
            ("PUS", "CJJ", "TAE"),
            ("IATA_APCD", "PRC_HR", "CGDR_ALL_LVL"),
        ),
        RequestSpec(
            "kac_parking",
            "Korea Airports Corporation",
            "https://apis.data.go.kr/B551178/parking-realtime-status",
            "/info",
            common_kac,
            "serviceKey",
            "DATA_GO_KR_SERVICE_KEY",
            CADENCE_SECONDS,
            tuple(airport.iata for airport in AIRPORTS),
            ("parkingIstay", "parkingFullSpace", "parkingGetdate", "parkingGettime"),
        ),
        RequestSpec(
            "kac_parking_congestion",
            "Korea Airports Corporation",
            "https://apis.data.go.kr/B551178/parking-congestion",
            "/info",
            common_kac,
            "serviceKey",
            "DATA_GO_KR_SERVICE_KEY",
            CADENCE_SECONDS,
            tuple(airport.iata for airport in AIRPORTS),
            (
                "parkingAirportCodeName",
                "parkingCongestion",
                "parkingCongestionDegree",
                "parkingOccupiedSpace",
                "parkingTotalSpace",
                "sysGetdate",
                "sysGettime",
            ),
        ),
    ]
    for airport in AIRPORTS:
        specs.append(
            RequestSpec(
                f"kac_flight_{airport.iata}",
                "Korea Airports Corporation",
                "https://apis.data.go.kr/B551178/flight-status",
                "/depart",
                {
                    "pageNo": "1",
                    "numOfRows": "1000",
                    "searchday": local.strftime("%Y%m%d"),
                    "from_time": start,
                    "to_time": end,
                    "airport_code": airport.iata,
                    "line": "D",
                    "type": "json",
                },
                "serviceKey",
                "DATA_GO_KR_SERVICE_KEY",
                CADENCE_SECONDS,
                (airport.iata,),
                ("fgenTime", "flightid", "scheduledatetime"),
            )
        )
    for airport in AIRPORTS:
        specs.append(
            RequestSpec(
                f"kac_flight_schedule_{airport.iata}",
                "Korea Airports Corporation",
                "https://apis.data.go.kr/B551178/flight-schedule",
                "/dom",
                {
                    "pageNo": "1",
                    "numOfRows": "1000",
                    "schDate": local.strftime("%Y%m%d"),
                    "schDeptCityCode": airport.iata,
                    "type": "json",
                },
                "serviceKey",
                "DATA_GO_KR_SERVICE_KEY",
                CADENCE_SECONDS,
                (airport.iata,),
                (
                    "domesticNum",
                    "domesticStartTime",
                    "domesticArrivalTime",
                    "startcityCode",
                    "arrivalcityCode",
                    "domesticStdate",
                    "domesticEddate",
                ),
            )
        )
    for airport in AIRPORTS:
        specs.append(
            RequestSpec(
                f"kma_metar_{airport.iata}",
                "Korea Meteorological Administration API Hub",
                "https://apihub.kma.go.kr/api/typ02/openApi/AmmIwxxmService",
                "/getMetar",
                {"pageNo": "1", "numOfRows": "10", "dataType": "JSON", "icao": airport.icao},
                "authKey",
                "KMA_API_HUB_KEY",
                WEATHER_CADENCE_SECONDS,
                (airport.iata,),
                ("om:phenomenonTime", "iwxxm:airTemperature"),
            )
        )
    specs.append(
        RequestSpec(
            "kma_airport_warning",
            "Korea Meteorological Administration API Hub",
            "https://apihub.kma.go.kr/api/typ02/openApi/AmmService",
            "/getWarning",
            {"pageNo": "1", "numOfRows": "100", "dataType": "JSON"},
            "authKey",
            "KMA_API_HUB_KEY",
            WEATHER_CADENCE_SECONDS,
            tuple(airport.iata for airport in AIRPORTS),
            ("tm", "icaoCode", "wrngType", "wrngMsg"),
        )
    )
    return specs


def _safe_query(spec: RequestSpec) -> dict[str, str]:
    return {**spec.params, spec.secret_param: "REDACTED"}


def _urls(spec: RequestSpec, secret: str | None) -> tuple[str | None, str]:
    endpoint = f"{spec.base_url}{spec.path}"
    safe_url = f"{endpoint}?{urllib.parse.urlencode(_safe_query(spec))}"
    if not secret:
        return None, safe_url
    query = urllib.parse.urlencode(spec.params)
    encoded_secret = urllib.parse.quote(secret, safe="%")
    return f"{endpoint}?{query}&{spec.secret_param}={encoded_secret}", safe_url


def _redact(value: str, secrets: Iterable[str | None]) -> str:
    result = value
    for secret in secrets:
        if not secret:
            continue
        variants = {secret, urllib.parse.quote(secret, safe=""), urllib.parse.quote(secret, safe="%")}
        for variant in variants:
            if variant:
                result = result.replace(variant, "REDACTED")
    return result


def _xml_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        key = child.tag.split("}")[-1]
        value = _xml_value(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def parse_payload(raw: bytes) -> tuple[dict[str, Any], str]:
    stripped = raw.lstrip()
    if stripped.startswith((b"{", b"[")):
        parsed = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(parsed, dict):
            raise ValueError("API payload root must be an object")
        return parsed, "application/json"
    root = ET.fromstring(raw)
    return {root.tag.split("}")[-1]: _xml_value(root)}, "application/xml"


def _api_root(parsed: dict[str, Any]) -> dict[str, Any]:
    gateway_error = parsed.get("OpenAPI_ServiceResponse")
    if isinstance(gateway_error, dict):
        common_header = gateway_error.get("cmmMsgHeader")
        if isinstance(common_header, dict):
            code = str(common_header.get("returnReasonCode", "UNKNOWN"))
            message = common_header.get(
                "returnAuthMsg", common_header.get("errMsg", "unknown gateway error")
            )
            raise RuntimeError(f"OpenAPI gateway result {code}: {message}")
    root = parsed.get("response", parsed)
    if isinstance(root, dict) and len(root) == 1:
        only = next(iter(root.values()))
        if isinstance(only, dict) and ("header" in only or "body" in only):
            root = only
    if not isinstance(root, dict):
        raise ValueError("API response is not an object")
    header = root.get("header")
    if isinstance(header, dict):
        code = str(header.get("resultCode", header.get("result_code", "00")))
        if code not in {"0", "00", "0000", "INFO-000"}:
            message = header.get("resultMsg", header.get("result_msg", "unknown API error"))
            raise RuntimeError(f"API result {code}: {message}")
    return root


def _items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    root = _api_root(parsed)
    body = root.get("body", root)
    if not isinstance(body, dict):
        return []
    items = body.get("items", body.get("item", []))
    if isinstance(items, dict) and "item" in items:
        items = items["item"]
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _get(item: dict[str, Any], *names: str) -> Any:
    folded = {str(key).casefold(): value for key, value in item.items()}
    for name in names:
        if name in item:
            return item[name]
        if name.casefold() in folded:
            return folded[name.casefold()]
    return None


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        for key in ("value", "_value", "content", "text", "#text"):
            if key in value:
                return _scalar(value[key])
        for nested in value.values():
            candidate = _scalar(nested)
            if candidate not in (None, ""):
                return candidate
    if isinstance(value, list):
        for nested in value:
            candidate = _scalar(nested)
            if candidate not in (None, ""):
                return candidate
    return None


def _find_recursive(value: Any, *names: str) -> Any:
    targets = {name.casefold().split(":")[-1] for name in names}
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold().split(":")[-1] in targets:
                return _scalar(nested)
        for nested in value.values():
            found = _find_recursive(nested, *names)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_recursive(nested, *names)
            if found not in (None, ""):
                return found
    return None


def _number(value: Any, *, integer: bool = False) -> int | float | None:
    value = _scalar(value)
    if value in (None, "", "-"):
        return None
    try:
        result = float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    return int(result) if integer else result


def _datetime(value: Any, *, default_tz: timezone = KST) -> datetime | None:
    value = _scalar(value)
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=default_tz) if parsed.tzinfo is None else parsed
    except ValueError:
        pass
    digits = re.sub(r"\D", "", text)
    for length, pattern in ((14, "%Y%m%d%H%M%S"), (12, "%Y%m%d%H%M"), (10, "%Y%m%d%H"), (8, "%Y%m%d")):
        if len(digits) >= length:
            try:
                return datetime.strptime(digits[:length], pattern).replace(tzinfo=default_tz)
            except ValueError:
                continue
    return None


def _iso(value: Any, *, default_tz: timezone = KST) -> str | None:
    parsed = _datetime(value, default_tz=default_tz)
    return parsed.isoformat() if parsed else (str(value) if value not in (None, "") else None)


def _airport_code(item: dict[str, Any]) -> str | None:
    direct = _get(
        item,
        "IATA_APCD",
        "airportCode",
        "airport_code",
        "schAirportCode",
        "startcityCode",
        "depcitycode",
    )
    if direct and str(direct).upper() in AIRPORT_BY_IATA:
        return str(direct).upper()
    icao = _get(item, "icao", "icaoCode")
    if icao and str(icao).upper() in AIRPORT_BY_ICAO:
        return AIRPORT_BY_ICAO[str(icao).upper()].iata
    haystack = " ".join(
        str(value)
        for value in (
            _get(item, "aprKor", "airportKor", "airportName", "startcity", "depcity"),
            _get(item, "aprEng", "airportEng"),
        )
        if value
    ).casefold()
    for airport in AIRPORTS:
        if airport.name_ko in haystack or airport.name_en.casefold() in haystack:
            return airport.iata
    return None


def _source_timestamp(source_id: str, parsed: dict[str, Any]) -> str | None:
    items = _items(parsed)
    candidates: list[Any] = []
    for item in items:
        if source_id.startswith(("kac_process_time", "kac_congestion")):
            candidates.append(_get(item, "PRC_HR"))
        elif source_id == "kac_parking":
            candidates.append(f"{_get(item, 'parkingGetdate') or ''}{_get(item, 'parkingGettime') or ''}")
        elif source_id == "kac_parking_congestion":
            candidates.append(f"{_get(item, 'sysGetdate') or ''}{_get(item, 'sysGettime') or ''}")
        elif source_id.startswith("kac_flight_"):
            candidates.append(_get(item, "fgenTime", "fgentime"))
        elif source_id.startswith("kma_metar_"):
            candidates.append(_find_recursive(item, "phenomenonTime", "tm"))
        elif source_id == "kma_airport_warning":
            candidates.append(_get(item, "tm"))
    parsed_values = [_datetime(value) for value in candidates]
    valid = [value for value in parsed_values if value]
    return max(valid).isoformat() if valid else None


def _missing_fields(spec: RequestSpec, parsed: dict[str, Any]) -> list[str]:
    items = _items(parsed)
    if not items:
        return ["items"]

    def contains_field(value: Any, field: str) -> bool:
        target = field.casefold().split(":")[-1]
        if isinstance(value, dict):
            return any(
                str(key).casefold().split(":")[-1] == target or contains_field(nested, field)
                for key, nested in value.items()
            )
        if isinstance(value, list):
            return any(contains_field(nested, field) for nested in value)
        return False

    missing = [
        field for field in spec.expected_fields if any(not contains_field(item, field) for item in items)
    ]
    root = _api_root(parsed)
    body = root.get("body", root)
    total_count = _number(body.get("totalCount"), integer=True) if isinstance(body, dict) else None
    if total_count is not None and total_count > len(items):
        missing.append("pagination_incomplete")
    return missing


def _is_due(state: dict[str, Any], spec: RequestSpec, now: datetime, *, force_weather: bool) -> bool:
    if force_weather or spec.cadence_seconds == CADENCE_SECONDS:
        return True
    entry = state.get("sources", {}).get(spec.source_id, {})
    previous = _datetime(entry.get("collected_at"), default_tz=UTC)
    return previous is None or (now - previous.astimezone(UTC)).total_seconds() >= spec.cadence_seconds - 60


def _fixture_payloads(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    responses = fixture.get("responses")
    if not isinstance(responses, dict):
        raise ValueError(f"fixture has no response map: {path}")
    return responses


def _empty_components() -> dict[str, dict[str, Any]]:
    return {
        airport.iata: {
            "process": None,
            "congestion": None,
            "parking": [],
            "parking_congestion": [],
            "flights": [],
            "flight_schedule": [],
            "weather": None,
            "warnings": [],
            "source_timestamps": {},
        }
        for airport in AIRPORTS
    }


def _apply_payload(components: dict[str, dict[str, Any]], source_id: str, parsed: dict[str, Any]) -> None:
    items = _items(parsed)
    if source_id.startswith("kac_process_time"):
        for item in items:
            code = _airport_code(item)
            if not code:
                continue
            components[code]["process"] = {
                "operating": str(_get(item, "OPR_STS_CD") or "") == "1",
                "stage_a_seconds": _number(_get(item, "STY_TCT_AVG_A"), integer=True),
                "stage_b_seconds": _number(_get(item, "STY_TCT_AVG_B"), integer=True),
                "stage_c_seconds": _number(_get(item, "STY_TCT_AVG_C"), integer=True),
                "provider_stage_d_seconds": _number(_get(item, "STY_TCT_AVG_D"), integer=True),
                "total_seconds": _number(_get(item, "STY_TCT_AVG_ALL"), integer=True),
            }
            components[code]["source_timestamps"]["process_time"] = _iso(_get(item, "PRC_HR"))
    elif source_id.startswith("kac_congestion"):
        for item in items:
            code = _airport_code(item)
            if not code:
                continue
            components[code]["congestion"] = {
                "stage_a_level": _number(_get(item, "CGDR_A_LVL"), integer=True),
                "stage_b_level": _number(_get(item, "CGDR_B_LVL"), integer=True),
                "stage_c_level": _number(_get(item, "CGDR_C_LVL"), integer=True),
                "overall_level": _number(_get(item, "CGDR_ALL_LVL"), integer=True),
            }
            components[code]["source_timestamps"]["congestion"] = _iso(_get(item, "PRC_HR"))
    elif source_id == "kac_parking":
        for item in items:
            code = _airport_code(item)
            if not code:
                continue
            components[code]["parking"].append(
                {
                    "name": _get(item, "parkingAirportCodeName"),
                    "occupied": _number(_get(item, "parkingIstay"), integer=True),
                    "capacity": _number(_get(item, "parkingFullSpace"), integer=True),
                    "entries": _number(_get(item, "parkingIincnt"), integer=True),
                    "exits": _number(_get(item, "parkingIoutcnt"), integer=True),
                }
            )
            timestamp = _iso(f"{_get(item, 'parkingGetdate') or ''}{_get(item, 'parkingGettime') or ''}")
            components[code]["source_timestamps"]["parking"] = timestamp
    elif source_id == "kac_parking_congestion":
        for item in items:
            code = _airport_code(item)
            if not code:
                continue
            components[code]["parking_congestion"].append(
                {
                    "name": _get(item, "parkingAirportCodeName"),
                    "provider_level": _get(item, "parkingCongestion"),
                    "provider_degree_raw": _get(item, "parkingCongestionDegree"),
                    "provider_degree_percent": _number(_get(item, "parkingCongestionDegree")),
                    "occupied": _number(_get(item, "parkingOccupiedSpace"), integer=True),
                    "capacity": _number(_get(item, "parkingTotalSpace"), integer=True),
                }
            )
            timestamp = _iso(f"{_get(item, 'sysGetdate') or ''}{_get(item, 'sysGettime') or ''}")
            components[code]["source_timestamps"]["parking_congestion"] = timestamp
    elif source_id.startswith("kac_flight_"):
        code = source_id.rsplit("_", 1)[-1]
        if source_id.startswith("kac_flight_schedule_"):
            for item in items:
                components[code]["flight_schedule"].append(
                    {
                        "flight_id": _get(item, "domesticNum"),
                        "origin_iata": _get(item, "startcityCode"),
                        "origin_name": _get(item, "startcity"),
                        "destination_iata": _get(item, "arrivalcityCode"),
                        "destination_name": _get(item, "arrivalcity"),
                        "departure_time_local": _get(item, "domesticStartTime"),
                        "arrival_time_local": _get(item, "domesticArrivalTime"),
                        "valid_from": _iso(_get(item, "domesticStdate")),
                        "valid_to": _iso(_get(item, "domesticEddate")),
                        "operates": {
                            "monday": _get(item, "domesticMon"),
                            "tuesday": _get(item, "domesticTue"),
                            "wednesday": _get(item, "domesticWed"),
                            "thursday": _get(item, "domesticThu"),
                            "friday": _get(item, "domesticFri"),
                            "saturday": _get(item, "domesticSat"),
                            "sunday": _get(item, "domesticSun"),
                        },
                        "airline_ko": _get(item, "airlineKorean"),
                        "airline_en": _get(item, "airlineEnglish"),
                        "flight_purpose": _get(item, "flightPurpose"),
                    }
                )
            # The /dom operation publishes schedule validity dates but no data-generation timestamp.
            components[code]["source_timestamps"]["flight_schedule"] = None
        else:
            for item in items:
                components[code]["flights"].append(
                    {
                        "flight_id": _get(item, "flightid", "airFln", "AIR_FLN"),
                        "scheduled_at": _iso(_get(item, "scheduledatetime", "std", "STD")),
                        "estimated_at": _iso(_get(item, "estimateddatetime", "etd", "ETD")),
                        "status": _get(item, "rmkKor", "RMK_KOR"),
                        "destination_iata": _get(item, "arrvAirportCode", "arrAirportCode"),
                        "destination_name": _get(item, "arrAirport"),
                        "source_flight_id": _get(item, "fid", "UFID"),
                    }
                )
            components[code]["source_timestamps"]["flight_status"] = _source_timestamp(source_id, parsed)
    elif source_id.startswith("kma_metar_"):
        code = source_id.rsplit("_", 1)[-1]
        item = items[0] if items else parsed
        observed = _find_recursive(item, "phenomenonTime", "tm")
        components[code]["weather"] = {
            "observed_at": _iso(observed, default_tz=UTC),
            "metar": _find_recursive(item, "msgText", "metarMsg"),
            "temperature_c": _number(_find_recursive(item, "airTemperature", "ta")),
            "dewpoint_c": _number(_find_recursive(item, "dewpointTemperature", "td")),
            "qnh_hpa": _number(_find_recursive(item, "qnh", "ps")),
            "wind_direction_deg": _number(_find_recursive(item, "meanWindDirection", "wd")),
            "wind_speed": _number(_find_recursive(item, "meanWindSpeed", "ws")),
            "wind_gust": _number(_find_recursive(item, "windGustSpeed", "gst")),
            "visibility_m": _number(_find_recursive(item, "AerodromeHorizontalVisibility", "visibility", "vs")),
            "present_weather": _find_recursive(item, "presentWeather", "ww"),
        }
        components[code]["source_timestamps"]["weather"] = _iso(observed, default_tz=UTC)
    elif source_id == "kma_airport_warning":
        for item in items:
            code = _airport_code(item)
            if not code:
                continue
            components[code]["warnings"].append(
                {
                    "issued_at": _iso(_get(item, "tm")),
                    "type": _get(item, "wrngType"),
                    "valid_from": _iso(_get(item, "validTm1", "stTm")),
                    "valid_to": _iso(_get(item, "validTm2", "edTm")),
                    "message": _get(item, "wrngMsg"),
                }
            )
            components[code]["source_timestamps"]["weather_warning"] = _iso(_get(item, "tm"))


def _group_status(observations: dict[str, SourceObservation], source_ids: list[str]) -> str:
    statuses = [observations[source_id].status for source_id in source_ids if source_id in observations]
    if not statuses:
        return "NOT_REQUESTED"
    if all(status == "SKIPPED_NOT_DUE" for status in statuses):
        return "SKIPPED_NOT_DUE"
    if any(status == "ERROR" for status in statuses):
        return "ERROR"
    if any(status == "PARTIAL" for status in statuses):
        return "PARTIAL"
    if all(status == "DUPLICATE" for status in statuses):
        return "DUPLICATE"
    return "OK"


_SCHEDULE_DAY_KEYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _schedule_departure_at(schedule: dict[str, Any], local: datetime) -> datetime | None:
    valid_from = _datetime(schedule.get("valid_from"))
    valid_to = _datetime(schedule.get("valid_to"))
    if valid_from and local.date() < valid_from.astimezone(KST).date():
        return None
    if valid_to and local.date() > valid_to.astimezone(KST).date():
        return None
    flag = schedule.get("operates", {}).get(_SCHEDULE_DAY_KEYS[local.weekday()])
    if str(flag or "").strip().upper() not in {"Y", "1", "TRUE"}:
        return None
    digits = re.sub(r"\D", "", str(schedule.get("departure_time_local") or ""))
    if len(digits) < 4:
        return None
    hour, minute = int(digits[:2]), int(digits[2:4])
    if hour > 23 or minute > 59:
        return None
    return local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def normalize_records(
    parsed_payloads: dict[str, dict[str, Any]],
    observations: dict[str, SourceObservation],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    components = _empty_components()
    for source_id, parsed in parsed_payloads.items():
        _apply_payload(components, source_id, parsed)
    local = now.astimezone(KST)
    calendar = calendar_features(local.date())
    records: list[dict[str, Any]] = []
    for airport in AIRPORTS:
        value = components[airport.iata]
        component_sources = {
            "process_time": "kac_process_time_v1" if airport.iata in {"GMP", "CJU"} else "kac_process_time_v2",
            "congestion": "kac_congestion_v1" if airport.iata in {"GMP", "CJU"} else "kac_congestion_v2",
            "flight_status": f"kac_flight_{airport.iata}",
            "flight_schedule": f"kac_flight_schedule_{airport.iata}",
            "parking": "kac_parking",
            "parking_congestion": "kac_parking_congestion",
            "weather": f"kma_metar_{airport.iata}",
            "weather_warning": "kma_airport_warning",
        }
        for component_name, source_id in component_sources.items():
            observation = observations.get(source_id)
            if observation and observation.source_timestamp:
                value["source_timestamps"].setdefault(component_name, observation.source_timestamp)
        process = value["process"] or {}
        congestion = value["congestion"] or {}
        lots = value["parking"]
        congestion_lots = value["parking_congestion"]
        capacity_values = [lot["capacity"] for lot in lots if lot["capacity"] is not None]
        occupied_values = [lot["occupied"] for lot in lots if lot["occupied"] is not None]
        capacity = sum(capacity_values) if capacity_values else None
        occupied = sum(occupied_values) if occupied_values else None
        available = max(0, capacity - occupied) if capacity is not None and occupied is not None else None
        occupancy_ratio = round(occupied / capacity, 6) if capacity and occupied is not None else None
        congestion_capacity_values = [
            lot["capacity"] for lot in congestion_lots if lot["capacity"] is not None
        ]
        congestion_occupied_values = [
            lot["occupied"] for lot in congestion_lots if lot["occupied"] is not None
        ]
        congestion_capacity = sum(congestion_capacity_values) if congestion_capacity_values else None
        congestion_occupied = sum(congestion_occupied_values) if congestion_occupied_values else None
        upcoming: list[dict[str, Any]] = []
        delayed = 0
        cancelled = 0
        window_end = local + timedelta(minutes=30)
        for flight in value["flights"]:
            scheduled = _datetime(flight["scheduled_at"])
            if scheduled and local <= scheduled.astimezone(KST) <= window_end:
                upcoming.append(flight)
                status = str(flight.get("status") or "").casefold()
                delayed += int("지연" in status or "delay" in status)
                cancelled += int("결항" in status or "cancel" in status)
        timetable_upcoming: list[dict[str, Any]] = []
        for schedule in value["flight_schedule"]:
            departure_at = _schedule_departure_at(schedule, local)
            if departure_at and local <= departure_at <= window_end:
                timetable_upcoming.append({**schedule, "scheduled_at": departure_at.isoformat()})
        source_status = {
            "process_time": _group_status(
                observations,
                [component_sources["process_time"]],
            ),
            "congestion": _group_status(
                observations,
                [component_sources["congestion"]],
            ),
            "flight_status": _group_status(observations, [component_sources["flight_status"]]),
            "flight_schedule": _group_status(observations, [component_sources["flight_schedule"]]),
            "parking": _group_status(observations, [component_sources["parking"]]),
            "parking_congestion": _group_status(
                observations, [component_sources["parking_congestion"]]
            ),
            "weather": _group_status(observations, [component_sources["weather"]]),
            "weather_warning": _group_status(observations, [component_sources["weather_warning"]]),
        }
        missing = [
            section
            for section in (
                "process_time",
                "congestion",
                "parking",
                "parking_congestion",
                "flight_status",
                "flight_schedule",
                "weather",
                "weather_warning",
            )
            if source_status[section] in {"ERROR", "PARTIAL"}
        ]
        if value["process"] is None:
            missing.append("process_time_values")
        if value["congestion"] is None:
            missing.append("congestion_values")
        if source_status["parking"] != "SKIPPED_NOT_DUE" and not lots:
            missing.append("parking_values")
        if source_status["parking_congestion"] != "SKIPPED_NOT_DUE" and not congestion_lots:
            missing.append("parking_congestion_values")
        if source_status["weather"] != "SKIPPED_NOT_DUE" and value["weather"] is None:
            missing.append("weather_values")
        friction = {
            "checkin": {
                "to_identity_seconds": process.get("stage_a_seconds"),
                "to_identity_level": congestion.get("stage_a_level"),
            },
            "identity": {
                "to_security_seconds": process.get("stage_b_seconds"),
                "to_security_level": congestion.get("stage_b_level"),
            },
            "security": {
                "to_boarding_seconds": process.get("stage_c_seconds"),
                "to_boarding_level": congestion.get("stage_c_level"),
            },
            "boarding": {
                "to_departure_seconds": process.get("provider_stage_d_seconds"),
                "to_departure_level": None,
                "level_reason": "KAC congestion publishes three stages; no fourth-stage congestion level",
            },
            "provider_stage_d_seconds": process.get("provider_stage_d_seconds"),
            "provider_stage_d_mapping": "boarding_to_aircraft_departure",
            "total_seconds": process.get("total_seconds"),
            "overall_level": congestion.get("overall_level"),
            "operating": process.get("operating"),
        }
        record = {
            "schema_version": "airport-friction-0.1",
            "timestamp": now.isoformat(),
            "airport": asdict(airport),
            "friction": friction,
            "departures_30m": len(upcoming),
            "delayed_departures_30m": delayed,
            "cancelled_departures_30m": cancelled,
            "timetable_departures_30m": len(timetable_upcoming),
            "timetable_minus_live_departures_30m": len(timetable_upcoming) - len(upcoming),
            "departure_window": {"start": local.isoformat(), "end": window_end.isoformat()},
            "flights_in_requested_window": value["flights"],
            "schedule_in_departure_window": timetable_upcoming,
            "parking": {
                "capacity": capacity,
                "occupied": occupied,
                "available": available,
                "occupancy_ratio": occupancy_ratio,
                "facilities": lots,
                "provider_congestion": {
                    "capacity": congestion_capacity,
                    "occupied": congestion_occupied,
                    "facilities": congestion_lots,
                },
                "realtime_minus_congestion_occupied": (
                    occupied - congestion_occupied
                    if occupied is not None and congestion_occupied is not None
                    else None
                ),
            },
            "weather": value["weather"],
            "weather_warnings": value["warnings"],
            "calendar": calendar,
            "source_timestamps": value["source_timestamps"],
            "source_status": source_status,
            "missing_sections": sorted(set(missing)),
            "quality_status": "PARTIAL" if missing else "OK",
        }
        record["record_hash"] = sha256_json(record)
        records.append(record)
    return records


class AirportFrictionCollector:
    def __init__(
        self,
        *,
        data_go_key: str | None = None,
        kma_key: str | None = None,
        client: HttpClient | None = None,
        fixture_path: Path | None = None,
    ) -> None:
        self.data_go_key = data_go_key
        self.kma_key = kma_key
        self.client = client or HttpClient(timeout=30, max_retries=2)
        self.fixture_path = fixture_path or FIXTURE_PATH

    def _secret(self, spec: RequestSpec) -> str | None:
        return self.data_go_key if spec.secret_env == "DATA_GO_KR_SERVICE_KEY" else self.kma_key

    def collect(
        self,
        output_root: Path,
        *,
        mode: str = "live",
        now: datetime | None = None,
        trigger_source: str = "manual",
        force_weather: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"live", "fixture"}:
            raise ValueError("mode must be 'live' or 'fixture'")
        now = now or datetime.now(UTC)
        now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
        collected_at = now.isoformat()
        run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        state_path = namespace_path(output_root, "state", NAMESPACE, "latest_hashes.json")
        state = read_json_state(state_path, namespace=NAMESPACE)
        state.setdefault("sources", {})
        state.setdefault("storage", {"total_new_gzip_bytes": 0})
        health_schedule = schedule_health(
            state,
            now,
            cadence_seconds=CADENCE_SECONDS,
            gap_threshold_multiplier=GAP_THRESHOLD_MULTIPLIER,
        )
        fixture_payloads = _fixture_payloads(self.fixture_path) if mode == "fixture" else {}
        observations: dict[str, SourceObservation] = {}
        parsed_payloads: dict[str, dict[str, Any]] = {}
        payloads: dict[str, bytes] = {}
        specs = _request_specs(now)

        for spec in specs:
            secret = self._secret(spec)
            request_url, safe_url = _urls(spec, secret)
            safe_query = _safe_query(spec)
            response: HttpResponse | None = None
            if not _is_due(state, spec, now, force_weather=force_weather):
                observations[spec.source_id] = SourceObservation(
                    spec.source_id,
                    spec.provider,
                    "SKIPPED_NOT_DUE",
                    collected_at,
                    state["sources"].get(spec.source_id, {}).get("source_timestamp"),
                    safe_url,
                    safe_query,
                    list(spec.airports),
                    state["sources"].get(spec.source_id, {}).get("content_hash"),
                    None,
                    0,
                    0,
                    [],
                    None,
                    0,
                    0,
                )
                continue
            try:
                if mode == "fixture":
                    if spec.source_id not in fixture_payloads:
                        raise KeyError(f"fixture response missing for {spec.source_id}")
                    body = (canonical_json(fixture_payloads[spec.source_id]) + "\n").encode("utf-8")
                    response = HttpResponse(body, 200, "application/json", 0, 0)
                    safe_url = f"fixture://airport-friction/{spec.source_id}"
                    safe_query = {"fixture": self.fixture_path.name}
                else:
                    if request_url is None:
                        raise RuntimeError(f"missing repository secret {spec.secret_env}")
                    response = self.client.request(request_url)
                parsed, mime_type = parse_payload(response.body)
                _api_root(parsed)
                content_hash = sha256_bytes(response.body)
                previous = state["sources"].get(spec.source_id, {})
                duplicate = previous.get("content_hash") == content_hash
                source_timestamp = _source_timestamp(spec.source_id, parsed)
                missing = _missing_fields(spec, parsed)
                raw_member = None
                compressed_bytes = 0
                if not duplicate:
                    suffix = "json" if "json" in mime_type else "xml"
                    raw_member = f"payloads/{slug(spec.source_id)}-{content_hash}.{suffix}.gz"
                    compressed = gzip.compress(response.body, compresslevel=6, mtime=0)
                    payloads[raw_member] = compressed
                    compressed_bytes = len(compressed)
                status = "DUPLICATE" if duplicate else "PARTIAL" if missing else "OK"
                observation = SourceObservation(
                    spec.source_id,
                    spec.provider,
                    status,
                    collected_at,
                    source_timestamp,
                    safe_url,
                    safe_query,
                    list(spec.airports),
                    content_hash,
                    raw_member,
                    len(response.body),
                    compressed_bytes,
                    missing,
                    response.status,
                    response.elapsed_ms,
                    response.retries,
                )
                observations[spec.source_id] = observation
                parsed_payloads[spec.source_id] = parsed
                state["sources"][spec.source_id] = {
                    "content_hash": content_hash,
                    "source_timestamp": source_timestamp,
                    "collected_at": collected_at,
                    "status": status,
                    "cadence_seconds": spec.cadence_seconds,
                }
            except Exception as exc:
                error = _redact(str(exc), (self.data_go_key, self.kma_key))
                http_status = getattr(exc, "status", None)
                if http_status is None and response is not None:
                    http_status = response.status
                latency_ms = getattr(exc, "elapsed_ms", None)
                if latency_ms is None:
                    latency_ms = response.elapsed_ms if response is not None else 0
                retries = getattr(exc, "retries", None)
                if retries is None:
                    retries = response.retries if response is not None else 0
                observations[spec.source_id] = SourceObservation(
                    spec.source_id,
                    spec.provider,
                    "ERROR",
                    collected_at,
                    None,
                    safe_url,
                    safe_query,
                    list(spec.airports),
                    None,
                    None,
                    0,
                    0,
                    list(spec.expected_fields) or ["items"],
                    http_status,
                    int(latency_ms),
                    int(retries),
                    error=error,
                )

        normalized = normalize_records(parsed_payloads, observations, now=now)
        source_gaps: list[dict[str, Any]] = []
        for spec in specs:
            entry = state["sources"].get(spec.source_id)
            if not entry:
                source_gaps.append({"source_id": spec.source_id, "status": "NO_SUCCESS_BASELINE"})
                continue
            previous = _datetime(entry.get("collected_at"), default_tz=UTC)
            age = round((now - previous.astimezone(UTC)).total_seconds()) if previous else None
            if age is None or age > spec.cadence_seconds * GAP_THRESHOLD_MULTIPLIER:
                source_gaps.append(
                    {
                        "source_id": spec.source_id,
                        "status": "STALE",
                        "age_seconds": age,
                        "cadence_seconds": spec.cadence_seconds,
                    }
                )

        succeeded = sum(value.status in {"OK", "PARTIAL", "DUPLICATE"} for value in observations.values())
        partials = sum(value.status == "PARTIAL" for value in observations.values())
        errors = sum(value.status == "ERROR" for value in observations.values())
        overall = "SUCCESS" if errors == 0 and partials == 0 else "PARTIAL" if succeeded else "FAILED"
        new_gzip_bytes = sum(value.raw_gzip_bytes for value in observations.values())
        state["storage"]["total_new_gzip_bytes"] = int(state["storage"].get("total_new_gzip_bytes", 0)) + new_gzip_bytes
        storage_warning = state["storage"]["total_new_gzip_bytes"] >= 500_000_000
        manifest = {
            "schema_version": 1,
            "normalized_schema_version": "airport-friction-0.1",
            "namespace": NAMESPACE,
            "collector_id": COLLECTOR_ID,
            "run_id": run_id,
            "status": overall,
            "mode": mode.upper(),
            "trigger_source": trigger_source,
            "collected_at": collected_at,
            "source_observations": [asdict(observations[spec.source_id]) for spec in specs],
            "normalized_records": normalized,
            "summary": {
                "airports": len(AIRPORTS),
                "sources_due_or_skipped": len(specs),
                "sources_succeeded": succeeded,
                "sources_partial": partials,
                "sources_skipped_not_due": sum(value.status == "SKIPPED_NOT_DUE" for value in observations.values()),
                "new_payloads": sum(value.raw_member is not None for value in observations.values()),
                "duplicates": sum(value.status == "DUPLICATE" for value in observations.values()),
                "errors": errors,
                "gzip_bytes": new_gzip_bytes,
            },
            "health": {
                "schedule": health_schedule,
                "source_gaps": source_gaps,
                "requests": {
                    "total_retries": sum(value.retries for value in observations.values()),
                    "max_latency_ms": max((value.latency_ms for value in observations.values()), default=0),
                    "missing_sections": sum(len(value.missing_sections) for value in observations.values()),
                },
                "storage": {
                    "new_gzip_bytes": new_gzip_bytes,
                    "cumulative_new_gzip_bytes": state["storage"]["total_new_gzip_bytes"],
                    "migration_threshold_bytes": 500_000_000,
                    "status": "MIGRATION_REVIEW" if storage_warning else "OK",
                },
            },
            "quota_budget": quota_budget(),
        }
        date_path = Path(now.strftime("%Y/%m/%d"))
        run_path = namespace_path(output_root, "runs", NAMESPACE, date_path, f"{run_id}.json")
        write_json_atomic(run_path, manifest)
        bundle_path: Path | None = None
        if payloads:
            bundle_path = namespace_path(output_root, "bundles", NAMESPACE, date_path, f"{run_id}.tar")
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(bundle_path, "w") as archive:
                add_bytes(
                    archive,
                    "manifest.json",
                    (canonical_json(manifest) + "\n").encode("utf-8"),
                    int(now.timestamp()),
                )
                for member_name, content in sorted(payloads.items()):
                    add_bytes(archive, member_name, content, int(now.timestamp()))
        state.update(
            {
                "version": 1,
                "namespace": NAMESPACE,
                "updated_at": collected_at,
                "last_run_id": run_id,
                "last_status": overall,
                "last_mode": mode.upper(),
                "last_trigger_source": trigger_source,
                "last_health": manifest["health"],
            }
        )
        write_json_atomic(state_path, state)
        return {
            "status": overall,
            "mode": mode.upper(),
            "run_id": run_id,
            "run_path": str(run_path),
            "bundle_path": str(bundle_path) if bundle_path else None,
            "health_status": health_schedule["status"],
            "missed_intervals": health_schedule["missed_intervals"],
            **manifest["summary"],
        }
