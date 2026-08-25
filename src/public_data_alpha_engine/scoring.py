from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from .utils import canonical_json, utc_now


CALCULATION_VERSION = "foundry-v0.3-rules-1"

PRA_WEIGHTS: dict[str, int] = {
    "existing_payment_evidence": 20,
    "cost_substitution": 15,
    "join_amplification": 15,
    "release_probability": 10,
    "lead_time": 10,
    "data_time": 10,
    "distribution_payer": 10,
    "machine_processability": 5,
    "non_obviousness": 5,
}

SEED_WEIGHTS: dict[str, int] = {
    "past_reconstruction_impossibility": 25,
    "direct_money_link": 20,
    "multi_source_join_value": 15,
    "automated_collection": 15,
    "update_frequency": 10,
    "ground_truth_possible": 10,
    "storage_operations_cost": 5,
}

EPHEMERAL_WEIGHTS: dict[str, int] = {
    "overwrite_risk": 30,
    "historical_absence": 25,
    "refresh_velocity": 15,
    "economic_state": 20,
    "machine_capture": 10,
}

MONEY_TERMS = {
    "매출",
    "소비",
    "결제",
    "가격",
    "거래",
    "재고",
    "상권",
    "수요",
    "전력",
    "주문",
    "검색어",
    "편성",
    "요금",
    "입찰",
    "조달",
}
JOIN_TERMS = {"인구", "교통", "날씨", "행사", "상권", "카드", "업종", "지역", "시간", "통합", "복합"}
OUTCOME_TERMS = {"행사", "매출", "소비", "혼잡", "결제", "사고", "재난", "개방", "입찰", "계약", "수요"}


@dataclass(frozen=True)
class DimensionValue:
    rating: float
    rationale: str
    evidence: list[str]


def _bounded(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 2)


def _text(row: sqlite3.Row) -> str:
    values = [
        row["title"] or "",
        row["description"] or "",
        row["provider"] or "",
        row["update_frequency"] or "",
        row["machine_format"] or "",
    ]
    if "keywords_json" in row.keys():
        values.extend(json.loads(row["keywords_json"] or "[]"))
    return " ".join(values)


def _term_count(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term.casefold() in text.casefold())


def _frequency_rating(value: str) -> float:
    lowered = value.casefold()
    if any(token in lowered for token in ("실시간", "분", "real-time", "realtime")):
        return 10
    if any(token in lowered for token in ("일", "daily", "수시")):
        return 8
    if any(token in lowered for token in ("주", "weekly")):
        return 6
    if any(token in lowered for token in ("월", "monthly")):
        return 4
    if any(token in lowered for token in ("연", "year", "1회")):
        return 1
    return 4


def ephemeral_dimensions(row: sqlite3.Row) -> dict[str, DimensionValue]:
    text = _text(row)
    freq = _frequency_rating(row["update_frequency"] or "")
    history = (row["historical_availability"] or "UNKNOWN").upper()
    if history in {"NONE", "NOT_PROVIDED"}:
        history_rating = 10
    elif history in {"LIMITED", "PARTIAL"}:
        history_rating = 7
    elif history in {"AVAILABLE", "FULL"}:
        history_rating = 1
    else:
        history_rating = 7 if freq >= 8 else 4
    money_count = _term_count(text, MONEY_TERMS)
    machine = 10 if row["api_available"] else 7 if row["file_available"] else 2
    return {
        "overwrite_risk": DimensionValue(_bounded((freq + history_rating) / 2), "High refresh plus absent history implies overwrite risk.", [row["update_frequency"] or "unknown"]),
        "historical_absence": DimensionValue(history_rating, "Official or inferred historical replay availability.", [history]),
        "refresh_velocity": DimensionValue(freq, "Mapped from declared source refresh cadence.", [row["update_frequency"] or "unknown"]),
        "economic_state": DimensionValue(_bounded(2 + 1.6 * money_count), "Economic-state keywords found in metadata.", sorted(term for term in MONEY_TERMS if term in text)),
        "machine_capture": DimensionValue(machine, "API/file availability determines unattended capture feasibility.", [f"api={row['api_available']}", f"file={row['file_available']}"]),
    }


