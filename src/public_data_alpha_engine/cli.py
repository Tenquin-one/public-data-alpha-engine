from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .bootstrap import bootstrap
from .collectors.seoul_city import SeoulCityCollector, detect_gaps
from .cloud_archive import collect_cloud_archive
from .db import DEFAULT_DB, PROJECT_ROOT, connect, init_db, integrity
from .exports import DEFAULT_EXPORT_ROOT, export_initial_results
from .prerelease import fetch_nia_signals, link_signals_to_datasets, upsert_signals
from .registry import finish_run, mirror_records, reconcile_planned_to_open, start_run
from .scoring import score_all
from .sources import fetch_csv_registry, fetch_odcloud_catalog
from .utils import load_local_env


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _database(value: str | None) -> Path:
    return Path(value) if value else DEFAULT_DB


def command_init(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        init_db(conn)
    _json({"status": "initialized", "db": str(_database(args.db))})


def command_bootstrap(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        result = bootstrap(conn)
    _json({"status": "bootstrapped", "db": str(_database(args.db)), **result})


def command_mirror_odcloud(args: argparse.Namespace) -> None:
    key = "data-portal-test-key" if args.test_key else os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required, or pass --test-key for the official 10-row sample")
    with connect(_database(args.db)) as conn:
        init_db(conn)
        run_id = start_run(conn, "data_go_registry")
        try:
            batch = fetch_odcloud_catalog(
                service_key=key,
                endpoint=args.endpoint,
                page=args.page,
                per_page=10 if args.test_key else args.per_page,
            )
            counts = mirror_records(
                conn,
                source_id="data_go_registry",
                records=batch.records,
                source_url=batch.source_url,
                query_params=batch.query_params,
                raw_payload=batch.raw_payload,
                run_id=run_id,
            )
            linked = reconcile_planned_to_open(conn)
            finish_run(
                conn,
                run_id,
                status="SUCCESS",
                requested=len(batch.records),
                received=len(batch.records),
                inserted=counts["new"],
                duplicates=counts["unchanged"],
            )
            score_all(conn)
            conn.commit()
        except Exception as exc:
            finish_run(conn, run_id, status="FAILED", errors=1, error_message=str(exc))
            conn.commit()
            raise
    _json({"status": "success", "run_id": run_id, "release_links": linked, **counts})


def command_mirror_csv(args: argparse.Namespace) -> None:
    source_id = "data_go_planned" if args.planned else "data_go_registry"
    default_status = "PLANNED" if args.planned else "OPEN"
    with connect(_database(args.db)) as conn:
        init_db(conn)
        run_id = start_run(conn, source_id)
        try:
            batch = fetch_csv_registry(source=args.source, default_status=default_status)
            counts = mirror_records(
                conn,
                source_id=source_id,
                records=batch.records,
                source_url=batch.source_url,
                raw_payload=batch.raw_payload,
                run_id=run_id,
            )
            linked = reconcile_planned_to_open(conn)
            finish_run(
                conn,
                run_id,
                status="SUCCESS",
                requested=len(batch.records),
                received=len(batch.records),
                inserted=counts["new"],
                duplicates=counts["unchanged"],
            )
            score_all(conn)
            conn.commit()
        except Exception as exc:
            finish_run(conn, run_id, status="FAILED", errors=1, error_message=str(exc))
            conn.commit()
            raise
    _json({"status": "success", "run_id": run_id, "release_links": linked, **counts})


def command_watch_nia(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        init_db(conn)
        run_id = start_run(conn, "nia_procurement")
        try:
            signals, raw = fetch_nia_signals(data_only=not args.all_notices)
            counts = upsert_signals(
                conn,
                source_id="nia_procurement",
                signals=signals,
                raw_payload=raw,
                run_id=run_id,
            )
            links = link_signals_to_datasets(conn)
            finish_run(
                conn,
                run_id,
                status="SUCCESS",
                requested=len(signals),
                received=len(signals),
                inserted=counts["new"],
                duplicates=counts["unchanged"],
            )
            score_all(conn)
            conn.commit()
        except Exception as exc:
            finish_run(conn, run_id, status="FAILED", errors=1, error_message=str(exc))
            conn.commit()
            raise
    _json({"status": "success", "run_id": run_id, "links": links, **counts})


def command_score(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        result = score_all(conn)
        conn.commit()
    _json({"status": "scored", **result})


def command_collect_seoul(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        collector = SeoulCityCollector(conn, api_key="sample" if args.sample else None)
        results = collector.collect(sample_only=args.sample)
    _json([result.__dict__ for result in results])


def command_collect_cloud(args: argparse.Namespace) -> None:
    api_key = os.getenv("SEOUL_OPEN_DATA_KEY") or "sample"
    result = collect_cloud_archive(Path(args.output), api_key=api_key)
    _json(result)
    if result["status"] == "FAILED":
        raise RuntimeError("all Seoul cloud archive requests failed")


def command_health(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        gaps = detect_gaps(conn)
        conn.commit()
        latest = conn.execute(
            "SELECT * FROM collector_health_logs ORDER BY health_id DESC LIMIT 1"
        ).fetchone()
    _json({"new_gap_events": gaps, "latest_health": dict(latest) if latest else None})


def command_status(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        result = {
            "datasets": conn.execute("SELECT count(*) FROM datasets").fetchone()[0],
            "dataset_events": conn.execute("SELECT count(*) FROM dataset_events").fetchone()[0],
            "pre_release_signals": conn.execute("SELECT count(*) FROM pre_release_signals").fetchone()[0],
            "signal_links": conn.execute("SELECT count(*) FROM signal_dataset_links").fetchone()[0],
            "snapshots": conn.execute("SELECT count(*) FROM snapshots").fetchone()[0],
            "raw_payloads": conn.execute("SELECT count(*) FROM raw_payloads").fetchone()[0],
            "seed_queue": [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT d.title, q.seed_score, q.decision, q.reason, q.collector_id
                    FROM seed_queue q JOIN datasets d ON d.dataset_id=q.dataset_id
                    ORDER BY q.seed_score DESC
                    """
                )
            ],
            "pre_release_rank": [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT p.title, a.pra_score, a.recommendation
                    FROM alpha_scores a JOIN pre_release_signals p ON p.signal_id=a.candidate_id
                    WHERE a.candidate_type='SIGNAL' ORDER BY a.pra_score DESC
                    """
                )
            ],
        }
    _json(result)


def command_check(args: argparse.Namespace) -> None:
    with connect(_database(args.db)) as conn:
        check, fk_count = integrity(conn)
    _json({"integrity_check": check, "foreign_key_errors": fk_count})


def command_export(args: argparse.Namespace) -> None:
    output_root = Path(args.output) if args.output else DEFAULT_EXPORT_ROOT
    with connect(_database(args.db)) as conn:
        result = export_initial_results(conn, output_root)
    _json({"status": "exported", "output": str(output_root), **result})


def command_live_smoke(args: argparse.Namespace) -> None:
    """One bounded network check covering all three first-version live sources."""
    summary: dict[str, Any] = {"odcloud": {}, "nia": {}, "seoul_sample": []}
    with connect(_database(args.db)) as conn:
        bootstrap(conn)

        registry_run = start_run(conn, "data_go_registry")
        try:
            batch = fetch_odcloud_catalog(
                service_key="data-portal-test-key",
                endpoint="dataset",
                page=1,
                per_page=10,
            )
            counts = mirror_records(
                conn,
                source_id="data_go_registry",
                records=batch.records,
                source_url=batch.source_url,
                query_params=batch.query_params,
                raw_payload=batch.raw_payload,
                run_id=registry_run,
            )
            finish_run(
                conn,
                registry_run,
                status="SUCCESS",
                requested=10,
                received=len(batch.records),
                inserted=counts["new"],
                duplicates=counts["unchanged"],
            )
            summary["odcloud"] = {"status": "SUCCESS", **counts}
        except Exception as exc:
            finish_run(conn, registry_run, status="FAILED", errors=1, error_message=str(exc))
            summary["odcloud"] = {"status": "FAILED", "error": str(exc)}

        nia_run = start_run(conn, "nia_procurement")
        try:
            signals, raw = fetch_nia_signals(data_only=True)
            counts = upsert_signals(
                conn,
                source_id="nia_procurement",
                signals=signals,
                raw_payload=raw,
                run_id=nia_run,
            )
            finish_run(
                conn,
                nia_run,
                status="SUCCESS",
                requested=len(signals),
                received=len(signals),
                inserted=counts["new"],
                duplicates=counts["unchanged"],
            )
            summary["nia"] = {"status": "SUCCESS", "received": len(signals), **counts}
        except Exception as exc:
            finish_run(conn, nia_run, status="FAILED", errors=1, error_message=str(exc))
            summary["nia"] = {"status": "FAILED", "error": str(exc)}

        try:
            collector = SeoulCityCollector(conn, api_key="sample")
            summary["seoul_sample"] = [result.__dict__ for result in collector.collect(sample_only=True)]
        except Exception as exc:
            summary["seoul_sample"] = [{"status": "FAILED", "error": str(exc)}]

        reconcile_planned_to_open(conn)
        link_signals_to_datasets(conn)
        score_all(conn)
        conn.commit()
    _json(summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Opportunity Foundry Public Data Alpha Engine")
    parser.add_argument("--db", help=f"SQLite path (default: {DEFAULT_DB})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init").set_defaults(func=command_init)
    sub.add_parser("bootstrap").set_defaults(func=command_bootstrap)

    odcloud = sub.add_parser("mirror-odcloud")
    odcloud.add_argument("--test-key", action="store_true", help="Use official 10-row test key")
    odcloud.add_argument("--endpoint", default="dataset", choices=["dataset", "file-data-list", "open-data-list", "standard-data-list"])
    odcloud.add_argument("--page", type=int, default=1)
    odcloud.add_argument("--per-page", type=int, default=1000)
    odcloud.set_defaults(func=command_mirror_odcloud)

    csv_parser = sub.add_parser("mirror-csv")
    csv_parser.add_argument("source", help="Local CSV path or direct CSV URL")
    csv_parser.add_argument("--planned", action="store_true")
    csv_parser.set_defaults(func=command_mirror_csv)

    nia = sub.add_parser("watch-nia")
    nia.add_argument("--all-notices", action="store_true", help="Keep non-data notices too")
    nia.set_defaults(func=command_watch_nia)

    sub.add_parser("score").set_defaults(func=command_score)
    seoul = sub.add_parser("collect-seoul")
    seoul.add_argument("--sample", action="store_true", help="Use official sample key for 광화문·덕수궁")
    seoul.set_defaults(func=command_collect_seoul)
    cloud = sub.add_parser("collect-cloud")
    cloud.add_argument("--output", required=True, help="Data-branch checkout directory")
    cloud.set_defaults(func=command_collect_cloud)
    sub.add_parser("health").set_defaults(func=command_health)
    sub.add_parser("status").set_defaults(func=command_status)
    sub.add_parser("check").set_defaults(func=command_check)
    export = sub.add_parser("export")
    export.add_argument("--output", help=f"Output directory (default: {DEFAULT_EXPORT_ROOT})")
    export.set_defaults(func=command_export)
    sub.add_parser("live-smoke").set_defaults(func=command_live_smoke)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Local convenience only. Existing shell/Actions variables always take precedence.
    load_local_env(PROJECT_ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
