from __future__ import annotations

import html
import json
import re
import sqlite3
import urllib.parse
from dataclasses import dataclass
from typing import Any

from .http_client import HttpClient
from .storage import store_raw_payload
from .utils import canonical_json, sha256_json, slug, utc_now


NIA_BID_LIST_URL = "https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=78336"
DATA_TERMS = {
    "데이터",
    "개방",
    "공공데이터",
    "빅데이터",
    "정보",
    "플랫폼",
    "인공지능",
    "통합",
}


@dataclass(frozen=True)
class PreReleaseSignal:
    external_id: str
    title: str
    buyer_org: str
    posted_at: str | None
    notice_type: str
    source_url: str
    keywords: list[str]
    entities: list[str]
    metadata: dict[str, Any]


def _clean_html(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _notice_type(title: str) -> str:
    match = re.match(r"\[([^]]+)\]", title)
    return match.group(1).strip() if match else "UNKNOWN"


def _keywords(title: str) -> list[str]:
    return sorted(
        {
            token
            for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", title)
            if token not in {"사전규격공개", "조달입찰공고", "입찰공고", "사업", "용역", "위탁감리"}
        }
    )


def _external_id(href: str) -> str:
    params = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    for key in ("bcIdx", "bcidx", "boardNo"):
        if params.get(key):
            return params[key][0]
    return sha256_json(href)[:20]


def parse_nia_html(value: bytes | str, *, data_only: bool = False) -> list[PreReleaseSignal]:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    signals: list[PreReleaseSignal] = []
    pattern = re.compile(
        r"<a\b[^>]*href=[\"'](?P<href>[^\"']*View\.do\?[^\"']+)[\"'][^>]*>(?P<title>.*?)</a>(?P<tail>.*?)(?=</li>|<a\b)",
        re.I | re.S,
    )
    seen: set[str] = set()
    for match in pattern.finditer(text):
        title = _clean_html(match.group("title"))
        href = html.unescape(match.group("href"))
        if not title or title in {"입찰공고", "공지사항", "보도자료"}:
            continue
        external_id = _external_id(href)
        if external_id in seen:
            continue
        if data_only and not any(term in title for term in DATA_TERMS):
            continue
        tail = _clean_html(match.group("tail"))
        date_match = re.search(r"20\d{2}[.-]\d{2}[.-]\d{2}", tail)
        posted_at = date_match.group().replace(".", "-") if date_match else None
        source_url = urllib.parse.urljoin(NIA_BID_LIST_URL, href)
        terms = _keywords(title)
        entities = [term for term in terms if term.endswith(("청", "부", "원", "공사", "공단", "시", "도"))]
        signals.append(
            PreReleaseSignal(
                external_id=external_id,
                title=title,
                buyer_org="한국지능정보사회진흥원",
                posted_at=posted_at,
                notice_type=_notice_type(title),
                source_url=source_url,
                keywords=terms,
                entities=entities,
                metadata={"list_tail": tail[:500]},
            )
        )
        seen.add(external_id)
    return signals


def fetch_nia_signals(*, client: HttpClient | None = None, data_only: bool = True) -> tuple[list[PreReleaseSignal], bytes]:
    response = (client or HttpClient()).request(NIA_BID_LIST_URL)
    return parse_nia_html(response.body, data_only=data_only), response.body


def upsert_signals(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    signals: list[PreReleaseSignal],
    raw_payload: bytes | str | None = None,
    source_url: str = NIA_BID_LIST_URL,
    run_id: int | None = None,
    observed_at: str | None = None,
) -> dict[str, int]:
    observed_at = observed_at or utc_now()
    payload = raw_payload if raw_payload is not None else [signal.__dict__ for signal in signals]
    stored = store_raw_payload(
        conn,
        source_id=source_id,
        source_url=source_url,
        payload=payload,
        run_id=run_id,
        collected_at=observed_at,
        mime_type="text/html" if isinstance(payload, (bytes, str)) else "application/json",
    )
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    for signal in signals:
        signal_id = f"{slug(source_id, 25)}:{slug(signal.external_id, 60)}"
        content_hash = sha256_json(signal.__dict__)
        existing = conn.execute("SELECT content_hash FROM pre_release_signals WHERE signal_id=?", (signal_id,)).fetchone()
        if existing is None:
            counts["new"] += 1
        elif existing["content_hash"] == content_hash:
            counts["unchanged"] += 1
        else:
            counts["updated"] += 1
        conn.execute(
            """
            INSERT INTO pre_release_signals(
                signal_id, source_id, external_id, title, buyer_org, posted_at, notice_type,
                source_url, keywords_json, entities_json, content_hash, first_seen_at,
                last_seen_at, raw_payload_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
                title=excluded.title, buyer_org=excluded.buyer_org, posted_at=excluded.posted_at,
                notice_type=excluded.notice_type, source_url=excluded.source_url,
                keywords_json=excluded.keywords_json, entities_json=excluded.entities_json,
                content_hash=excluded.content_hash, last_seen_at=excluded.last_seen_at,
                raw_payload_id=excluded.raw_payload_id, metadata_json=excluded.metadata_json
            """,
            (
                signal_id,
                source_id,
                signal.external_id,
                signal.title,
                signal.buyer_org,
                signal.posted_at,
                signal.notice_type,
                signal.source_url,
                canonical_json(signal.keywords),
                canonical_json(signal.entities),
                content_hash,
                observed_at,
                observed_at,
                stored.payload_id,
                canonical_json(signal.metadata),
            ),
        )
    return counts


def link_signals_to_datasets(conn: sqlite3.Connection, *, min_confidence: float = 0.28) -> int:
    signals = conn.execute("SELECT * FROM pre_release_signals").fetchall()
    datasets = conn.execute("SELECT * FROM datasets").fetchall()
    count = 0
    for signal in signals:
        signal_terms = set(json.loads(signal["keywords_json"] or "[]"))
        for dataset in datasets:
            dataset_text = " ".join(
                [dataset["title"] or "", dataset["provider"] or "", dataset["description"] or ""]
            )
            dataset_terms = set(re.findall(r"[0-9A-Za-z가-힣]{2,}", dataset_text))
            matches = sorted(signal_terms & dataset_terms)
            meaningful = [term for term in matches if term not in DATA_TERMS]
            if not meaningful:
                continue
            confidence = min(1.0, 0.2 + 0.15 * len(meaningful))
            if signal["buyer_org"] and signal["buyer_org"] == dataset["provider"]:
                confidence += 0.15
            confidence = min(1.0, confidence)
            if confidence < min_confidence:
                continue
            conn.execute(
                """
                INSERT INTO signal_dataset_links(
                    signal_id, dataset_id, confidence, method, matched_terms_json, review_status, created_at
                ) VALUES (?, ?, ?, 'TOKEN_ENTITY_V1', ?, 'AUTO', ?)
                ON CONFLICT(signal_id, dataset_id) DO UPDATE SET
                    confidence=excluded.confidence, matched_terms_json=excluded.matched_terms_json,
                    review_status='AUTO'
                """,
                (signal["signal_id"], dataset["dataset_id"], confidence, canonical_json(meaningful), utc_now()),
            )
            count += 1
    return count
