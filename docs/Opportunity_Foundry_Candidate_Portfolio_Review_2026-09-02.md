# Opportunity Foundry Candidate Portfolio Review

**Consolidated update · 2026-09-02 · internal working document**

이 문서는 기존 Charter나 상태 스냅샷을 덮어쓰지 않는다. 2026-08-26 `Opportunity Foundry v0.4`, 2026-08-27 `Status Snapshot`, 이후 WILD 발산, 그리고 2026-09-02 저장소 검증 결과를 한 번에 비교하기 위한 **추가 기준선**이다. 사업 후보와 Foundry 자산/프로젝트는 분리하며, 자산 마일스톤은 별도 문서인 [Opportunity Foundry Project Milestones](Opportunity_Foundry_Project_Milestones_2026-09-02.md)에서 관리한다.

## 1. 결론

1. **직접 BUILD 승인 후보는 여전히 0개다.** Travel Intent & Friction Graph는 기존 81점과 `PRIORITY PROBE / SEED`를 유지하지만, 데이터·백테스트·사용자 Ground Truth 전에는 앱을 만들지 않는다.
2. 기존 성숙 후보의 Foundry 100점과 상태는 새 외부 근거가 없으므로 변경하지 않는다. 2026-08-27 PARK/KILL 기준선도 유지한다.
3. WILD의 최고 Exploration Score는 Group Chat Sidecar 84점이다. 그러나 이 점수는 성공확률이나 매출전망이 아니다. Bring Your Own Crowd 유통가설을 가장 싸게 시험할 수 있다는 뜻이다.
4. WILD에서 희소자산 잠재력이 상대적으로 큰 후보는 Personal Laugh Engine, Purchase Prediction Receipt, ODDITY INDEX, HUMAN SPECIES, Ticket Prophecy다. 모두 아직 `HYPOTHESIS`이며 Evidence Confidence가 낮다.
5. 가장 먼저 돌릴 저비용 Probe는 **Personal Laugh Engine**과 **Group Chat Sidecar**다. 둘은 각각 `personalization/data lift`와 `embedded distribution/paid host intent`라는 서로 다른 실패가정을 시험한다. GiftQuest와 Ticket Prophecy는 다음 Probe queue다.
6. REALWORLD WEIRDO의 기준형은 **Zero-Ops Anonymous Microplay Network**로 고정한다. 자유 UGC·영상댓글·프로필 관계형 버전은 Founder Resource Fit과 moderation 비용 때문에 별도 `PARK`다.
7. Experience Sidecar/Trip Sidequest Pack은 독립 사업보다 Travel 또는 REALWORLD WEIRDO의 유통·콘텐츠 레이어로 보존한다. Human Sidequest도 standalone 플랫폼이 아니라 `CORE-RADAR` 메커니즘으로만 남긴다.
8. Generic Internet Change Radar는 기존 generic watcher KILL thesis를 깨지 못한다. Public Data Alpha Engine의 기술 재사용만으로는 충분하지 않으며, 독점적인 수직 source·outcome·distribution이 확인되기 전에는 `KILL`이다.

## 2. 기준 소스와 검증 범위

| Source | 확인 기준 | 이 문서에서의 역할 |
|---|---|---|
| `sources/Opportunity_Foundry_v0.4_2026-08-26.docx` | 2026-08-26 Charter | Foundry 원칙, 하드게이트, 상태체계, 기존 포트폴리오 |
| `sources/Opportunity_Foundry_Status_Snapshot_2026-08-27.docx` | 2026-08-27 Snapshot | 기존 100점, Travel/Airport 우선순위, PARK/KILL 기준선 |
| 연결 대화 `사업기회 발산 탐색` | 2026-09-02까지의 WILD 탐색 | 최근 후보 정의, 구조 교정, cheap probe 가설 |
| [`public_data_alpha_engine`](../README.md) | `main` 786da7e, `origin/data` 4a5c810b를 2026-09-02 06:44 KST에 확인 | 실제 구현·축적 여부, 기술자산과 사업가설의 분리 |
| `prelaunch_signal_graph` local project | DB·backtest·8개 test 확인 | Pre-Launch 자산은 보존하되 사업은 PARK라는 근거 |

확인되지 않은 매출, 고객수, 전환율, 시장규모는 추정하지 않았다. 경쟁서비스 검토는 WILD 발산 과정의 구조적 참고로만 사용했고, 이 문서에서 Evidence Confidence를 올리는 실증으로 간주하지 않았다.