def seed_dimensions(row: sqlite3.Row) -> dict[str, DimensionValue]:
    text = _text(row)
    ephemeral = ephemeral_dimensions(row)
    freq = ephemeral["refresh_velocity"].rating
    money_count = _term_count(text, MONEY_TERMS)
    join_count = _term_count(text, JOIN_TERMS)
    outcome_count = _term_count(text, OUTCOME_TERMS)
    history_rating = ephemeral["historical_absence"].rating
    machine = 10 if row["api_available"] else 7 if row["file_available"] else 2
    metadata = json.loads(row["metadata_json"] or "{}")
    storage_hint = metadata.get("storage_estimate_bytes_day")
    if isinstance(storage_hint, (int, float)):
        storage_rating = 10 if storage_hint < 10_000_000 else 8 if storage_hint < 100_000_000 else 4
    else:
        storage_rating = 9 if machine >= 7 else 5
    return {
        "past_reconstruction_impossibility": DimensionValue(history_rating, "Uses official history status, falling back to cadence-based inference.", [row["historical_availability"]]),
        "direct_money_link": DimensionValue(_bounded(2 + 1.6 * money_count), "Money-linked terms in title/description/keywords.", sorted(term for term in MONEY_TERMS if term in text)),
        "multi_source_join_value": DimensionValue(_bounded(2 + 1.25 * join_count), "Distinct source/entity domains increase JOIN option value.", sorted(term for term in JOIN_TERMS if term in text)),
        "automated_collection": DimensionValue(machine, "Structured API/file access enables unattended capture.", [row["machine_format"] or "unknown"]),
        "update_frequency": DimensionValue(freq, "v0.3 favors recurring daily/weekly state changes.", [row["update_frequency"] or "unknown"]),
        "ground_truth_possible": DimensionValue(_bounded(3 + 1.4 * outcome_count), "Later observable outcomes can label captured states.", sorted(term for term in OUTCOME_TERMS if term in text)),
        "storage_operations_cost": DimensionValue(storage_rating, "Small structured snapshots receive the highest rating.", [str(storage_hint or "metadata-only estimate")]),
    }


def pra_dimensions_dataset(row: sqlite3.Row) -> dict[str, DimensionValue]:
    text = _text(row)
    money_count = _term_count(text, MONEY_TERMS)
    join_count = _term_count(text, JOIN_TERMS)
    ephemeral = ephemeral_dimensions(row)
    status = (row["public_status"] or "UNKNOWN").upper()
    release = 10 if status == "OPEN" else 7 if status == "OPEN_LINKED" else 4
    current_year = datetime.now(UTC).year
    expected = row["expected_release_year"]
    lead = 2 if status == "OPEN" else 8 if expected and expected >= current_year else 5
    machine = 10 if row["api_available"] else 7 if row["file_available"] else 2
    popularity = 0
    metadata = json.loads(row["metadata_json"] or "{}")
    for key in ("활용신청", "활용신청 수", "usage_count"):
        try:
            popularity = max(popularity, int(str(metadata.get(key, 0)).replace(",", "")))
        except ValueError:
            pass
    non_obvious = 8 if popularity < 100 else 6 if popularity < 1000 else 3
    return {
        "existing_payment_evidence": DimensionValue(_bounded(2 + 1.4 * money_count), "Metadata proximity to existing paid workflows.", sorted(term for term in MONEY_TERMS if term in text)),
        "cost_substitution": DimensionValue(_bounded(2 + machine * 0.35 + money_count * 0.7), "Free structured access can replace manual/paid collection.", [row["cost_status"], row["machine_format"] or "unknown"]),
        "join_amplification": DimensionValue(_bounded(2 + 1.25 * join_count), "Cross-domain terms proxy JOIN amplification.", sorted(term for term in JOIN_TERMS if term in text)),
        "release_probability": DimensionValue(release, "Current registry status is the base release-probability evidence.", [status]),
        "lead_time": DimensionValue(lead, "Open data has little pre-release lead; planned data receives more.", [str(expected or status)]),
        "data_time": DimensionValue(round(sum(ephemeral[name].rating * weight / 100 for name, weight in EPHEMERAL_WEIGHTS.items()), 2), "Ephemeral Score is reused as Data Time rating.", []),
        "distribution_payer": DimensionValue(_bounded(2 + 1.25 * money_count), "Payer clarity inferred conservatively from economic workflow terms.", []),
        "machine_processability": DimensionValue(machine, "Structured format and stable access path.", [row["machine_format"] or "unknown"]),
        "non_obviousness": DimensionValue(non_obvious, "High existing usage lowers non-obviousness.", [f"usage_count={popularity}"]),
    }


