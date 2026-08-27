from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from public_data_alpha_engine.airport_friction import (
    AIRPORT_BY_ICAO,
    AirportFrictionCollector,
    FIXTURE_PATH,
    quota_budget,
)
from public_data_alpha_engine.collectors.factory import create_collector
from public_data_alpha_engine.http_client import HttpResponse
from public_data_alpha_engine.utils import canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FixtureRoutingClient:
    def __init__(self, *, fail_fragment: str | None = None) -> None:
        self.responses = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["responses"]
        self.fail_fragment = fail_fragment
        self.urls: list[str] = []

    def request(self, url: str, **_: object) -> HttpResponse:
        self.urls.append(url)
        if self.fail_fragment and self.fail_fragment in url:
            raise ConnectionError(f"failed request {url}")
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if "airport-process-time" in parsed.path:
            source_id = f"kac_process_time_{parsed.path.rsplit('/', 1)[-1]}"
        elif "airport-congestion" in parsed.path:
            source_id = f"kac_congestion_{parsed.path.rsplit('/', 1)[-1]}"
        elif "parking-realtime-status" in parsed.path:
            source_id = "kac_parking"
        elif "parking-congestion" in parsed.path:
            source_id = "kac_parking_congestion"
        elif "flight-status" in parsed.path:
            source_id = f"kac_flight_{query['airport_code'][0]}"
        elif "flight-schedule" in parsed.path:
            source_id = f"kac_flight_schedule_{query['schDeptCityCode'][0]}"
        elif parsed.path.endswith("/getMetar"):
            source_id = f"kma_metar_{AIRPORT_BY_ICAO[query['icao'][0]].iata}"
        elif parsed.path.endswith("/getWarning"):
            source_id = "kma_airport_warning"
        else:
            raise AssertionError(f"unexpected URL: {url}")
        body = (canonical_json(self.responses[source_id]) + "\n").encode("utf-8")
        return HttpResponse(body, 200, "application/json", 7, 1)


class AirportFrictionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.now = datetime(2026, 8, 27, 1, 0, tzinfo=UTC)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fixture_collect(self, **kwargs: object) -> dict[str, object]:
        return AirportFrictionCollector().collect(
            self.output,
            mode="fixture",
            now=kwargs.pop("now", self.now),
            force_weather=kwargs.pop("force_weather", True),
            **kwargs,
        )

    def manifest(self, result: dict[str, object]) -> dict[str, object]:
        return json.loads(Path(str(result["run_path"])).read_text(encoding="utf-8"))

    def test_schema_and_normalization(self) -> None:
        manifest = self.manifest(self.fixture_collect())
        by_airport = {row["airport"]["iata"]: row for row in manifest["normalized_records"]}
        gimpo = by_airport["GMP"]
        self.assertEqual(gimpo["friction"]["checkin"]["to_identity_seconds"], 240)
        self.assertEqual(gimpo["friction"]["identity"]["to_security_level"], 3)
        self.assertEqual(gimpo["friction"]["boarding"]["to_departure_seconds"], 90)
        self.assertIsNone(gimpo["friction"]["boarding"]["to_departure_level"])
        self.assertEqual(gimpo["friction"]["provider_stage_d_mapping"], "boarding_to_aircraft_departure")
        self.assertEqual(gimpo["departures_30m"], 2)
        self.assertEqual(gimpo["delayed_departures_30m"], 1)
        self.assertEqual(gimpo["cancelled_departures_30m"], 1)
        self.assertEqual(gimpo["timetable_departures_30m"], 2)
        self.assertEqual(gimpo["timetable_minus_live_departures_30m"], 0)
        self.assertEqual(gimpo["parking"]["available"], 200)
        self.assertEqual(gimpo["parking"]["provider_congestion"]["facilities"][0]["provider_level"], "혼잡")
        self.assertEqual(gimpo["parking"]["provider_congestion"]["facilities"][0]["provider_degree_percent"], 80.0)
        self.assertNotIn("gimpo_indoor_cells", gimpo["parking"])
        self.assertEqual(gimpo["weather"]["temperature_c"], 28.0)
        self.assertEqual(by_airport["CJU"]["weather_warnings"][0]["type"], "강풍")
        self.assertEqual(gimpo["calendar"]["weekday_iso"], 4)

    def test_dedupe_uses_namespaced_latest_hashes(self) -> None:
        first = self.fixture_collect()
        second = self.fixture_collect(now=self.now + timedelta(minutes=15))
        self.assertEqual(first["new_payloads"], 22)
        self.assertEqual(second["new_payloads"], 0)
        self.assertEqual(second["duplicates"], 22)
        self.assertIsNone(second["bundle_path"])
        state = self.output / "state" / "airport_friction" / "latest_hashes.json"
        self.assertTrue(state.exists())
        self.assertFalse((self.output / "state" / "latest_hashes.json").exists())

    def test_redaction_covers_urls_query_and_errors(self) -> None:
        data_secret = "data+/secret=="
        kma_secret = "kma%2Bsecret"
        client = FixtureRoutingClient(fail_fragment="parking-realtime-status")
        result = AirportFrictionCollector(
            data_go_key=data_secret,
            kma_key=kma_secret,
            client=client,
        ).collect(self.output, mode="live", now=self.now, force_weather=True)
        text = Path(str(result["run_path"])).read_text(encoding="utf-8")
        self.assertNotIn(data_secret, text)
        self.assertNotIn(kma_secret, text)
        self.assertIn("REDACTED", text)
        observations = json.loads(text)["source_observations"]
        for observation in observations:
            serialized = canonical_json(
                {"source_url": observation["source_url"], "query_params": observation["query_params"]}
            )
            self.assertNotIn(data_secret, serialized)
            self.assertNotIn(kma_secret, serialized)
            self.assertEqual(observation["query_params"].get("serviceKey", observation["query_params"].get("authKey")), "REDACTED")

    def test_quota_calculation_fits_every_official_limit(self) -> None:
        budget = quota_budget()
        self.assertEqual(budget["totals"]["all_requests_per_day"], 1824)
        self.assertEqual(budget["totals"]["requests_90_days"], 164160)
        self.assertEqual(budget["temporary_dual_scheduler_overlap"]["all_requests_per_day"], 3360)
        self.assertEqual(budget["temporary_dual_scheduler_overlap"]["kac_shared_pool_utilization_pct"], 61.44)
        self.assertTrue(budget["temporary_dual_scheduler_overlap"]["all_services_within_published_limits"])
        for service in budget["services"].values():
            self.assertLess(service["requests_per_day"], service["quota"])

    def test_partial_api_failure_keeps_other_sources_and_manifest(self) -> None:
        client = FixtureRoutingClient(fail_fragment="parking-realtime-status")
        result = AirportFrictionCollector(
            data_go_key="data-key",
            kma_key="kma-key",
            client=client,
        ).collect(self.output, mode="live", now=self.now, force_weather=True)
        self.assertEqual(result["status"], "PARTIAL")
        manifest = self.manifest(result)
        self.assertEqual(manifest["summary"]["errors"], 1)
        self.assertEqual(len(manifest["health"]["source_gaps"]), 1)
        for row in manifest["normalized_records"]:
            self.assertIn("parking", row["missing_sections"])
            self.assertEqual(row["source_status"]["parking"], "ERROR")

    def test_schema_drift_marks_run_partial(self) -> None:
        client = FixtureRoutingClient()
        client.responses["kac_process_time_v2"]["response"]["body"]["items"]["item"][0].pop(
            "STY_TCT_AVG_ALL"
        )
        result = AirportFrictionCollector(
            data_go_key="data-key",
            kma_key="kma-key",
            client=client,
        ).collect(self.output, mode="live", now=self.now, force_weather=True)
        manifest = self.manifest(result)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(manifest["summary"]["sources_partial"], 1)
        observation = next(
            value for value in manifest["source_observations"] if value["source_id"] == "kac_process_time_v2"
        )
        self.assertEqual(observation["status"], "PARTIAL")
        self.assertIn("STY_TCT_AVG_ALL", observation["missing_sections"])
        pus = next(value for value in manifest["normalized_records"] if value["airport"]["iata"] == "PUS")
        self.assertEqual(pus["source_status"]["process_time"], "PARTIAL")
        self.assertEqual(pus["quality_status"], "PARTIAL")
        self.assertIn("process_time", pus["missing_sections"])

    def test_incomplete_page_is_marked_partial(self) -> None:
        client = FixtureRoutingClient()
        client.responses["kac_flight_schedule_GMP"]["response"]["body"]["totalCount"] = 6000
        result = AirportFrictionCollector(
            data_go_key="data-key",
            kma_key="kma-key",
            client=client,
        ).collect(self.output, mode="live", now=self.now, force_weather=True)
        manifest = self.manifest(result)
        observation = next(
            value
            for value in manifest["source_observations"]
            if value["source_id"] == "kac_flight_schedule_GMP"
        )
        self.assertEqual(observation["status"], "PARTIAL")
        self.assertIn("pagination_incomplete", observation["missing_sections"])

    def test_manifest_and_bundle_are_reconstructable(self) -> None:
        result = self.fixture_collect(trigger_source="external")
        manifest = self.manifest(result)
        self.assertEqual(manifest["namespace"], "airport_friction")
        self.assertEqual(manifest["trigger_source"], "external")
        self.assertEqual(len(manifest["source_observations"]), 22)
        self.assertEqual(len(manifest["normalized_records"]), 5)
        with tarfile.open(str(result["bundle_path"])) as archive:
            names = archive.getnames()
        self.assertIn("manifest.json", names)
        self.assertEqual(sum(name.startswith("payloads/") for name in names), 22)

    def test_data_namespace_separation(self) -> None:
        result = self.fixture_collect()
        self.assertIn("/bundles/airport_friction/", str(result["bundle_path"]))
        self.assertIn("/runs/airport_friction/", str(result["run_path"]))
        self.assertFalse((self.output / "bundles" / "2026").exists())

    def test_weather_is_skipped_between_30_minute_slots(self) -> None:
        self.fixture_collect(force_weather=False)
        second = self.fixture_collect(now=self.now + timedelta(minutes=15), force_weather=False)
        manifest = self.manifest(second)
        self.assertEqual(manifest["summary"]["sources_skipped_not_due"], 6)
        gimpo = manifest["normalized_records"][0]
        self.assertEqual(gimpo["source_status"]["weather"], "SKIPPED_NOT_DUE")
        self.assertIsNotNone(gimpo["source_timestamps"]["weather"])
        self.assertNotIn("weather", gimpo["missing_sections"])

    def test_factory_constructs_airport_collector(self) -> None:
        self.assertIsInstance(create_collector("airport_friction"), AirportFrictionCollector)

    def test_external_workflow_dispatch_path(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "collect-airport-friction.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("trigger_source:", workflow)
        self.assertIn("collect-airport", workflow)
        self.assertIn("bundles/airport_friction", workflow)
        self.assertIn("runs/airport_friction", workflow)
        self.assertIn("state/airport_friction", workflow)


if __name__ == "__main__":
    unittest.main()
