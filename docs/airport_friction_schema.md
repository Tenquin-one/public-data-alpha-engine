# Airport Friction normalized schema v0.1

Every run contains five normalized records, one for GMP, CJU, PUS, CJJ, and TAE. Raw provider payloads remain authoritative.

## Record shape

- `timestamp`: collector observation time in UTC.
- `airport`: IATA, ICAO, Korean name, English name.
- `friction.checkin.to_identity_seconds|level`: KAC stage A.
- `friction.identity.to_security_seconds|level`: KAC stage B.
- `friction.security.to_boarding_seconds|level`: KAC stage C.
- `friction.boarding.to_departure_seconds`: KAC process-time stage D.
- `friction.boarding.to_departure_level`: always null in v0.1 because KAC congestion documents only three stage levels.
- `friction.total_seconds`, `friction.overall_level`, `friction.operating`: provider total/state values.
- `departures_30m`: domestic departures whose scheduled time is inside `[observed_at, observed_at + 30m]`.
- `delayed_departures_30m`, `cancelled_departures_30m`: subsets identified from KAC's Korean/English status text. These are counts, not predictions.
- `timetable_departures_30m`: planned domestic departures from KAC's recurring schedule for the local date, weekday, and validity range.
- `timetable_minus_live_departures_30m`: planned count minus rows currently visible in realtime flight status; retained as a backtest feature, not treated as an error by itself.
- `departure_window`: exact KST interval used for the 30-minute features.
- `flights_in_requested_window`: normalized flight-level input retained for later recomputation and status-transition backtests.
- `schedule_in_departure_window`: only the schedule rows in the 30-minute feature window. The full schedule payload remains in raw storage and is not repeated in every manifest.
- `parking.capacity|occupied`: summed across returned airport facilities.
- `parking.available`: derived as `max(capacity - occupied, 0)`.
- `parking.occupancy_ratio`: derived as `occupied / capacity` when capacity is positive.
- `parking.provider_congestion`: KAC's independently published congestion label, degree, occupied count, capacity, and facility rows. Raw degree text and numeric percent are both retained.
- `parking.realtime_minus_congestion_occupied`: difference between the two KAC parking counters when both exist; useful for source-lag analysis.
- `weather`: latest METAR-derived observation fields on 30-minute collection runs; null on an intentional not-due run.
- `weather_warnings`: active rows returned by the KMA airport warning endpoint; an empty list is valid.
- `calendar`: local date, ISO weekday, weekend, named holiday, and meteorological season.
- `source_timestamps`: provider timestamps by component. This is the join key for age/staleness analysis.
- `source_status`: `OK`, `PARTIAL`, `DUPLICATE`, `ERROR`, or `SKIPPED_NOT_DUE` per component.
- `missing_sections`, `quality_status`: explicit partial-data markers.
- `record_hash`: SHA-256 of the normalized record before the hash field is added.

## Null and derivation policy

No unsupported value is fabricated. Missing provider fields stay null. An empty flight, schedule, or warning list after a successful API response means “none returned,” while an API failure is separately recorded in `source_status` and `missing_sections`.

The flight schedule `/dom` operation has no provider generation timestamp. `source_timestamps.flight_schedule` is therefore null; `collected_at`, content hash, validity dates, and immutable raw payload provide its observation/version history.

Weather is called every 30 minutes even though the parent collector runs every 15 minutes. Intermediate records say `SKIPPED_NOT_DUE`; a backtest can forward-fill only by using the associated source timestamp and its chosen maximum age.

## Durable data-branch layout

```text
bundles/airport_friction/YYYY/MM/DD/<run-id>.tar
runs/airport_friction/YYYY/MM/DD/<run-id>.json
state/airport_friction/latest_hashes.json
```

The immutable tar contains its manifest plus each new raw response as an individually gzipped member. Identical consecutive source payloads are represented in the run manifest but are not stored again. The run JSON always retains normalized records, failures, retry/latency data, missing sections, quota proof, trigger source, and schedule/source-gap health.

For a 2–3 month backtest this preserves:

- original KAC process, congestion, realtime parking, provider parking-congestion, per-airport live-flight, and per-airport schedule responses;
- original KMA METAR and airport-warning responses;
- per-source content hashes and redacted request provenance;
- live flight-level rows, schedule rows in the feature window, timetable/live differences, and 30-minute aggregate targets;
- friction stages, parking derivations, weather, calendar context, and source timestamps;
- every partial failure and scheduler gap rather than silently dropping bad intervals.