## 3. 고정 운영원칙

### 3.1 Foundry thesis

- 아이디어 자체보다 **Evidence / Probe / Ground Truth / Scarce Advantage**를 중시한다.
- Evidence Ladder는 `IDEA → HYPOTHESIS → EVIDENCE → PROBE RESULT → ASSET`이다.
- 사업 상태는 `BUILD / PROBE / SELL / PARK / KILL`, 자산 상태는 `CORE / CORE-PILOT / CORE-RADAR / SEED`다.
- WILD는 `발산 → structural attractiveness → similar service/market review → cold Foundry convergence` 순서로 다룬다. 재미있다는 이유로 기존 Foundry 100점에 바로 넣지 않는다.
- KILL은 삭제가 아니라 active spend 중단이다. 이름만 바꾼 재포장을 새 후보로 세지 않는다.

### 3.2 성숙 후보 Foundry Score

| 축 | 비중 |
|---|---:|
| Money | 30 |
| Defensibility | 25 |
| Autonomy | 20 |
| Distribution | 15 |
| Risk Control | 10 |

다섯 하드게이트가 점수보다 우선한다.

1. Founder Resource Fit
2. Evidence
3. Distribution
4. Data Rights
5. Data Accumulation

초기 현금·월 고정비·사람 운영이 거의 0에 가까워야 한다. 직접영업, 현장작업, 개별 계약·수금, 상시 moderation/CS가 필요한 구조는 직접 BUILD하지 않는다.

### 3.3 WILD Exploration Score

각 항목을 0–5로 평가하고 아래 비중으로 환산한다. 높은 점수가 좋다. `Legal/Platform Dependency Risk`도 높은 점수가 더 안전하다는 뜻이다.

| 축 | 비중 | 질문 |
|---|---:|---|
| User Delight / Novelty | 20 | 즉시 해보고 싶고 결과를 보여주고 싶은가? |
| Low Initial Build Cost | 15 | URL 하나·정적 콘텐츠·기본 DB로 Probe 가능한가? |
| Low Ongoing Ops / Moderation | 15 | 트래픽 외 고정비와 사람 개입을 구조적으로 제거했는가? |
| Organic / Embedded Distribution | 15 | 사용자·creator·event·group이 자기 crowd를 데려오는가? |
| Repeatability / Retention | 10 | 같은 사용자가 자연스럽게 다시 올 이유가 있는가? |
| Monetization Clarity | 10 | 광고규모를 제외해도 결제·affiliate·sponsor 경로가 선명한가? |
| Scarce Advantage / Data Accumulation | 10 | 후발자가 복원하기 어려운 반응·결과·시간축이 남는가? |
| Legal / Platform Dependency Risk | 5 | 저작권·UGC·API·플랫폼 리스크가 낮은가? |

### 3.4 Evidence Confidence 0–5

Evidence Confidence는 후보의 매력도가 아니라 **현재 판정을 지지하는 근거의 질**이다. KILL/PARK 후보도 반례 근거가 강하면 confidence가 높을 수 있다.

| 값 | 의미 |
|---:|---|
| 0 | 아이디어 문장만 존재 |
| 1 | 내부 가설과 유사사례만 존재 |
| 2 | 외부 시장·구조 evidence 또는 재현 가능한 source가 있음 |
| 3 | 자체 샘플·작동 asset·소규모 행동 관측이 있음 |
| 4 | 반복 가능한 Probe Result나 유의미한 longitudinal data가 있음 |
| 5 | 지불·유통·Ground Truth·unit economics가 반복 검증됨 |

## 4. Mature / previously reviewed portfolio

기존 Foundry 점수와 상태를 그대로 유지했다. Evidence Confidence는 이 업데이트에서 처음 붙인 보조값이며 기존 점수를 변경하지 않는다.

