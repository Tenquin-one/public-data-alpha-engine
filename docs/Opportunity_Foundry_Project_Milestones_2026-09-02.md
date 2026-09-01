# Opportunity Foundry Project Milestones

**Asset/project tracker · 2026-09-02 · separate from business candidate scoring**

이 문서는 사업 아이디어 순위표가 아니다. 실제 코드·데이터·Probe Result·운영기록을 **Foundry 자산**으로 추적한다. 사업 후보 비교는 [Candidate Portfolio Review](Opportunity_Foundry_Candidate_Portfolio_Review_2026-09-02.md)를 사용한다.

## 1. 검증 기준과 Source of Truth

### 1.1 상태 freeze

| 항목 | 검증값 |
|---|---|
| 확인 시각 | 2026-09-02 06:44 KST |
| Engine code | `public_data_alpha_engine` `main` = `786da7e` (`origin/main`과 일치) |
| Production asset | fetch 후 `origin/data` = `4a5c810b` |
| 주의한 stale source | 별도 local `data` worktree는 `e41acfc`에 머물러 있어 생산현황 근거로 사용하지 않음 |
| Engine verification | `unittest` 42개 통과, SQLite `integrity_check=ok`, foreign-key error 0 |
| Pre-Launch verification | `unittest` 8개 통과, SQLite `integrity_check=ok` |

실제 구현·축적 상태는 [`README`](../README.md), 코드, workflow, SQLite, fetch한 `origin/data`의 run manifest와 state를 함께 확인했다. 대화나 과거 Snapshot에만 있고 저장소에서 확인되지 않은 것은 `UNKNOWN / needs verification` 또는 `planned`로 표시했다.

### 1.2 해석 규칙

- `CORE / CORE-PILOT / CORE-RADAR / SEED`는 자산 상태다. 사업의 `BUILD / PROBE / SELL / PARK / KILL`과 합치지 않는다.
- 진척도 퍼센트는 사용하지 않는다. 이전 Snapshot의 퍼센트는 내부 추정치였고, 이 문서는 통과한 gate와 관측된 수치만 기록한다.
- collector가 실행된 것, 데이터가 쌓인 것, 제품가치가 검증된 것은 서로 다른 milestone이다.
- `PARTIAL/FAILED` manifest가 남는 것은 관측 자산일 수 있다. 다만 usable coverage와 제품 backtest 준비도를 별도로 측정한다.

## 2. Executive tracker

| Asset / project | Asset state | Evidence ladder | Current verdict | Next value milestone |
|---|---|---|---|---|
| Public Data Alpha Engine | **CORE-PILOT** | EVIDENCE → ASSET infrastructure | 핵심 모듈 구현·테스트 완료. upstream 일일 운영과 National Priority Watch는 미완료 | 30일 무인 upstream run + planned→open reconciliation + provenance audit |
| Seoul realtime commercial district Archive | **SEED / ASSET forming** | ASSET accumulation | 8개 지역 production cohort 5.73일. 정상 누적이나 cadence 이상 존재 | 8–12주 품질·비용·event-value audit |
| Airport Friction Seed | **PRIORITY SEED / ASSET forming** | ASSET accumulation | 5개 공항·22 sources 운영 5.33일. KAC 간헐 outage와 PARTIAL 다수 | 8–12주 coverage gate 후 safe-slack proxy backtest |
| Travel Intent & Friction Graph | business `PRIORITY PROBE`; data asset planned | HYPOTHESIS | 공공 시계열 flywheel만 구현. 사용자 intent/outcome GT 없음 | utility probe에서 privacy-safe trip outcome을 얻을 수 있는지 검증 |
| Pre-Launch Product Signal Graph | **Legacy SEED**; business PARK | PROBE RESULT / ASSET | 40 events backtest 보존. prospective cohort는 미가동 | 무비용 prospective negative sample이 가능할 때만 재개 |
| Foundry decision ledger / Seed governance | **CORE** | ASSET | Charter·Snapshot·이번 consolidated update 존재 | 이후 상태·점수 변경에 evidence link와 stop/go result 의무화 |

## 3. Dependency and stop gates

```text
Registry / Pre-release signals
        ↓
Diff / Classifier / Alpha scoring / Seed Queue
        ↓
Collector Factory
        ↓
Seoul + Airport time-axis assets
        ↓  [8–12 week quality / rights / cost gate]
Backtestable proxy and failure analysis
        ↓  [measurable lift over naive baseline]
Free consumer utility Probe
        ↓  [privacy-safe intent/outcome Ground Truth]
Proprietary advice improvement → aggregate B2B intelligence
```

