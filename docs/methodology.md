# Methodology

## 1. 목적과 비목적

목적은 공개데이터 목록을 많이 모으는 것이 아니라, **사라지거나 현재값으로 덮어써지는 상태를 거의 무료로 선점할 수 있는지** 판정하는 것이다. 다음은 비목적이다.

- 모든 원자료의 전수 보관
- 데이터가 쌓이기 전 파생상품 BUILD
- AI가 권리·시장·역사 부재를 추측한 값을 사실처럼 사용
- 소스 갱신보다 빠른 polling

기준은 Opportunity Foundry v0.3의 PRA 9축과 Data Accumulation Gate 7축이다.

## 2. 수집 계층

### Registry Mirror

현재 개방목록은 공공데이터포털 목록조회 API 또는 공식 CSV를 입력으로 받는다. 개방예정목록은 공식 CSV/JSON feed를 같은 normalizer에 통과시킨다. 원래 컬럼은 `metadata_json`에 남기고 다음 공통 필드로 정규화한다.

`external_id`, `title`, `provider`, `public_status`, `expected_release_year`, `api_available`, `file_available`, `update_frequency`, `license`, `terms`, `modified_at`, `source_url`.

정규화 레코드의 canonical JSON SHA-256이 바뀔 때만 field diff를 생성한다. `last_seen_at`은 매 관측마다 갱신하지만, 동일 원문은 새 raw 파일을 만들지 않는다.

### Metadata Diff

감시 이벤트는 `NEW_DATASET`, `MODIFIED_AT_CHANGED`, `PUBLIC_STATUS_CHANGED`, `API_ADDED`, `FILE_ADDED`, `UPDATE_FREQUENCY_CHANGED`, `LICENSE_CHANGED`, `TERMS_CHANGED`, `PROVIDER_CHANGED`, `EXPECTED_TO_OPEN`이다.

예정→공개 연결은 기관명이 같고, 일반어를 뺀 제목 token Jaccard가 0.62 이상일 때 자동 후보로 만든다. 자동 연결은 confidence와 대상 dataset ID를 남기므로 사람이 재검토할 수 있다.

### Pre-Release Watcher

첫 소스는 [NIA 입찰공고](https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=78336)다. 기본 수집 범위는 제목, 공고 유형, 게시일, 기관, 원문 URL이다. 첨부 RFP 전체는 비용·저작권·파싱 복잡도를 늘리므로 v1에서 자동 보관하지 않는다.

signal과 dataset은 token/entity overlap으로 연결한다. confidence는 제품 판단이 아니라 **사람이 볼 후보의 정렬값**이다. 나라장터는 같은 `PreReleaseSignal` 인터페이스를 구현하면 추가할 수 있다.

## 3. Scoring과 override

자동 규칙은 metadata만 사용한다. 돈·JOIN·Ground Truth처럼 metadata로 확정하기 어려운 항목은 낮고 보수적인 기본값을 준다. 공식 문서 검토나 사람 판단이 있으면 `score_overrides`에 HUMAN 또는 AI로 별도 기록한다.

계산 시 `auto_rating`, `override_rating`, `effective_rating`, rationale, evidence를 모두 `scoring_dimensions`에 저장한다. override는 원래 자동값을 덮어 지우지 않는다. 자세한 가중치는 [scoring spec](scoring_spec.md)에 있다.

## 4. Seed Queue gate

다음을 모두 만족해야 `COLLECT_NOW`다.

1. Seed Score ≥ 75
2. rights status = `ALLOW`
3. cost status = `FREE` 또는 `NEAR_ZERO`

점수가 높아도 권리가 제한되면 `METADATA_ONLY`, 권리·비용이 불명확하면 `REVIEW_RIGHTS_COST`다. 이 gate는 권리 불확실성을 점수로 상쇄하지 못하게 한다.

## 5. 서울 Seed 방법

[서울 실시간 도시데이터 페이지](https://data.seoul.go.kr/dataList/OA-21285/F/1/datasetView.do)는 공공누리 1유형, 상업적 이용·변경 가능, 제3저작권자 없음으로 표시한다. 같은 페이지 FAQ는 분단위 대용량 API-to-API 데이터라 과거를 따로 적재하지 않아 제공할 수 없다고 명시한다. [상권 전용 페이지](https://data.seoul.go.kr/dataList/OA-22385/F/1/datasetView.do)도 동일한 이용허락과 과거 미제공을 명시한다.

[공식 매뉴얼 v8.5](https://data.seoul.go.kr/SeoulRtd/downloads/%EC%8B%A4%EC%8B%9C%EA%B0%84_%EB%8F%84%EC%8B%9C%EB%8D%B0%EC%9D%B4%ED%84%B0_%EB%A7%A4%EB%89%B4%EC%96%BC.pdf)에 따르면 통합 데이터는 인구, 상권, 교통, 환경, 행사 등을 결합하고 최소 5분 주기로 갱신된다. 카드소비는 10분 단위로 집계되고 약 15분 후 제공되며 82개 장소를 지원한다. 15분 cadence는 5/10분의 모든 중간 상태를 보존하지는 않지만, 8곳 기준 하루 768회로 운영량을 제한한다.

초기 cohort는 서로 다른 사건·소비 패턴을 갖는 8곳이다.

- 홍대 관광특구: 야간·축제·관광
- 성수카페거리: 팝업·패션·리테일
- 이태원 관광특구: 관광·야간·행사
- 명동 관광특구: 관광 리테일
- 강남역: 통근→야간 상태전환
- 잠실 관광특구: 스포츠·대형행사
- 광화문·덕수궁: 집회·축제·공공행사, 공식 sample 지원
- 여의도: 오피스·금융·축제

## 6. Snapshot 재현성

각 payload는 다음을 남긴다.

- `collected_at`: 엔진 수집시각(UTC)
- `source_timestamp`: 현재 상태 필드 중 가장 최근 서울 현지시각
- redacted source endpoint와 query params
- 원문 SHA-256
- 새로운 content hash일 때만 gzip raw path
- 정규화 JSON과 누락 section 목록
- run/health/retry/HTTP status

예보시각(`FCST_TIME`, `FCST_DT`)과 행사 종료일은 현재 source timestamp 계산에서 제외한다. API 키는 저장하지 않는다.

## 7. 품질과 누락

- 동일 entity의 직전 content hash와 같으면 snapshot을 중복 저장하지 않는다.
- JSON 호출이 실패하면 XML을 한 번 fallback한다.
- HTTP client는 최대 2회 재시도한다.
- 마지막 snapshot이 cadence의 2.5배보다 오래되면 `data_gap_events`를 만든다.
- 기대 section이 없으면 snapshot은 `PARTIAL`, 전부 있으면 `OK`다.
- 카드소비는 신한카드 내국인 표본을 보정한 값이며 전수 거래가 아니다. 가맹점/소비가 적은 영역은 비식별 처리로 누락될 수 있다.

## 8. 향후 feature 공간

`snapshot_features`는 동일 요일·시간대 baseline, percentile, abnormality 같은 feature를 위한 비어 있는 공간이다. `event_annotations`는 행사·집회·날씨·프로모션의 시간구간과 confidence를 저장한다. 충분한 기간과 Ground Truth가 생기기 전에는 계산·상품화하지 않는다.