| Candidate | Category | Stage / state | Foundry score | Evidence confidence | Initial build cost | Ongoing ops | Monetization | Distribution | Scarce advantage | Key failure mode | Next cheapest probe |
|---|---|---|---:|---:|---|---|---|---|---|---|---|
| Travel Intent & Friction Graph / Airport Last Safe Minute | Utility → proprietary GT → B2B data | EVIDENCE / PRIORITY PROBE + SEED | **81** | 3.0 | 낮음(앱 전) | 낮음~중간 | 집계형 B2B intelligence; 광고는 비용보조 | 무료 공항 utility | 공공 시계열 + 사용자 intent/outcome GT | 공공데이터만으로 권고 lift를 만들지 못하거나 사용자 outcome이 안 모임 | 8–12주 품질통과 후 `Last Safe Minute/safe slack` proxy backtest; boarding probability는 user outcome 없이는 주장 금지 |
| Pre-Opening Commerce Graph | B2B time-axis graph | EVIDENCE / SELL-A·PARK | 75 | 2.5 | 중간 | 중간~높음 | B2B dossier/data | 직접영업 의존 | 개점·폐점 outcome history | entity resolution과 sales가 Founder Fit 위반 | 새 무료 entity source 또는 inbound buyer evidence가 생길 때만 재검토 |
| Procurement Intent Graph | Procurement intelligence | EVIDENCE / SELL-B·PARK | 72 | 2.5 | 낮음~중간 | 중간 | B2B intelligence | 조달업체 직접영업 | 사전규격→RFP→낙찰 시계열 | 구매·결제경로가 수동영업에 묶임 | self-serve 검색수요나 구매자 inbound 증거 전까지 없음 |
| Reconciliation Foundry | B2B recovery SaaS | EVIDENCE / SELL-B·PARK | 69 | 2.5 | 중간~높음 | 높음 | recovery fee/SaaS | 기업영업 | 실제 누수·회수 outcome | SaaS 연동·지원·귀속·수금 | 한 vertical의 익명 샘플에서 자동 검출률만 검증; 고객통합 금지 |
| Machine Condition Passport | Object history / resale | HYPOTHESIS / SELL-B·PARK | 67 | 2.0 | 중간 | 높음 | listing/referral/B2B | marketplace/partner 필요 | condition trajectory → resale outcome | 반복 capture와 책임·현장검증 실패 | 현재효용이 있는 한 카테고리에서 반복 capture 의향 조사만 수행 |
| Building Flexibility Autopilot | Building operations | EVIDENCE / PARK·SELL | 64 | 2.0 | 높음 | 높음 | B2B SaaS | 계약영업 | building operational data | 현장통합·전문책임·계약 | 자동유통/표준 API 증거 없으면 probe 없음 |
| Waste Heat Exchange Opportunity Data | Industrial opportunity data | EVIDENCE / PARK·SELL | 63 | 2.0 | 높음 | 높음 | lead/data fee | 산업 파트너 | spatial supply-demand time series | 물리 인프라·거래·계약 | 공개 source만으로 반복 match를 증명할 때만 재검토 |
| Physical Problem-Solving / 3D Micro-Manufacturing | Physical service/manufacturing | HYPOTHESIS / PARK-LONG | 61 | 2.0 | 높음 | 매우 높음 | 제작 margin | 마켓/직접수주 | problem→design→fit outcome | 실측·CAD 수정·제조·품질책임 | 자동 주문·표준화된 한 부품군 evidence 전까지 없음 |
| Pre-Launch Product Signal Graph — business | Consumer decision signal | PROBE RESULT / business PARK; asset SEED | 58 | **4.0** | 낮음~중간 | 중간 | affiliate/alerts 불명확 | SEO/alerts | 40 launch events + 24 certifications | 음성표본·가격 snapshot·직접 상품성 부족 | prospective source가 무비용 자동화될 때만 mature negative sample 축적 |
| Digital Rescue / Dead SaaS Salvage | Event-driven rescue | HYPOTHESIS / PARK | 53 | 1.5 | 중간 | 높음·불규칙 | acquisition/service | 사건별 탐색 | 사건별 code/data | 반복성·deal sourcing·지원 부재 | 구체 shutdown event와 자동 인수경로가 동시에 생길 때만 |
| Safety Disclosure Baseline Graph | Compliance data | EVIDENCE / KILL·PARK | 약 45 | 3.0 | 낮음~중간 | 중간 | B2B | 직접영업 | 제한적 | 형식문서 비중이 높아 정보밀도·GT가 약함 | Kill thesis를 깨는 outcome-linked dataset 전까지 없음 |

## 5. WILD portfolio — Exploration Score

### 5.1 점수 산출표

각 축은 원점수 0–5다. 총점만 가중합 후 반올림했다.

