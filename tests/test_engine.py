from __future__ import annotations

import json
import os
import sqlite3
import tarfile
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from public_data_alpha_engine.bootstrap import bootstrap
from public_data_alpha_engine.collectors.seoul_city import (
    COLLECTOR_ID,
    SeoulCityCollector,
    _source_timestamp,
    detect_gaps,
    parse_payload,
)
from public_data_alpha_engine.db import connect, init_db, integrity, upsert_source
from public_data_alpha_engine.cloud_archive import collect_cloud_archive
from public_data_alpha_engine.exports import export_initial_results
from public_data_alpha_engine.http_client import HttpClient, HttpResponse
from public_data_alpha_engine.prerelease import link_signals_to_datasets, parse_nia_html, upsert_signals
from public_data_alpha_engine.registry import (
    DatasetRecord,
    mirror_records,
    normalize_record,
    reconcile_planned_to_open,
)
from public_data_alpha_engine.scoring import score_dataset, set_override
from public_data_alpha_engine.utils import load_local_env


FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def request(self, url: str, **_: object) -> HttpResponse:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


class EngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp.name)
        self.db_path = self.temp_path / "test.sqlite"
        self.project_patch = patch("public_data_alpha_engine.storage.PROJECT_ROOT", self.temp_path)
        self.project_patch.start()

    def tearDown(self) -> None:
        self.project_patch.stop()
        self.temp.cleanup()

    def connection(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_db(conn)
        return conn

    def test_local_env_loads_known_keys_without_overriding_shell(self) -> None:
        env_path = self.temp_path / ".env"
        env_path.write_text(
            'SEOUL_OPEN_DATA_KEY="file-key"\nUNKNOWN_KEY=ignored\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_local_env(env_path), {"SEOUL_OPEN_DATA_KEY"})
            self.assertEqual(os.environ["SEOUL_OPEN_DATA_KEY"], "file-key")
            self.assertNotIn("UNKNOWN_KEY", os.environ)
        with patch.dict(os.environ, {"SEOUL_OPEN_DATA_KEY": "shell-key"}, clear=True):
            self.assertEqual(load_local_env(env_path), set())
            self.assertEqual(os.environ["SEOUL_OPEN_DATA_KEY"], "shell-key")

    def test_bootstrap_is_idempotent_and_integral(self) -> None:
        with self.connection() as conn:
            first = bootstrap(conn)
            second = bootstrap(conn)
            self.assertEqual(first["datasets"], 6)
            self.assertEqual(second["datasets"], 6)
            self.assertEqual(conn.execute("SELECT count(*) FROM datasets").fetchone()[0], 6)
            self.assertEqual(conn.execute("SELECT count(*) FROM score_overrides WHERE active=1").fetchone()[0], 10)
            self.assertEqual(integrity(conn), ("ok", 0))

    def test_diff_engine_emits_only_changed_fields(self) -> None:
        with self.connection() as conn:
            upsert_source(
                conn,
                source_id="test",
                name="test",
                source_type="REGISTRY",
                base_url="https://example.test",
                cadence_seconds=86400,
                rights_status="ALLOW",
                terms_memo="test",
            )
            first = DatasetRecord(
                external_id="1",
                title="테스트 데이터",
                source_url="https://example.test/1",
                provider="기관A",
                public_status="OPEN",
                file_available=True,
                update_frequency="월간",
                license="제한 없음",
            )
            mirror_records(conn, source_id="test", records=[first], source_url="https://example.test")
            changed = DatasetRecord(**{**first.__dict__, "api_available": True, "update_frequency": "일간"})
            counts = mirror_records(conn, source_id="test", records=[changed], source_url="https://example.test")
            event_types = {row[0] for row in conn.execute("SELECT event_type FROM dataset_events")}
            self.assertEqual(counts["updated"], 1)
            self.assertIn("API_ADDED", event_types)
            self.assertIn("UPDATE_FREQUENCY_CHANGED", event_types)
            self.assertEqual(counts["events"], 2)

    def test_expected_to_open_reconciliation(self) -> None:
        with self.connection() as conn:
            for source_id in ("planned", "open"):
                upsert_source(
                    conn,
                    source_id=source_id,
                    name=source_id,
                    source_type="REGISTRY",
                    base_url="https://example.test",
                    cadence_seconds=86400,
                    rights_status="ALLOW",
                    terms_memo="test",
                )
            planned = normalize_record(
                {"목록명": "서울특별시 실시간 상권 소비 데이터", "기관명": "서울특별시", "개방예정년도": "2026"},
                default_status="PLANNED",
            )
            opened = normalize_record(
                {"목록명": "서울특별시 실시간 상권 소비 데이터", "기관명": "서울특별시", "데이터유형": "API"},
                default_status="OPEN",
            )
            mirror_records(conn, source_id="planned", records=[planned], source_url="https://example.test/planned")
            mirror_records(conn, source_id="open", records=[opened], source_url="https://example.test/open")
            self.assertEqual(reconcile_planned_to_open(conn), 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM dataset_events WHERE event_type='EXPECTED_TO_OPEN'").fetchone()[0], 1)

    def test_human_override_is_separate_from_auto_rating(self) -> None:
        with self.connection() as conn:
            bootstrap(conn)
            dataset_id = "seoul-open-data:oa-21285"
            score_dataset(conn, dataset_id)
            row = conn.execute(
                """
                SELECT auto_rating, override_rating, effective_rating, override_source_type
                FROM scoring_dimensions
                WHERE candidate_type='DATASET' AND candidate_id=? AND score_kind='SEED'
                  AND dimension='direct_money_link'
                """,
                (dataset_id,),
            ).fetchone()
            self.assertNotEqual(row["auto_rating"], row["override_rating"])
            self.assertEqual(row["effective_rating"], 9)
            self.assertEqual(row["override_source_type"], "HUMAN")

    def test_rights_gate_blocks_collection_even_with_high_score(self) -> None:
        with self.connection() as conn:
            bootstrap(conn)
            dataset_id = "data-go-registry:15077093"
            conn.execute("UPDATE datasets SET rights_status='RESTRICTED' WHERE dataset_id=?", (dataset_id,))
            for dimension in (
                "past_reconstruction_impossibility",
                "direct_money_link",
                "multi_source_join_value",
                "automated_collection",
                "update_frequency",
                "ground_truth_possible",
                "storage_operations_cost",
            ):
                set_override(
                    conn,
                    candidate_type="DATASET",
                    candidate_id=dataset_id,
                    score_kind="SEED",
                    dimension=dimension,
                    rating=10,
                    source_type="HUMAN",
                    source_name="test",
                    rationale="test",
                )
            result = score_dataset(conn, dataset_id)
            self.assertEqual(result["seed"], 100)
            self.assertEqual(result["recommendation"], "METADATA_ONLY")

    def test_nia_parser_filters_and_links(self) -> None:
        html = (FIXTURES / "nia_list.html").read_text(encoding="utf-8")
        signals = parse_nia_html(html, data_only=True)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].external_id, "30001")
        self.assertEqual(signals[0].posted_at, "2026-08-24")
        with self.connection() as conn:
            bootstrap(conn)
            upsert_signals(conn, source_id="nia_procurement", signals=signals)
            self.assertGreaterEqual(link_signals_to_datasets(conn), 1)

    def test_parse_json_and_xml_payloads(self) -> None:
        raw = (FIXTURES / "seoul_city_sample.json").read_bytes()
        parsed, mime = parse_payload(raw)
        self.assertEqual(mime, "application/json")
        self.assertEqual(parsed["CITYDATA"][0]["AREA_NM"], "광화문·덕수궁")
        xml = b"<SeoulRtd.citydata><CITYDATA><AREA_NM>sample</AREA_NM><LIVE_PPLTN_STTS><PPLTN_TIME>2026-08-26 12:15</PPLTN_TIME></LIVE_PPLTN_STTS></CITYDATA></SeoulRtd.citydata>"
        parsed_xml, mime_xml = parse_payload(xml)
        self.assertEqual(mime_xml, "application/xml")
        self.assertIn("SeoulRtd.citydata", parsed_xml)

    def test_collector_deduplicates_consecutive_payload(self) -> None:
        raw = (FIXTURES / "seoul_city_sample.json").read_bytes()
        response = HttpResponse(raw, 200, "application/json", 12, 0)
        with self.connection() as conn:
            bootstrap(conn)
            collector = SeoulCityCollector(conn, api_key="sample", client=FakeClient([response]))
            first = collector.collect_area("광화문·덕수궁")
            second = collector.collect_area("광화문·덕수궁")
            self.assertFalse(first.duplicate)
            self.assertTrue(second.duplicate)
            self.assertEqual(first.byte_count, second.byte_count)
            self.assertEqual(conn.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM raw_payloads WHERE is_duplicate=1").fetchone()[0], 1)

    def test_duplicate_observation_counts_as_fresh_for_gap_detection(self) -> None:
        raw = (FIXTURES / "seoul_city_sample.json").read_bytes()
        response = HttpResponse(raw, 200, "application/json", 12, 0)
        with self.connection() as conn:
            bootstrap(conn)
            collector = SeoulCityCollector(conn, api_key="sample", client=FakeClient([response]))
            collector.collect_area("광화문·덕수궁")
            collector.collect_area("광화문·덕수궁")
            inserted = detect_gaps(conn, now=datetime.now(UTC) + timedelta(minutes=20))
            self.assertEqual(inserted, 7)
            self.assertIsNone(
                conn.execute(
                    "SELECT gap_id FROM data_gap_events WHERE entity_key='광화문·덕수궁'"
                ).fetchone()
            )

    def test_collector_falls_back_to_xml(self) -> None:
        xml = b"<SeoulRtd.citydata><CITYDATA><AREA_NM>sample</AREA_NM><RESULT><CODE>INFO-000</CODE></RESULT></CITYDATA></SeoulRtd.citydata>"
        fake = FakeClient([ValueError("bad json"), HttpResponse(xml, 200, "application/xml", 20, 1)])
        with self.connection() as conn:
            bootstrap(conn)
            collector = SeoulCityCollector(conn, api_key="sample", client=fake)
            result = collector.collect_area("광화문·덕수궁")
            self.assertEqual(fake.calls, 2)
            self.assertEqual(result.status, "PARTIAL")

    def test_gap_detection_records_missing_cohort(self) -> None:
        with self.connection() as conn:
            bootstrap(conn)
            now = datetime.now(UTC) + timedelta(hours=1)
            inserted = detect_gaps(conn, now=now)
            self.assertEqual(inserted, 8)
            self.assertEqual(conn.execute("SELECT count(*) FROM data_gap_events").fetchone()[0], 8)
            self.assertEqual(detect_gaps(conn, now=now + timedelta(minutes=5)), 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM data_gap_events").fetchone()[0], 8)

    def test_http_client_retries_transient_failure(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"{}"
        response.status = 200
        response.headers.get_content_type.return_value = "application/json"
        with (
            patch(
                "public_data_alpha_engine.http_client.urllib.request.urlopen",
                side_effect=[urllib.error.URLError("temporary"), response],
            ) as urlopen,
            patch("public_data_alpha_engine.http_client.time.sleep"),
        ):
            result = HttpClient(timeout=1, max_retries=2).request("https://example.test")
        self.assertEqual(result.status, 200)
        self.assertEqual(result.retries, 1)
        self.assertEqual(urlopen.call_count, 2)

    def test_source_timestamp_ignores_forecast_values(self) -> None:
        payload = {
            "PPLTN_TIME": "2026-08-26 08:20:00",
            "FCST_PPLTN_TIME": "2026-08-26 20:00:00",
            "WEATHER_TIME": "2026-08-26 08:15:00",
        }
        self.assertEqual(_source_timestamp(payload), "2026-08-26T08:20:00+09:00")

    def test_exports_reproduce_initial_results(self) -> None:
        with self.connection() as conn:
            bootstrap(conn)
            output = self.temp_path / "exports"
            manifest = export_initial_results(conn, output)
            self.assertEqual(manifest["files"]["initial_scores.csv"], 6)
            self.assertEqual(manifest["files"]["seed_queue.csv"], 6)
            self.assertEqual(manifest["files"]["pre_release_signals.csv"], 4)
            self.assertEqual(manifest["files"]["seoul_seed_places.csv"], 8)
            self.assertTrue((output / "manifest.json").exists())

    def test_cloud_archive_is_reconstructable_and_deduplicated(self) -> None:
        raw = (FIXTURES / "seoul_city_sample.json").read_bytes()
        response = HttpResponse(raw, 200, "application/json", 12, 0)
        output = self.temp_path / "cloud-data"
        first = collect_cloud_archive(
            output,
            api_key="sample",
            client=FakeClient([response]),
            now=datetime(2026, 8, 26, 0, 0, tzinfo=UTC),
        )
        self.assertEqual(first["status"], "SUCCESS")
        self.assertEqual(first["mode"], "SAMPLE")
        self.assertEqual(first["areas_requested"], 1)
        self.assertEqual(first["new_payloads"], 1)
        bundle = Path(first["bundle_path"])
        self.assertTrue(bundle.exists())
        with tarfile.open(bundle) as archive:
            names = archive.getnames()
            self.assertIn("manifest.json", names)
            self.assertEqual(sum(name.startswith("payloads/") for name in names), 1)
        state_text = (output / "state" / "latest_hashes.json").read_text(encoding="utf-8")
        self.assertNotIn("sample/json", state_text)
        self.assertNotIn("SEOUL_OPEN_DATA_KEY", state_text)

        second = collect_cloud_archive(
            output,
            api_key="sample",
            client=FakeClient([response]),
            now=datetime(2026, 8, 26, 0, 15, tzinfo=UTC),
        )
        self.assertEqual(second["new_payloads"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(second["health_status"], "OK")
        self.assertEqual(second["missed_intervals"], 0)
        self.assertIsNone(second["bundle_path"])
        self.assertTrue(Path(second["run_path"]).exists())

        delayed = collect_cloud_archive(
            output,
            api_key="sample",
            client=FakeClient([response]),
            now=datetime(2026, 8, 26, 1, 15, tzinfo=UTC),
        )
        self.assertEqual(delayed["health_status"], "WARNING")
        self.assertEqual(delayed["missed_intervals"], 3)
        delayed_manifest = json.loads(Path(delayed["run_path"]).read_text(encoding="utf-8"))
        self.assertEqual(delayed_manifest["health"]["schedule"]["late_by_seconds"], 2700)


if __name__ == "__main__":
    unittest.main()