어느 gate가 실패해도 아래 단계를 미리 만들지 않는다. 특히 consumer app은 collector 존재만으로 정당화되지 않는다.

## 4. Public Data Alpha Engine

**Asset state:** `CORE-PILOT`

**Objective:** 지금 저장하지 않으면 복원하기 어려운 경제적 상태를 upstream signal에서 찾고, 권리·비용·축적가치를 통과한 소수만 표준 collector와 Seed Queue로 연결한다.

### Current State

코드 수준의 파이프라인은 구현돼 있고 42개 test가 통과한다. 로컬 SQLite에는 dataset 6개, dataset event 6개, NIA pre-release signal 4개, signal↔dataset link 1개, alpha score 10개, scoring dimension 162개, Seed Queue 6개가 있다. Seed Queue 중 `COLLECT_NOW`는 4개다.

다만 이는 **bootstrap 및 작동증거**이지, Registry/NIA upstream이 매일 무인으로 갱신된다는 증거는 아니다. 저장소에는 `scripts/run_core_daily.sh`가 있지만 `.github/workflows/`에는 core-daily workflow가 없다. 현재 자동 운영이 확인된 것은 Seoul과 Airport collector다.

### Completed

- **Registry Mirror:** ODCloud 목록 API와 current/planned CSV를 공통 schema로 정규화하는 CLI 구현.
- **Metadata Diff:** 신규·변경 field event와 planned→open reconciliation 구현 및 test 통과.
- **Pre-Release Watcher:** NIA HTML parse, signal upsert, dataset linking 구현. 현재 DB에 4 signals, 1 link.
- **Ephemeral / Alpha Scoring:** PRA, Ephemeral, Seed dimension과 HUMAN/AI override 분리 구현.
- **Seed Queue:** Seed ≥75 + rights PASS + cost PASS gate 구현. 현재 6개 중 4개 `COLLECT_NOW`.
- **Collector Factory:** `seoul_city`, `airport_friction` 두 constructor를 lazy factory에서 지원.
- **Asset layer:** raw hash, gzip, immutable run manifest, health/gap, source timestamp, namespace 분리 구현.
- **Verification:** 42 tests, DB integrity와 foreign-key check 통과.

### In Progress

- Engine 구성요소를 실제 upstream 일일 cycle로 연결하는 운영 gate.
- Seed Queue의 후보가 collector specification·workflow deployment로 얼마나 자동 연결되는지 검증.
- Seoul/Airport의 운영 failure를 scoring/queue review로 되돌리는 feedback loop.

### Blocker / Unknown

- **National Priority Watch는 독립 source/module/workflow로 저장소에서 확인되지 않았다.** 현재 확인 가능한 pre-release source는 NIA watcher다. 따라서 상태는 `planned / needs implementation evidence`다.
- `scripts/run_core_daily.sh`는 존재하지만 실제 scheduler 등록·최근 run history는 확인되지 않았다.
- 로컬 DB timestamp만으로는 Registry/NIA가 이후 반복 갱신됐다고 말할 수 없다.
- generic public-data search나 watcher는 희소자산이 아니며 독립 business로 승격할 수 없다.

### Next Gate

1. National Priority/RFP/open-plan source를 source ID·rights memo·checked-at과 함께 Registry upstream에 등록한다.
2. 30일 동안 사람이 손대지 않는 daily mirror/watch/score run을 보존한다.
3. 최소 한 건의 metadata change 또는 planned→open reconciliation을 before/after event로 재현한다.
4. 자동 Seed Queue 추천이 사람 검토에서 왜 통과/탈락했는지 ground-truth label을 남긴다.

### Success Metric

- 30일 expected daily run의 95% 이상 manifest 존재.
- 모든 diff/signal에 source URL, observed time, raw hash 또는 reproducible source reference 존재.
- planned→open 또는 metadata-change 사례 1건 이상 end-to-end 재현.
- 신규 `COLLECT_NOW`는 rights·cost·Data Seed gate를 모두 통과하고 수동 정제 없이 collector spec 초안을 생성.
- active upstream 운영비가 거의 0이고 반복 사람 개입이 없음.

### Do Not Build Yet