| Candidate | Delight 20 | Build 15 | Ops 15 | Distribution 15 | Repeat 10 | Money 10 | Scarce 10 | Risk 5 | Exploration score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Group Chat Sidecar | 4.0 | 5.0 | 4.5 | 5.0 | 4.0 | 4.0 | 2.5 | 3.5 | **84** |
| Ticket Prophecy / Audience Prediction League | 4.0 | 4.5 | 4.0 | 4.0 | 4.0 | 3.5 | 4.0 | 3.0 | **80** |
| Secret Mission Engine / Memory Heist / Prediction Party | 4.5 | 4.5 | 4.0 | 4.5 | 3.5 | 3.5 | 2.5 | 3.5 | **80** |
| ODDITY INDEX | 4.0 | 5.0 | 5.0 | 3.0 | 3.5 | 2.0 | 4.0 | 4.5 | **79** |
| Personal Laugh Engine | 4.5 | 4.5 | 4.0 | 3.0 | 4.5 | 2.5 | 4.0 | 3.0 | **78** |
| HUMAN SPECIES | 4.0 | 3.5 | 4.5 | 3.5 | 4.0 | 3.0 | 4.0 | 4.0 | **77** |
| GiftQuest | 4.0 | 5.0 | 4.5 | 4.0 | 2.5 | 4.0 | 2.0 | 3.5 | **77** |
| Purchase Prediction Receipt | 3.5 | 5.0 | 5.0 | 2.5 | 3.0 | 2.5 | 4.5 | 4.5 | **76** |
| Experience Sidecar / Trip Sidequest Pack | 4.0 | 4.0 | 4.0 | 4.0 | 3.0 | 4.0 | 2.5 | 3.5 | **75** |
| REALWORLD WEIRDO — Zero-Ops Anonymous Microplay Network | 4.5 | 3.5 | 4.0 | 3.0 | 4.0 | 2.5 | 3.0 | 4.0 | **73** |
| Receipt Creature | 4.5 | 3.5 | 4.0 | 2.5 | 4.0 | 2.5 | 3.0 | 2.5 | **70** |
| First 24 Hours | 3.5 | 4.0 | 3.0 | 2.0 | 3.5 | 4.0 | 3.0 | 4.0 | **66** |
| Internet Change Radar — generic | 2.0 | 4.0 | 4.0 | 2.5 | 4.0 | 4.0 | 2.0 | 3.5 | **63** |
| Human Sidequest — standalone | 4.5 | 2.5 | 2.0 | 2.0 | 3.5 | 2.0 | 3.5 | 2.5 | **58** |

### 5.2 비교표와 현재 판정

