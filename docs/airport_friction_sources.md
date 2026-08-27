# Airport Friction Seed v0.1 — official source audit

Verified against official first-party pages and their embedded Swagger definitions on 2026-08-28 (Asia/Seoul).

## KAC / Public Data Portal

The project owner confirmed applications for seven KAC services on 2026-08-27. Six are accumulated by Airport Friction Seed; the Gimpo cell-level service is reserved for on-demand app display. All seven are free, allow unrestricted use, auto-approve development accounts, and publish a development allowance of 5,000 calls/day per service. One `DATA_GO_KR_SERVICE_KEY` can be reused across the approved services.

| Dataset | Official ID | Endpoint used | Parameters used | Fields retained |
|---|---:|---|---|---|
| [Airport process time GW](https://www.data.go.kr/data/15158950/openapi.do) | 15158950 | `https://apis.data.go.kr/B551178/airport-process-time/v1` for GMP/CJU; `/v2` for PUS/CJJ/TAE | `pageNo`, `numOfRows`, `type=xml`, `serviceKey` | `IATA_APCD`, `PRC_HR`, `OPR_STS_CD`, `STY_TCT_AVG_A..D`, `STY_TCT_AVG_ALL` |
| [Airport congestion GW](https://www.data.go.kr/data/15159598/openapi.do) | 15159598 | `https://apis.data.go.kr/B551178/airport-congestion/v1` for GMP/CJU; `/v2` for PUS/CJJ/TAE | `pageNo`, `numOfRows`, `type=json`, `serviceKey` | v2: `IATA_APCD`, `PRC_HR`, `CGDR_A_LVL`, `CGDR_B_LVL`, `CGDR_C_LVL`, `CGDR_ALL_LVL` |
| [Realtime parking GW](https://www.data.go.kr/data/15158681/openapi.do) | 15158681 | `https://apis.data.go.kr/B551178/parking-realtime-status/info` | one nationwide request with `numOfRows=1000`; `schAirportCode` omitted | `parkingIstay`, `parkingFullSpace`, `parkingAirportCodeName`, `parkingGetdate`, `parkingGettime`, `parkingIincnt`, `parkingIoutcnt`, airport names |
| [Nationwide parking congestion GW](https://www.data.go.kr/data/15158689/openapi.do) | 15158689 | `https://apis.data.go.kr/B551178/parking-congestion/info` | one nationwide request with `numOfRows=1000`; `schAirportCode` omitted | `parkingCongestion`, `parkingCongestionDegree`, `parkingOccupiedSpace`, `parkingTotalSpace`, `sysGetdate`, `sysGettime`, facility and airport names |
| [Realtime flight status GW](https://www.data.go.kr/data/15158625/openapi.do) | 15158625 | `https://apis.data.go.kr/B551178/flight-status/depart` | one domestic departure request per airport, local date and a narrow time window | `fgenTime`, flight ID, scheduled/estimated time, status, origin/destination, codeshare IDs |
| [Flight schedule GW](https://www.data.go.kr/data/15158949/openapi.do) | 15158949 | `https://apis.data.go.kr/B551178/flight-schedule/dom` | one current-date domestic schedule request per departure airport | flight number, origin/destination codes, departure/arrival times, validity dates, day-of-week flags, airline, purpose |

The process-time page defines four stages: check-in → identity, identity → security, security → boarding, and boarding → aircraft departure. The congestion page defines only the first three stage levels. Therefore boarding-to-departure seconds are populated, while the fourth-stage congestion level remains null.

The embedded Swagger for congestion `/v1` currently declares `items` as a string and omits its item fields. The collector still archives the raw GMP/CJU response and accepts the documented v2 field names if present; a live payload that differs remains `PARTIAL` rather than being force-mapped.

The parking detail prose says “available spaces,” while its Swagger calls `parkingIstay` the number of currently parked vehicles. v0.1 follows the field-level Swagger: `occupied = parkingIstay`, `capacity = parkingFullSpace`, and `available = max(capacity - occupied, 0)` as an explicitly derived value.

The two accumulated parking services are intentionally not collapsed. Realtime parking supplies vehicle/capacity counters, while parking congestion supplies KAC's own label and congestion degree.

[Gimpo indoor available spaces GW](https://www.data.go.kr/data/15158508/openapi.do) (15158508) is deliberately **not** called by the Seed collector. Its cell-level `EMPTY`/`IN` state is most useful at the moment a user asks for Gimpo parking guidance, and historical cell rows would add substantial storage without strengthening the initial airport-level friction backtest. Keep the approved access for a future B2C on-demand request; do not archive its payloads in the data branch.

Realtime flight status and flight schedule are also separate. `/depart` is the observed day-of-operation state including delays and cancellations. `/dom` is the planned recurring timetable with validity dates and weekday flags. v0.1 collects domestic schedules for the five priority airports and retains timetable-versus-live 30-minute differences. The `/dom` Swagger publishes no data-generation timestamp, so its provider timestamp is null; collection time and raw content hash still preserve when a schedule version was observed.

KAC announced the GW replacements in [the 2026-06-12 transition notice](https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000004750). The retired endpoints are not used.

The August 2026 KAC reference guides show XML in every request example. The
collector therefore requests `type=xml` with 100 rows per page and places the
service key first, matching the guide's ordering and response format. This avoids the
gateway `04 HTTP_ERROR` observed when the newly migrated services were called
with forced JSON and 1,000-row pages; raw XML remains gzip-compressed and the
same normalization layer handles it.

Live verification on 2026-08-28 then matched the guide exactly with a 10-row
page. All 16 calls across the six KAC service families passed gateway
authentication but timed out while waiting for the institution response. This
is a KAC/GW linkage outage rather than missing overnight data, a bad key, or an
unapproved service. The collector probes two KAC operations per run and opens a
run-local circuit after two consecutive transport failures, while KMA and the
immutable manifest continue normally. Every new run probes again, so recovery
is automatic.

## KMA API Hub

The [KMA API Hub terms and quota page](https://apihub.kma.go.kr/apiInfo.do) states that a general-member account and authentication key are issued automatically at signup, and provides 20,000 calls/day and 5 GB/day. APIs are free and subject to the applicable Korea Open Government License type. The aviation detail page still exposes per-function `API 활용신청` actions, so setup only verifies those functions are active; there is no separate key-issuance application. The two individual aviation endpoint pages do not display a numbered Public Nuri type, so v0.1 does not invent one: it records the Hub-wide condition and requires a rights review if the service page or terms change.

| Data | Endpoint used | Cadence | Parameters / retained values |
|---|---|---:|---|
| [Domestic METAR/SPECI](https://apihub.kma.go.kr/apiList.do?seqApi=14) | `https://apihub.kma.go.kr/api/typ02/openApi/AmmIwxxmService/getMetar` | 30 min | one request per ICAO: RKSS, RKPC, RKPK, RKTU, RKTN; observation time, temperature, dewpoint, pressure, wind, visibility, present weather; raw `msgText` only when the provider includes it |
| [Airport warning](https://apihub.kma.go.kr/apiList.do?seqApi=14&seqApiSub=260) | `https://apihub.kma.go.kr/api/typ02/openApi/AmmService/getWarning` | 30 min | one nationwide request; `tm`, `icaoCode`, `airportName`, `wrngType`, validity, `wrngMsg`, filtered to the five airports |

KMA stopped publishing its temporary test key on 2026-05-06. No unofficial or guessed sample credential is used. The checked-in fixture is an offline contract fixture derived from the official field definitions and is labeled as non-live in both the file and every manifest.

KMA's 2025-08-01 IWXXM 2023-1 upgrade notice says `msgText` is no longer guaranteed. The collector therefore validates observation time and air temperature as the minimum weather contract and keeps the raw METAR text nullable instead of marking an otherwise valid response partial.

## Daily quota proof

`python3 -m public_data_alpha_engine.cli airport-quota` reproduces the calculation.

| Quota bucket | Requests/day | Published limit | Utilization |
|---|---:|---:|---:|
| KAC process time | 192 | 5,000 | 3.84% |
| KAC congestion | 192 | 5,000 | 3.84% |
| KAC parking | 96 | 5,000 | 1.92% |
| KAC parking congestion | 96 | 5,000 | 1.92% |
| KAC flight status | 480 | 5,000 | 9.60% |
| KAC flight schedule | 480 | 5,000 | 9.60% |
| KMA METAR + warning | 288 | 20,000 | 1.44% |

Total network calls are 1,824/day, 109,440/60 days, and 164,160/90 days. Even if the KAC allowance were conservatively treated as one shared 5,000-call pool rather than six collected service allowances, the KAC total is 1,536/day (30.72%).

During the temporary seven-day external-scheduler + GitHub-backup overlap, shared state still cadence-gates KMA but KAC may be requested twice: KAC 3,072/day, KMA 288/day, total 3,360/day. That remains 61.44% even under the conservative single-pool KAC assumption; each individual service also remains below its published limit. Remove the backup `schedule` after the overlap validation.

## Static calendar source

The initial 90-day window uses the official [2026 calendar basis published by the Korea Astronomy and Space Science Institute](https://www.kasi.re.kr/kor/post/newsMaterial/32031), with the later 2026 Labour Day and Constitution Day restorations confirmed by the [Ministry of Personnel Management](https://www.mpm.go.kr/mpm/comm/newsPress/newsPressRelease/?boardId=bbs_0000000000000029&cntId=4250&mode=view). `weekday`, `weekend`, and meteorological `season` are deterministic derivations. An unknown future year deliberately produces no named holiday instead of guessing.