- public data 검색 UI나 generic change-monitoring SaaS
- Seed의 지불 evidence 전 enterprise dashboard/API product
- National Priority Watch를 별도 사업으로 포장하는 것
- 모든 open dataset을 무차별 mirror/archive하는 것

## 5. Seoul realtime commercial district Archive

**Asset state:** `SEED / ASSET forming`

**Objective:** 서울시가 분단위 과거 원천을 충분히 제공하지 않는 8개 대표지역의 현재 상태를 저비용·자동으로 보존해 Data Time Advantage를 만든다.

### Current State

| Metric | Verified value |
|---|---:|
| 최초 sample run | 2026-08-26 08:55:25 KST |
| 최초 8-area `SEED_COHORT` run | **2026-08-27 12:56:29 KST** |
| 최신 확인 run | 2026-09-02 06:30:44 KST |
| production cohort duration | **5.73일** |
| production cohort runs | **722** = SUCCESS 716 + PARTIAL 6 |
| production area records | **5,776** = OK 5,749 + ERROR 11 + DUPLICATE 10 + PARTIAL 6 |
| 전체 history | 729 runs = SUCCESS 722 + PARTIAL 6 + FAILED 1 |
| manifest가 선언한 신규 gzip 합계 | 165,067,374 bytes, 약 157.4 MiB |
| 최신 run | 8/8 area OK, missing section 0, schedule health OK |

8개 지역은 홍대 관광특구, 성수카페거리, 이태원 관광특구, 명동 관광특구, 강남역, 잠실 관광특구, 광화문·덕수궁, 여의도다.

### Completed

- 8-area collector, raw gzip/hash dedupe, immutable bundle/run manifest, health state, data branch 구조 운영.
- 공식 이용허락과 상권·도시 data scope memo 기록.
- sample에서 기대 8 sections 확인 후 production cohort 전환.
- 최신 production run에서 8개 area 전부 HTTP 200, missing section 0 확인.

### In Progress

- 8–12주 uninterrupted accumulation.
- 누락·중복·latency·저장량과 section drift 관찰.
- event annotation과 same-day/time baseline을 만들 수 있는 기간 확보.

### Blocker / Anomaly

- 전체 run 인접간격 중 **5분 미만이 71회**, **37.5분 초과가 15회**다. 최신 run도 이전 run과 120초 차이다.
- 현재 health logic은 late gap은 탐지하지만 over-frequency/duplicate clock을 실패로 보지 않는다.
- 저장소의 Seoul workflow에는 GitHub 15분 schedule이 있다. 과거 Snapshot은 external scheduler 전환 준비를 언급했지만, Seoul manifest에는 trigger provenance가 없어 5분 미만 실행의 두 번째 clock/source를 확정할 수 없다. `UNKNOWN / needs verification`다.
- `event_annotations`와 `snapshot_features`는 아직 가치검증용 결과가 없다. 데이터가 쌓인 것과 파생상품 가치가 생긴 것을 혼동하면 안 된다.

### Next Gate

1. 5분 미만 run의 trigger source를 workflow/run metadata로 식별하고 single-clock 여부를 결정한다.
2. over-frequency와 late-gap을 동시에 보는 cadence audit를 수행한다.
3. first cohort 기준 8주인 **2026-10-22**, 12주인 **2026-11-19** 사이에 첫 value review를 한다.
4. 대표 event window를 사전에 정의하고 population/commercial/traffic/weather 변화가 noise 대비 재현되는지 본다.

### Success Metric

- expected 15분 slot coverage 95% 이상, unresolved gap 0.
- area-level OK 또는 valid duplicate 비율 99% 이상; schema missing은 별도 원인분류.
- 불필요한 5분 미만 over-collection 제거 또는 명시적 근거 기록.
- 12주 예상 저장량·Git repository growth가 운영 한도 안에 있고 월 현금비용이 거의 0.
- 최소 3개 pre-registered event window에서 timestamp join이 가능하며, 적어도 한 파생가설이 naive same-time baseline보다 설명력이 있음.

### Do Not Build Yet

- 전체 82개 상권/121개 장소 확대
- Seoul Now, Event Economic Impact, Pop-up Site Intelligence 제품
- event label을 사후에 골라 맞추는 분석
- 품질 audit 전에 별도 DB/server/dashboard 도입

## 6. Airport Friction Seed

**Asset state:** `PRIORITY SEED / ASSET forming`