| Candidate | Category | Stage / state | Score | Evidence confidence | Initial build cost | Ongoing ops | Monetization | Distribution | Scarce advantage | Key failure mode | Next cheapest probe |
|---|---|---|---:|---:|---|---|---|---|---|---|---|
| Group Chat Sidecar | Bring Your Own Crowd utility | HYPOTHESIS / PROBE | 84 E | 1.0 | 매우 낮음 | 낮음 | host 월구독·유료 pack | 카톡/WhatsApp/Discord 링크 | room outcome은 남지만 해자는 약함 | host가 한 번 쓰고 재사용·결제하지 않음 | 3개 room template, host 20명; reveal 도달률·14일 host repeat·paid fake-door 측정 |
| Ticket Prophecy / Audience Prediction League | Event prediction sidecar | HYPOTHESIS / PROBE | 80 E | 1.5 | 매우 낮음 | 낮음~중간 | sponsor·affiliate·organizer self-serve | creator/organizer와 실제 이벤트 | prediction→event GT→calibration history | organizer 배포가 수동영업이 되거나 reveal return이 낮음 | 5개 실제 event page; bespoke 운영 없이 share·submit·reveal return 측정 |
| Secret Mission Engine / Memory Heist / Prediction Party | Private-room mechanics | IDEA / PARK as standalone | 80 E | 1.0 | 매우 낮음 | 낮음 | pack·구독 | group host | 독립 scarce asset은 약함 | 아이디어가 여러 얇은 party game으로 분산 | Group Chat Sidecar의 template pack으로만 시험; 독립 브랜드/플랫폼 금지 |
| ODDITY INDEX | Self-knowledge/statistical play | HYPOTHESIS / PROBE | 79 E | 1.0 | 매우 낮음 | 매우 낮음 | 광고·premium statistics | 결과카드 공유·검색 | 생활행동 분포와 weirdness fingerprint | 첫 결과만 보고 재방문하지 않음; 광고규모 미달 | 30문항 static deck, 100 users; completion·share·7일 second session 측정 |
| Personal Laugh Engine | Personalized humor discovery | HYPOTHESIS / PROBE | 78 E | 1.5 | 낮음 | 낮음~중간 | premium·affiliate/ads 후순위 | share/referral, official embed | explicit laugh reaction + Humor Twin CF | playable content health가 낮거나 personalization lift가 없음 | 300 refs, 30–40 testers, generic vs personalized A/B; reaction lift와 latency gate |
| HUMAN SPECIES | Sensor-based human experiment | HYPOTHESIS / PROBE | 77 E | 1.0 | 낮음 | 매우 낮음 | 광고·premium percentile/pack | result-card share·SEO | sensor result distributions | 센서편차가 재미보다 크게 보이거나 repeat가 없음 | 타이머/탭/기울기 3개 web experiment, 100 mobile users; complete·second-play·share |
| GiftQuest | Gift purchase/reveal sidecar | HYPOTHESIS / PROBE | 77 E | 1.0 | 매우 낮음 | 매우 낮음 | affiliate + paid digital wrapping | sender→recipient one-link | 구매·reveal outcome은 제한적 | 수신자 reveal은 재밌어도 affiliate conversion이 없음 | 3개 quest/reveal template; link creation·recipient completion·outbound purchase click |
| Purchase Prediction Receipt | Choice outcome / calibration | HYPOTHESIS / PROBE | 76 E | 1.0 | 매우 낮음 | 매우 낮음 | premium history·affiliate 후순위 | receipt/share/reminder | desire forecast→actual use longitudinal GT | 구매 빈도·회수기간이 길고 follow-up 응답이 없음 | 7/30일 단기 category로 30명; prediction 생성률과 outcome follow-up completion 측정 |
| Experience Sidecar / Trip Sidequest Pack | Experience microplay layer | HYPOTHESIS / PARK as standalone | 75 E | 1.0 | 낮음 | 낮음 | affiliate·pack·sponsor | 이미 구매한 공연/전시/여행 | 장소·event별 play outcome은 약함 | Travel/REALWORLD와 중복되고 pack 제작노동이 늘어남 | 독립 제품 없이 Travel 또는 Ticket page 한 곳에 sidecar A/B |
| REALWORLD WEIRDO — Zero-Ops | Anonymous real-world microplay | HYPOTHESIS / PROBE-QUEUE | 73 E | 1.0 | 낮음 | 낮음 | 광고·sponsor 후순위 | result-card sharing | play→anonymous result distribution | social graph 없이 repeat/share가 충분하지 않음; 광고 트래픽 미달 | 12 curated plays, 50 testers; start→complete, second play, result-card share |
| Receipt Creature | Consumption-to-character play | IDEA / PARK | 70 E | 0.5 | 낮음 | 낮음 | premium·ads | monthly share card | 소비 흔적 history | receipt 입력 friction 또는 금융연동 비용이 재미를 압도 | 금융연동 금지; 수동 5건 입력 후 creature reveal completion만 확인 |
| First 24 Hours | Post-purchase activation | HYPOTHESIS / PARK conditional | 66 E | 1.0 | 낮음 | 중간 | merchant SaaS | merchant embed/QR | product→activation outcome | self-serve가 안 되고 영업·custom content가 필요 | 3 product template + self-serve fake door; merchant 요청이 bespoke면 즉시 PARK |
| Internet Change Radar — generic | Web monitoring | HYPOTHESIS / **KILL** | 63 E | 2.0 | 낮음 | 낮음~중간 | subscription | SEO/self-serve | generic page diff는 희소하지 않음 | 기존 watcher와 차별화·유통·데이터 해자 없음 | probe 금지. unique vertical source+outcome+distribution 세 가지가 동시에 생길 때만 새 버전 등록 |
| Human Sidequest — standalone | Human last-1% / kindness loops | HYPOTHESIS / business PARK; mechanism CORE-RADAR | 58 E | 1.0 | 중간 | 높음 | 불명확 | cold start 양면시장 | Reference Twin/outcome loop는 다른 후보에 재사용 가능 | supply·moderation·matching·human ops가 Founder Fit 위반 | standalone probe 없음; Reference Twin/Fresh Trail Relay를 다른 probe에 삽입 |
| REALWORLD WEIRDO — Social UGC/video variant | Rejected product variant | IDEA / PARK | hard-gate fail | 2.0 | 중간~높음 | **매우 높음** | 광고 | network effect | richer content graph 가능 | UGC hosting·moderation·copyright·abuse·CS | 재개하지 않음. current 기준형은 curated play + fixed reaction + result-only |