def pra_dimensions_signal(row: sqlite3.Row) -> dict[str, DimensionValue]:
    text = " ".join([row["title"] or "", row["buyer_org"] or "", row["notice_type"] or ""])
    money_count = _term_count(text, MONEY_TERMS)
    join_count = _term_count(text, JOIN_TERMS)
    notice = (row["notice_type"] or "").casefold()
    release = 8 if "사전규격" in notice else 7 if "입찰" in notice else 4
    return {
        "existing_payment_evidence": DimensionValue(_bounded(3 + money_count), "Procurement notice is budget-adjacent evidence, not customer payment proof.", []),
        "cost_substitution": DimensionValue(_bounded(3 + 0.8 * money_count), "Potential substitution remains unverified before schema release.", []),
        "join_amplification": DimensionValue(_bounded(3 + 1.25 * join_count), "Cross-domain terms in the notice title.", []),
        "release_probability": DimensionValue(release, "Procurement stage is stronger than policy intent but weaker than release.", [row["notice_type"] or "unknown"]),
        "lead_time": DimensionValue(8 if "사전규격" in notice else 6, "NIA pre-specification is in the v0.3 T-6~12 month alpha window.", []),
        "data_time": DimensionValue(5 if "데이터" in text else 3, "Time-series behavior is unknown until the schema is published.", []),
        "distribution_payer": DimensionValue(_bounded(3 + money_count), "Buyer remains a hypothesis at the notice stage.", []),
        "machine_processability": DimensionValue(3, "Future delivery format is not yet verified.", []),
        "non_obviousness": DimensionValue(8, "Pre-release procurement notices are less widely productized than released datasets.", []),
    }