**Objective:** 김포·제주·김해·청주·대구 5개 공항의 process time, congestion, realtime flight, schedule, parking, weather를 시계열로 축적해 `Airport Last Safe Minute / safe slack` 가능성을 검증한다.

### Current State

| Metric | Verified value |
|---|---:|
| 최초 live manifest | 2026-08-27 22:38:58 KST |
| 최신 확인 manifest | 2026-09-02 06:30:37 KST |
| accumulated duration | **5.33일** |
| runs | **690** = SUCCESS 138 + PARTIAL 334 + FAILED 218 |
| logical sources | **22** = KAC 16 + KMA 6 |
| normalized airport records | **3,450** = OK 790 + PARTIAL 2,660 |
| schedule health | OK 687 + WARNING 2 + NO_BASELINE 1 |
| cumulative new gzip | 4,142,767 bytes, 약 3.95 MiB |
| last all-success run | 2026-09-01 20:15:30 KST |
| latest run | KAC transport timeout/circuit open, KMA not due; manifest FAILED, `workflow.failure=false` |

KAC `result 04`는 24개 run에서 관측됐고 기간은 2026-08-28 00:35–08:36 KST였다. 공식 guide와 맞춘 XML/100-row request, pagination, circuit breaker가 반영된 뒤 all-22-source success가 실제 확인됐다. 따라서 `result 04` request-shape 문제는 역사적 issue로 보존하되 현재 주요 blocker는 간헐적인 KAC institution transport outage와 source-level PARTIAL이다.

### Completed

- 5개 공항, 22 logical source, 15분 KAC/30분 KMA cadence-gating 구현.
- raw page 보존, content hash, pagination cap, source timestamp, normalized 5-airport record, gap/health/storage manifest 구현.
- KAC result 04 request-shape 교정과 all-source live success 확인.
- KMA METAR/IWXXM nullable field, warning `03 NO_DATA`, KAC circuit breaker와 provider outage 처리 구현.
- Airport와 Seoul concurrency queue 분리, data-branch writer retry 구현.
- old GitHub backup schedule은 2026-08-29 제거; 현재 workflow는 external `workflow_dispatch` 단일 clock을 의도한다.
- 42 tests에 auth failure, provider outage, partial, pagination, schema drift, reconstruction, redaction, quota가 포함돼 통과.

### PARTIAL / email-alert handling

저장소에서 다음 수정이 확인됐다.

- `77db754` (2026-08-31 18:41 KST): expected PARTIAL에 `--strict`를 사용하지 않아 workflow를 green으로 유지.
- `02f8d86` (2026-08-31 19:04 KST): provider outage와 intervention-required infrastructure/auth failure를 분리.
- `e563132` (2026-08-31 23:12 KST): Seoul/Airport concurrency queue 분리.
- `786da7e` (2026-08-31 23:20 KST): transport timeout을 provider-level failure로 처리.

최신 data state의 `health.workflow.failure=false`가 이 분리를 실제 manifest에 반영한다. 따라서 KAC 전체 timeout으로 manifest가 `FAILED`여도 GitHub workflow failure 알림을 만들지 않는 경로는 **코드·test·data state에서 확인됨**이다. 다만 사용자의 실제 inbox에서 수정 후 실패메일이 0건이었는지는 저장소만으로 확인할 수 없으므로 `needs external verification`다.

### In Progress

- 8–12주 coverage와 provider reliability 축적.
- KAC partial/error 원인별 분포, 공항별 usable fields, day/time/holiday coverage audit.
- planned schedule와 day-of-operation status의 차이, process/congestion/parking/weather join 가능성 검증.

### Blocker

- 5.33일은 seasonality·요일·event·weather를 평가하기에 부족하다.
- 690개 run 중 PARTIAL/FAILED가 많아 단순 run 수를 usable sample 수로 읽을 수 없다.
- 저장소에 `Last Safe Minute`, `safe slack`, calibrated boarding probability backtest 구현은 확인되지 않았다.
- public sources는 flight operation outcome은 주지만 **개별 사용자가 실제로 제시간에 도착·보안통과·탑승했는지**를 주지 않는다. 따라서 public data만으로 `boarding success probability`라는 표현을 쓰면 안 된다.
- 사용자 출발지, 이동수단, 공항 도착시각, security/boarding outcome을 수집하는 privacy-safe utility와 consent 설계는 아직 없다.

### Next Gate — value milestone

