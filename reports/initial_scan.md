# Initial Scan — 2026-08-26

## 결론

**CORE 가정은 첫 스캔에서 살아남았다. 서울 실시간 도시·상권 Seed는 `GO: COLLECT_NOW`, 상품 BUILD는 계속 보류한다.**

서울은 다음 네 조건을 동시에 만족한다.

1. 거의 무료: 공식 OpenAPI, 기존 로컬 머신에서 무인 실행 가능
2. 복원 불가: 서울시 FAQ가 과거 실시간 데이터 미제공을 명시
3. 권리 명확: 공공누리 1유형, 출처표시 조건으로 상업적 이용·변경 가능
4. 경제 상태: 카드소비·상권·인구·교통·날씨·행사 상태를 동일 POI와 시간축으로 연결

## 초기 발견 후보

| Rank | Candidate | PRA | Ephemeral | Seed | Queue | 현재 조치 |
|---:|---|---:|---:|---:|---|---|
| 1 | 서울시 실시간 도시데이터 | 69.49 | 90.40 | 96.00 | COLLECT_NOW | 8곳 collector 가동 준비 |
| 2 | 서울시 실시간 상권현황데이터 | 70.41 | 93.60 | 91.80 | COLLECT_NOW | 통합 collector의 상권 section으로 적립 |
| 3 | 공영홈쇼핑 검색어·주문유입·매출순위 | 62.58 | 81.60 | 79.50 | COLLECT_NOW candidate | endpoint/history 범위 확인 후 두 번째 collector 검토 |
| 4 | 공영홈쇼핑 편성·가격·이벤트 | 59.04 | 78.40 | 77.25 | COLLECT_NOW candidate | 위 후보와 상품ID/시간 JOIN 가능성 검토 |
| 5 | 공공데이터포털 목록조회서비스 | 47.33 | 72.00 | 60.27 | HOLD | CORE metadata source로만 사용 |
| 6 | 범정부 개방예정 목록 자체 | 40.35 | 21.00 | 34.40 | HOLD | Seed가 아니라 탐색 input으로 사용 |

`COLLECT_NOW candidate`는 v0.3 gate 통과를 뜻하며 collector가 이미 만들어졌다는 뜻이 아니다. 첫 실제 collector는 서울 하나로 제한했다.

## NIA pre-release scan

| Signal | PRA | Decision |
|---|---:|---|
| 한국독립운동·학사정보 데이터 통합 위탁감리 | 46.38 | MONITOR |
| 지하철·문화·화학물질 데이터 개방 통합 위탁감리 | 46.38 | MONITOR |
| 사회 현안 해결형 복합데이터 세트 구축 방안 연구 | 46.38 | MONITOR |
| 운수종사자관리시스템 데이터 개방체계 구축 | 44.50 | HOLD |

사전규격은 공개확률·선행시간 신호지만 schema, rights, payer가 아직 없어 70점 Deep Review를 넘지 못했다. 이는 정상적인 보수 판정이다.

## 서울 cohort

홍대 관광특구, 성수카페거리, 이태원 관광특구, 명동 관광특구, 강남역, 잠실 관광특구, 광화문·덕수궁, 여의도 등 8곳이다. 관광·야간·팝업·오피스·스포츠·집회처럼 서로 다른 event regime을 일부러 섞었다.

공식 sample 키로 광화문·덕수궁 1곳을 실호출했다.

- result: SUCCESS / quality `OK`
- 확인 section: 인구, 상권, 도로, 주차, 지하철, 버스, 날씨, 행사
- 현재 source timestamp: `2026-08-26T08:20:53+09:00`
- gzip raw: 31,875 bytes
- normalized JSON: 약 158K characters
- source endpoint/query/hash/raw path 모두 DB에 저장, key는 redacted

## 저장량과 비용

실측 gzip 31,875 bytes를 그대로 적용한 보수 단순 추정이다.