def set_override(
    conn: sqlite3.Connection,
    *,
    candidate_type: str,
    candidate_id: str,
    score_kind: str,
    dimension: str,
    rating: float,
    source_type: str,
    source_name: str,
    rationale: str,
) -> None:
    if source_type not in {"HUMAN", "AI"}:
        raise ValueError("source_type must be HUMAN or AI")
    existing = conn.execute(
        """
        SELECT rating, source_type, source_name, rationale FROM score_overrides
        WHERE candidate_type=? AND candidate_id=? AND score_kind=? AND dimension=? AND active=1
        ORDER BY override_id DESC LIMIT 1
        """,
        (candidate_type, candidate_id, score_kind, dimension),
    ).fetchone()
    normalized_rating = _bounded(rating)
    if existing and (
        existing["rating"],
        existing["source_type"],
        existing["source_name"],
        existing["rationale"] or "",
    ) == (normalized_rating, source_type, source_name, rationale or ""):
        return
    conn.execute(
        """
        UPDATE score_overrides SET active=0
        WHERE candidate_type=? AND candidate_id=? AND score_kind=? AND dimension=? AND active=1
        """,
        (candidate_type, candidate_id, score_kind, dimension),
    )
    conn.execute(
        """
        INSERT INTO score_overrides(
            candidate_type, candidate_id, score_kind, dimension, rating,
            source_type, source_name, rationale, created_at, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (candidate_type, candidate_id, score_kind, dimension, normalized_rating, source_type, source_name, rationale, utc_now()),
    )


def _calculate_kind(
    conn: sqlite3.Connection,
    *,
    candidate_type: str,
    candidate_id: str,
    score_kind: str,
    weights: dict[str, int],
    dimensions: dict[str, DimensionValue],
) -> tuple[float, set[str]]:
    calculated_at = utc_now()
    override_types: set[str] = set()
    total = 0.0
    for name, weight in weights.items():
        auto = dimensions[name]
        override = conn.execute(
            """
            SELECT * FROM score_overrides
            WHERE candidate_type=? AND candidate_id=? AND score_kind=? AND dimension=? AND active=1
            ORDER BY override_id DESC LIMIT 1
            """,
            (candidate_type, candidate_id, score_kind, name),
        ).fetchone()
        effective = override["rating"] if override else auto.rating
        points = effective * weight / 10
        total += points
        if override:
            override_types.add(override["source_type"])
        conn.execute(
            """
            INSERT INTO scoring_dimensions(
                candidate_type, candidate_id, score_kind, dimension, weight, auto_rating,
                override_rating, override_source_type, override_source_name, effective_rating,
                effective_points, rationale, evidence_json, calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_type, candidate_id, score_kind, dimension) DO UPDATE SET
                weight=excluded.weight, auto_rating=excluded.auto_rating,
                override_rating=excluded.override_rating,
                override_source_type=excluded.override_source_type,
                override_source_name=excluded.override_source_name,
                effective_rating=excluded.effective_rating,
                effective_points=excluded.effective_points,
                rationale=excluded.rationale, evidence_json=excluded.evidence_json,
                calculated_at=excluded.calculated_at
            """,
            (
                candidate_type,
                candidate_id,
                score_kind,
                name,
                weight,
                auto.rating,
                override["rating"] if override else None,
                override["source_type"] if override else None,
                override["source_name"] if override else None,
                effective,
                points,
                override["rationale"] if override and override["rationale"] else auto.rationale,
                canonical_json(auto.evidence),
                calculated_at,
            ),
        )
    return round(total, 2), override_types


def score_dataset(conn: sqlite3.Connection, dataset_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
    if row is None:
        raise KeyError(dataset_id)
    pra, pra_overrides = _calculate_kind(
        conn,
        candidate_type="DATASET",
        candidate_id=dataset_id,
        score_kind="PRA",
        weights=PRA_WEIGHTS,
        dimensions=pra_dimensions_dataset(row),
    )
    seed, seed_overrides = _calculate_kind(
        conn,
        candidate_type="DATASET",
        candidate_id=dataset_id,
        score_kind="SEED",
        weights=SEED_WEIGHTS,
        dimensions=seed_dimensions(row),
    )
    ephemeral, ephemeral_overrides = _calculate_kind(
        conn,
        candidate_type="DATASET",
        candidate_id=dataset_id,
        score_kind="EPHEMERAL",
        weights=EPHEMERAL_WEIGHTS,
        dimensions=ephemeral_dimensions(row),
    )
    rights_gate = "PASS" if row["rights_status"] == "ALLOW" else "FAIL" if row["rights_status"] == "RESTRICTED" else "REVIEW"
    cost_gate = "PASS" if row["cost_status"] in {"FREE", "NEAR_ZERO"} else "FAIL" if row["cost_status"] == "PAID" else "REVIEW"
    if seed >= 75 and rights_gate == "PASS" and cost_gate == "PASS":
        accumulation_gate = "PASS"
        recommendation = "COLLECT_NOW"
    elif rights_gate == "FAIL":
        accumulation_gate = "FAIL"
        recommendation = "METADATA_ONLY"
    elif seed >= 75 and (rights_gate == "REVIEW" or cost_gate == "REVIEW"):
        accumulation_gate = "REVIEW"
        recommendation = "REVIEW_RIGHTS_COST"
    else:
        accumulation_gate = "FAIL"
        recommendation = "HOLD"
    override_types = pra_overrides | seed_overrides | ephemeral_overrides
    review_status = "AUTO" if not override_types else "MIXED_OVERRIDE" if len(override_types) > 1 else f"{next(iter(override_types))}_OVERRIDE"
    conn.execute(
        """
        INSERT INTO alpha_scores(
            candidate_type, candidate_id, pra_score, seed_score, ephemeral_score,
            rights_gate, cost_gate, accumulation_gate, review_status, recommendation,
            calculation_version, calculated_at
        ) VALUES ('DATASET', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_type, candidate_id) DO UPDATE SET
            pra_score=excluded.pra_score, seed_score=excluded.seed_score,
            ephemeral_score=excluded.ephemeral_score, rights_gate=excluded.rights_gate,
            cost_gate=excluded.cost_gate, accumulation_gate=excluded.accumulation_gate,
            review_status=excluded.review_status, recommendation=excluded.recommendation,
            calculation_version=excluded.calculation_version, calculated_at=excluded.calculated_at
        """,
        (dataset_id, pra, seed, ephemeral, rights_gate, cost_gate, accumulation_gate, review_status, recommendation, CALCULATION_VERSION, utc_now()),
    )
    collector = conn.execute("SELECT collector_id FROM collector_registry WHERE dataset_id=?", (dataset_id,)).fetchone()
    reason = (
        f"seed={seed:.1f}; rights={rights_gate}; cost={cost_gate}; "
        "v0.3 threshold requires seed>=75 and both gates PASS"
    )
    now = utc_now()
    conn.execute(
        """
        INSERT INTO seed_queue(
            candidate_type, candidate_id, dataset_id, seed_score, decision, reason,
            rights_ok, low_cost, collector_id, created_at, updated_at
        ) VALUES ('DATASET', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_type, candidate_id) DO UPDATE SET
            dataset_id=excluded.dataset_id, seed_score=excluded.seed_score,
            decision=excluded.decision, reason=excluded.reason, rights_ok=excluded.rights_ok,
            low_cost=excluded.low_cost, collector_id=excluded.collector_id,
            updated_at=excluded.updated_at
        """,
        (
            dataset_id,
            dataset_id,
            seed,
            recommendation,
            reason,
            int(rights_gate == "PASS"),
            int(cost_gate == "PASS"),
            collector["collector_id"] if collector else None,
            now,
            now,
        ),
    )
    return {"pra": pra, "seed": seed, "ephemeral": ephemeral, "recommendation": recommendation}


def score_signal(conn: sqlite3.Connection, signal_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM pre_release_signals WHERE signal_id=?", (signal_id,)).fetchone()
    if row is None:
        raise KeyError(signal_id)
    pra, override_types = _calculate_kind(
        conn,
        candidate_type="SIGNAL",
        candidate_id=signal_id,
        score_kind="PRA",
        weights=PRA_WEIGHTS,
        dimensions=pra_dimensions_signal(row),
    )
    recommendation = "DEEP_REVIEW" if pra >= 70 else "MONITOR" if pra >= 45 else "HOLD"
    review_status = "AUTO" if not override_types else f"{next(iter(override_types))}_OVERRIDE"
    conn.execute(
        """
        INSERT INTO alpha_scores(
            candidate_type, candidate_id, pra_score, seed_score, ephemeral_score,
            rights_gate, cost_gate, accumulation_gate, review_status, recommendation,
            calculation_version, calculated_at
        ) VALUES ('SIGNAL', ?, ?, NULL, NULL, 'REVIEW', 'REVIEW', 'NOT_APPLICABLE', ?, ?, ?, ?)
        ON CONFLICT(candidate_type, candidate_id) DO UPDATE SET
            pra_score=excluded.pra_score, review_status=excluded.review_status,
            recommendation=excluded.recommendation, calculation_version=excluded.calculation_version,
            calculated_at=excluded.calculated_at
        """,
        (signal_id, pra, review_status, recommendation, CALCULATION_VERSION, utc_now()),
    )
    return {"pra": pra, "recommendation": recommendation}


def score_all(conn: sqlite3.Connection) -> dict[str, int]:
    dataset_ids = [row[0] for row in conn.execute("SELECT dataset_id FROM datasets")]
    signal_ids = [row[0] for row in conn.execute("SELECT signal_id FROM pre_release_signals")]
    for dataset_id in dataset_ids:
        score_dataset(conn, dataset_id)
    for signal_id in signal_ids:
        score_signal(conn, signal_id)
    return {"datasets": len(dataset_ids), "signals": len(signal_ids)}