1. 8–12주 data에서 expected slot coverage, KAC due-source usability, 공항별 missingness를 먼저 확정한다.
2. `scheduled departure / estimated departure / process time / parking / weather`로 **operational safe-slack proxy**를 정의한다.
3. 시간순 out-of-time split으로 static timetable 또는 fixed-buffer baseline과 비교한다.
4. proxy가 baseline을 이길 때만 free web utility를 만들고, 앱보다 먼저 minimal trip outcome capture를 검증한다.
5. 실제 user outcome이 모인 뒤에만 boarding probability/calibration을 별도 모델로 평가한다.

### Success Metric

- 8주 이상, expected 15분 slot coverage 95% 이상.
- KAC due-source usable observation(`OK/PARTIAL/DUPLICATE` 중 핵심 field 보유) 90% 이상을 공항별로 확인.
- source/version drift와 provider outage를 분리한 missingness report 완성.
- safe-slack proxy가 out-of-time holdout에서 fixed-buffer baseline보다 error/calibration 중 최소 한 핵심지표를 개선하고 다른 지표를 악화시키지 않음.
- boarding probability는 trip-level user outcome과 pre-registered calibration metric 없이는 milestone 통과 불가.

### Do Not Build Yet

- iPhone/native app
- 유료 consumer subscription
- 개인 raw trip data 판매
- `boarding probability` 마케팅 문구
- B2B Airport Access Stress/Parking Demand/Route Intent product
- 김포 cell-level indoor parking의 장기 archival collector

## 7. Travel Intent & Friction Graph

**Business state:** `PRIORITY PROBE`

**Asset state:** proprietary GT layer는 `planned`; 현재 공공 Airport Seed만 존재

**Objective:** 무료 utility가 사용자의 self-interested trip input과 실제 outcome을 만들고, 그 Ground Truth가 더 나은 departure advice와 익명 집계형 B2B intelligence를 강화하는 flywheel을 검증한다.

### Current State

공공 Airport Friction collector는 구현·운영 중이다. 그러나 consumer utility, user intent schema, outcome capture, advice backtest, retention, distribution, 광고 또는 B2B 구매 evidence는 저장소에서 확인되지 않는다. 따라서 사업은 여전히 `HYPOTHESIS / PRIORITY PROBE`다.

### Completed

- flywheel과 non-goals 정의.
- 5-airport public source와 rights/quota/runbook 구현.
- 앱보다 data/backtest를 앞세우는 stop rule 확정.

### In Progress

- Airport public time series accumulation.
- safe-slack proxy와 user GT 사이의 경계 명확화.

### Blocker

- public data만으로 individual trip success GT를 만들 수 없음.
- free utility의 distribution과 repeat use evidence 없음.
- B2B payer, product unit, minimum aggregation/privacy threshold 미검증.

### Next Gate

Airport Seed의 quality/backtest gate를 통과한 뒤, 설치 없는 mobile web으로 한 공항/한 trip flow를 Probe한다. 입력은 필요한 최소값만 받고, raw 개인경로 판매를 금지하며, outcome 회수율과 advice usefulness를 측정한다.

### Success Metric

- utility 사용자가 자기 이익을 위해 trip input을 자발적으로 제공.
- reminder 없이 또는 최소 reminder로 outcome 회수 가능.
- advice가 fixed-buffer baseline 대비 실제 safe arrival outcome 또는 user-rated usefulness를 개선.
- 개인식별 없이 집계 가능한 minimum cohort와 data retention rule을 사전 정의.

### Do Not Build Yet

- App Store 출시
- multi-airport consumer product expansion
- 광고수익을 주 수익가설로 계산
- B2B sales deck/직접영업

## 8. Pre-Launch Product Signal Graph

**Asset state:** `Legacy SEED`

**Business state:** `PARK`

**Objective:** 인증·공식 신호가 한국 출시시점과 commerce lead를 얼마나 선행하는지 leakage-safe backtest로 보존한다.

### Current State

| Metric | Verified value |
|---|---:|
| independent launch events | 40 |
| certifications | 24 |
| high-confidence eligible events | 13 |
| Commerce Lead median | 58일 |
| 45–90일 비율 | 69% |
| rolling Prediction MAE | 28.2일 |
| prospective `collection_run` | **0** |
| product candidates / commerce snapshots / prediction snapshots | **0 / 0 / 0** |

역사 backtest와 8 tests는 재현되지만 prospective cohort는 실제 운영되지 않는다. 따라서 “collector가 존재”와 “시간축이 계속 쌓임”을 구분해 상태를 frozen Legacy SEED로 둔다.