`E`는 Exploration Score를 뜻한다. Mature Foundry Score와 서로 더하거나 순위를 합치지 않는다.

## 6. Tier와 자원배분

### Tier 0 — keep accumulating; product BUILD 금지

- **Travel Intent & Friction Graph / Airport Last Safe Minute**: 기존 최상위. 현재 자원은 collector 품질, 데이터 기간, safe-slack proxy backtest에만 쓴다.

### Tier 1 — active cheap probes, 동시에 최대 2개

1. **Personal Laugh Engine** — proprietary reaction data가 실제 personalization lift를 만드는가.
2. **Group Chat Sidecar** — host가 자기 crowd를 데려오고 반복·결제하는가.

두 Probe가 끝나기 전에는 네 후보를 동시에 구현하지 않는다. 성공/실패를 먼저 기록하고 다음 queue로 이동한다.

### Tier 2 — next probe queue

- **GiftQuest** — 돈과 가장 가깝고 하루 수준의 one-link probe가 가능.
- **Ticket Prophecy** — 이벤트가 content와 GT를 공급하지만 self-serve distribution이 필수.
- **ODDITY INDEX** — build/ops가 가장 작지만 광고규모 전 retention evidence가 먼저.
- **HUMAN SPECIES** — 숫자·percentile 중심 Zero-Ops 가능성; 센서 신뢰성과 repeat 검증.
- **Purchase Prediction Receipt** — 장기자산 잠재력은 높지만 follow-up latency를 먼저 줄여야 함.
- **REALWORLD WEIRDO Zero-Ops** — 철학은 보존하되 social graph 없는 repeat를 정적 prototype에서 먼저 확인.

### Tier 3 — keep only as layer/mechanism

- Experience Sidecar/Trip Sidequest Pack → Travel/Ticket/REALWORLD의 layer
- Secret Mission Engine/Memory Heist/Prediction Party → Group Chat Sidecar의 private-room templates
- Human Sidequest → `Reference Twin`, `Fresh Trail Relay`, kindness/outcome mechanism의 `CORE-RADAR`
- First 24 Hours → self-serve merchant demand가 확인될 때만 복귀
- Receipt Creature → 입력 friction을 이기는 delight가 확인될 때만 복귀

### KILL / archive 유지

- Generic Internet Change Radar
- REALWORLD WEIRDO 자유 UGC/video/comment variant는 현재 조건에서 PARK; moderation 경제가 구조적으로 바뀌지 않으면 재개 금지
- 2026-08-27 기존 KILL/archive 전체. generic watcher, generic plugin/factory, static DB, generic lead/success-fee 등을 이름만 바꿔 재등록하지 않는다.

## 7. Novelty/Delight와 Money를 분리한 해석

| 구간 | 후보 | 해석 |
|---|---|---|
| Delight 높음 / Money 불명확 | REALWORLD WEIRDO, ODDITY INDEX, HUMAN SPECIES, Receipt Creature | 광고를 가정해 BUILD하지 않는다. repeat/share가 먼저다. |
| Delight 높음 / Money 상대적으로 명확 | Group Chat Sidecar, GiftQuest, Ticket Prophecy | 가장 좋은 cheap commercial probes. 그래도 실제 결제 evidence는 0에 가깝다. |
| Delight 중간 / Data asset 강함 | Personal Laugh Engine, Purchase Prediction Receipt | 재미 자체보다 explicit reaction/outcome이 쌓여 lift를 만드는지 본다. |
| Money 가설 명확 / Founder Fit 위험 | First 24 Hours, 기존 B2B PARK 후보 | self-serve가 아니면 점수와 무관하게 PARK다. |

Exploration Score에서 Delight는 20점, Monetization은 10점뿐이다. 따라서 높은 Exploration Score를 “돈이 된다”로 읽으면 안 된다. 반대로 Monetization이 선명해도 직접영업·운영·계약이 붙으면 Founder Resource Fit에서 탈락한다.