| 항목 | 값 |
|---|---:|
| 장소 | 8 |
| cadence | 15분 |
| snapshots/day | 768 |
| gzip/day | 24.48 MB |
| 30일 누적 | 0.734 GB |
| 1년 누적 | 8.94 GB |
| raw files/year | 최대 280,320 |

기존 로컬 디스크에서는 추가 현금비용이 사실상 0에 가깝다. 비교용으로 AWS 공식 공개단가의 S3 Standard 첫 50TB `US$0.023/GB-month`, PUT `US$0.005/1,000`을 적용하면 1년치 8.94GB를 계속 보유하는 시점의 월 storage 약 US$0.21 + 월 PUT 약 US$0.12, 합계 약 **US$0.32/month**다. 계산·전송비는 제외했다. [AWS S3 pricing](https://aws.amazon.com/s3/pricing/)

file 수가 1년 28만 개까지 늘 수 있어 비용보다 inode/backup overhead가 먼저 문제일 수 있다. 8~12주 운영 후 daily pack 또는 전용 object store 전환 여부를 판단한다.

## Rights와 데이터 한계

- [서울 실시간 도시데이터](https://data.seoul.go.kr/dataList/OA-21285/F/1/datasetView.do)와 [상권 데이터](https://data.seoul.go.kr/dataList/OA-22385/F/1/datasetView.do)는 공공누리 1유형과 제3저작권자 없음으로 표시한다.
- 두 페이지 FAQ는 과거 실시간 데이터 제공 불가를 명시한다.
- [공식 매뉴얼](https://data.seoul.go.kr/SeoulRtd/downloads/%EC%8B%A4%EC%8B%9C%EA%B0%84_%EB%8F%84%EC%8B%9C%EB%8D%B0%EC%9D%B4%ED%84%B0_%EB%A7%A4%EB%89%B4%EC%96%BC.pdf)에 따르면 상권은 신한카드 내국인 거래를 보정한 값이며 전수 거래가 아니다. 소수 가맹점·소비 영역은 비식별 처리로 누락될 수 있다.
- 통합 API는 현재 121개 주요장소, 상권 section은 82개 장소다. 초기 8곳은 모두 상권 지원 목록에 있다.

## 운영 검증

- 자동 테스트 13개 통과
- SQLite integrity check `ok`
- foreign key errors 0
- 서울 sample live call 성공
- ODCloud/NIA live smoke는 첫 실행에서 로컬 Python CA bundle 부재로 TLS verification 실패. `/etc/ssl/cert.pem`을 명시하도록 수정했으며 insecure fallback은 두지 않았다. 단일 승인 요청 원칙 때문에 같은 세션에서 외부 재호출은 추가하지 않았다.

## Kill / Go

| Gate | 판정 | 근거/조치 |
|---|---|---|
| Rights | GO | 공공누리 1유형. 변경되면 collector 즉시 중단, metadata only |
| Historical scarcity | GO | 공식 FAQ가 과거 미적재·미제공 명시 |
| Operating cost | GO | 약 24.48MB/day, 기존 로컬 실행비 거의 0 |
| Automation | GO | sample 무인 호출, retry/dedupe/gap/health 구현 |
| Economic state | GO | 카드소비·상권·교통·인구·행사 연결 |
| Product/business | NOT EVALUATED | Seed 적립과 분리. 파생상품 미구현 |

## 다음 확장 후보

1. 공영홈쇼핑 실시간 인기검색어 + 편성·판매가·할인 이벤트를 상품ID/시간으로 결합하는 소형 collector
2. NIA watcher의 나라장터 RFP/발주계획 adapter
3. 8~12주 서울 coverage 후 event annotation coverage와 missing rate 검토
4. 그 뒤에만 동일 요일/시간 baseline, percentile, abnormality feature 계산

전체 82곳 확대나 Event Economic Impact/Seoul Now BUILD는 현재 하지 않는다.