### Completed

- 40 independent events, 24 certification records, 144 evidence links, 86 sources.
- leakage-safe rolling prediction과 confidence guardrail.
- negative sample·Replacement Effect·Buy-or-Wait의 불충분성을 명시적으로 `INSUFFICIENT_DATA` 처리.

### In Progress

- 없음. 현재 active spend를 중단하고 자산만 보존한다.

### Blocker

- mature negative sample 0, prospective candidate 0.
- price/promotion/inventory snapshot 0.
- raw certification alert의 직접 상품성과 자동 distribution 부족.
- shopping crawler는 rights·maintenance·platform dependency가 Founder Fit과 충돌.

### Next Gate

공식·무비용 prospective source와 자동 scheduler가 생기고, 기존 자원 우선순위를 침해하지 않을 때만 재개한다. 기존 방법론의 최소기준은 mature candidate 20개와 negative sample 5개, 후속관계 event 10개, event 전후 snapshot 각 2개다.

### Success Metric

- prospective candidate가 실제 time-stamped raw source와 함께 자동 축적.
- 365일 maturity rule로 negative outcome을 사후선택 없이 기록.
- launch window가 out-of-time 기준에서 기존 28.2일 MAE를 유의미하게 개선.
- 가격·재고 source는 명확한 rights와 거의 0 운영비를 동시에 충족.

### Do Not Build Yet

- certification alert consumer product
- Korea Launch Probability 공개
- Buy-or-Wait recommendation
- unofficial retail crawling과 affiliate product

## 9. Foundry decision ledger and operating milestones

**Asset state:** `CORE`

**Objective:** 아이디어 수를 늘리는 대신, candidate state·asset state·evidence·probe result·kill thesis를 재현 가능한 decision history로 유지한다.

### Current State

- v0.4 Charter(2026-08-26), Status Snapshot(2026-08-27), 이번 Candidate Review와 Milestone tracker가 존재한다.
- Mature score는 freeze했고 WILD는 별도 Exploration Score로 분리했다.
- Evidence Confidence를 positive attractiveness와 분리했다.

### Completed

- Foundry Score, five hard gates, Evidence Ladder, dual state system 확정.
- 2026-08-27 mature PARK/KILL baseline 고정.
- WILD divergence와 cold convergence의 분리평가 도입.
- 사업 portfolio와 project milestone 문서 분리.

### In Progress

- Tier 1 cheap probe의 실제 결과를 decision ledger로 전환.
- Seed quality metric과 business value metric의 분리.

### Blocker

- 기존 Source of Truth가 synced Word 문서, 대화, repository docs로 분산돼 있다.
- WILD 아이디어 수가 늘면 비슷한 mechanic을 독립 사업으로 중복 계산할 위험이 있다.
- Probe metric을 사후에 바꾸면 false positive가 생긴다.

### Next Gate

Personal Laugh Engine과 Group Chat Sidecar의 probe contract를 실행하기 전에 sample, success metric, stop rule을 freeze하고 결과를 `PROBE RESULT`로 추가한다.

### Success Metric

- score/state 변경마다 source 또는 Probe Result link 존재.
- active cheap probe 동시 최대 2개.
- PARK/KILL 재활성화는 기존 kill thesis를 깨는 새 evidence를 명시.
- 월별 review에서 새 idea 수보다 closed uncertainty 수가 많음.

### Do Not Build Yet

- 모든 WILD 후보의 MVP
- Exploration Score와 Foundry Score의 통합 leaderboard
- evidence 없는 점수 미세조정
- 과거 KILL 후보의 이름 변경 재등록

## 10. Immediate milestone order

1. **수집을 유지하되 먼저 품질을 계측한다.** Seoul over-frequency 원인과 Airport KAC usable coverage를 확인한다.
2. **Public Data Alpha Engine upstream 운영을 증명한다.** National Priority Watch는 구현증거 전까지 planned다.
3. **8–12주 전 앱을 만들지 않는다.** Seoul은 2026-10-22~11-19 review window, Airport는 동등한 quality window를 사용한다.
4. **WILD cheap probe는 동시에 2개만 한다.** Personal Laugh Engine과 Group Chat Sidecar부터 시작한다.
5. **기존 PARK/KILL에 자원을 쓰지 않는다.** 새 evidence가 없으면 score와 state를 유지한다.