## 8. Probe contracts

Probe 결과는 인상평이 아니라 사전에 정한 행동지표로 `PROBE RESULT`를 만든다. 아래 수치는 투자판단용 통계기준이 아니라 다음 지출을 허용할지 결정하는 최소 stop/go 기준이다.

### 8.1 Personal Laugh Engine

- **Setup:** official embed 또는 user-supplied URL 중심 300 refs, 30–40 testers, `터짐/피식/안웃김/싫음` explicit reaction.
- **Gate A — content health:** 테스트 세션에서 playable ref 85% 이상, median start latency 3초 이내.
- **Gate B — lift:** popularity/random baseline보다 personalized `터짐+피식` 비율이 상대 15% 이상 높고, 참가자 과반에서 개인 lift가 양수.
- **Stop:** health gate 실패 또는 충분한 rating 후 lift가 거의 없으면 content platform을 만들지 않는다.

### 8.2 Group Chat Sidecar

- **Setup:** 익명투표, 예측, reveal 세 template; host 20명이 자기 group에 링크 배포.
- **Go:** 생성 room의 40% 이상이 5명 이상 참가 후 reveal 도달, host의 20% 이상이 14일 안에 두 번째 room 생성, paid template fake-door 클릭 10% 이상.
- **Stop:** 참가자는 와도 host repeat가 없으면 일회성 party page로 PARK.

### 8.3 GiftQuest

- **Setup:** 선물 reveal/선택/quest 세 one-link flow. 상품재고·결제보관·merchant integration 없음.
- **Go:** sender의 link creation completion 25% 이상, 열린 링크의 recipient completion 40% 이상, affiliate outbound 10% 이상.
- **Stop:** reveal은 완료되지만 구매 클릭이 없으면 유료 digital wrapping 의향을 따로 확인하고 둘 다 약하면 PARK.

### 8.4 Ticket Prophecy

- **Setup:** 실제 일정이 확정된 5개 event page, prediction→event→reveal.
- **Go:** bespoke 운영 없이 organizer/creator 또는 attendee가 링크를 배포하고, 방문자의 prediction submit 20% 이상, submitter의 reveal return 30% 이상.
- **Stop:** 배포마다 직접영업·수동 결과입력이 필요하면 standalone 사업으로 PARK.

### 8.5 ODDITY INDEX / HUMAN SPECIES

- **Setup:** 각각 30문항 deck과 mobile experiment 3개. 금융·건강 진단 표현 금지.
- **Go:** 첫 session completion 60% 이상, 결과카드 share 10–15% 이상, 7일 내 두 번째 session/experiment 20% 이상.
- **Stop:** 첫 결과 curiosity만 있고 second session이 없으면 광고사업 가정을 제거하고 PARK.

### 8.6 REALWORLD WEIRDO Zero-Ops

- **Setup:** curated/pre-generated safe play 12개, 자유댓글·자유 UGC·서버 영상호스팅·DM·follow 없음.
- **Go:** play start→complete 50% 이상, 같은 session의 second play 25% 이상, result-card share 8% 이상.
- **Stop:** 사람/친구 graph를 붙여야만 repeat가 생기면 현재 철학과 Founder Fit을 지키기 위해 PARK.

### 8.7 Purchase Prediction Receipt

- **Setup:** 1년 outcome을 기다리지 않고 7일/30일 사용예측이 가능한 소액·취미·구독 category로 제한.
- **Go:** 예측 생성자의 outcome follow-up completion 40% 이상, reminder 후 return 25% 이상.
- **Stop:** follow-up이 무너지면 calibration history가 생기지 않으므로 장기 제품을 만들지 않는다.

## 9. 다음 포트폴리오 업데이트 규칙

후보를 승격하거나 점수를 바꾸려면 아래 중 하나가 새로 생겨야 한다.

1. 실제 사용자 행동이 기록된 Probe Result
2. 반복 가능한 distribution 또는 payment evidence
3. 복원 불가능한 reaction/outcome/시간축 asset
4. 기존 kill thesis를 깨는 데이터권리·원가·자동운영 변화

새 evidence가 없으면 기존 점수·상태를 유지한다. WILD 이름을 늘리는 대신 상위 후보의 가장 싼 반증실험을 실행한다.
