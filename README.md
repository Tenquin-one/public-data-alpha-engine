# Public Data Alpha Engine

Opportunity Foundry v0.3의 CORE 모듈과 PRIORITY SEED 수집기를 SQLite·GitHub Actions 운영 구조로 구현한 MVP다. 질문은 하나다.

> 지금 저장하지 않으면 나중에 복원할 수 없는 경제적 상태는 무엇인가?

이 프로젝트는 전체 공공데이터를 아카이빙하지 않는다. 현재·예정 데이터의 **메타데이터 변화**, 공개 전 조달 신호, v0.3 점수, 75점 이상 Seed 후보만 관리한다. 실제 snapshot collector는 서울 실시간 도시·상권 데이터 8곳과 `Airport Friction Seed v0.1`의 국내 5개 공항을 수집한다. 기존 `prelaunch_signal_graph`는 변경하지 않았고 이 프로젝트의 실행 경로에도 포함하지 않았다.

## 현재 결과

- SQLite DB: `data/alpha_engine.sqlite`
- 초기 dataset 6개, NIA pre-release signal 4개
- 서울 실시간 도시데이터 Seed 96.0, 상권 전용 데이터 Seed 91.8
- 서울 sample 실호출 1건 성공: 광화문·덕수궁, 8개 기대 섹션 전부 확인
- GitHub Actions 15분 collector: `main`의 코드와 `data` 브랜치의 immutable run bundle 분리
- Airport Friction Seed v0.1: 김포·제주·김해·청주·대구의 KAC 시계열 6종(소요시간·혼잡도·운항정보·운항스케줄·주차정보·주차혼잡도) + KMA METAR/공항특보. 김포 실내 주차면은 향후 앱의 on-demand 소스로만 예약
- Airport offline fixture: 22개 source response, 5개 공항 normalized record, dedupe/partial-failure/manifest까지 검증
- gzip 원문 실측 31,875 bytes/snapshot
- 테스트 13개: diff, 예정→공개, rights kill gate, override 분리, NIA parsing/linking, JSON/XML, 중복, fallback, source timestamp, gap, export, cloud bundle
- SQLite `integrity_check=ok`, 외래키 오류 0

세부 판정은 [initial scan](reports/initial_scan.md)에 있다.

## 구조

```text
Registry Mirror ──┐
Planned Registry ─┼─> Metadata Diff ─> PRA / Ephemeral / Seed ─> Seed Queue
NIA Pre-Release ──┘                                      │
                                                         └─> Collector Registry
                                                               │
                                                     ├─ Seoul 8-place snapshots
                                                     └─ Airport Friction 5-airport snapshots
```

- Registry Mirror: ODCloud 목록조회 API, 현재/예정 CSV의 공통 정규화
- Diff Engine: 신규, 수정일, 상태, API/File, 갱신주기, 라이선스, 기관 변화와 예정→공개 기록
- Pre-Release Watcher: NIA 입찰공고/사전규격 제목·기관·일자·URL만 저장하고 dataset과 token/entity 연결
- Judge: PRA, Ephemeral Score, Data Accumulation Gate를 규칙으로 계산. 자동값과 HUMAN/AI override를 별도 보존
- Seed Queue: Seed 75 이상 + rights PASS + cost PASS만 `COLLECT_NOW`
- Collector Factory interface: source, endpoint, cadence, entity key, snapshot 전략, 저장량, 법적 메모, auth env 등록
- Asset Layer: raw payload의 SHA-256, gzip 경로, source/query timestamp, 정규화 snapshot, health/gap log

## 빠른 실행

Python 3.11 이상과 표준 라이브러리만 필요하다.

```bash
cd public_data_alpha_engine
export PYTHONPATH="$PWD/src"

python3 -m public_data_alpha_engine.cli bootstrap
python3 -m public_data_alpha_engine.cli status
python3 -m public_data_alpha_engine.cli export
python3 -m unittest discover -s tests -v
python3 -m public_data_alpha_engine.cli check
```

Airport Friction은 키 없이도 명시적인 offline fixture로 전체 저장 파이프라인을 검증할 수 있다.

```bash
python3 -m public_data_alpha_engine.cli airport-quota
python3 -m public_data_alpha_engine.cli collect-airport \
  --output /tmp/airport-friction-fixture \
  --fixture --force-weather --trigger-source fixture_smoke
```

공식 sample 키로 광화문·덕수궁 한 곳을 시험한다.

```bash
python3 -m public_data_alpha_engine.cli collect-seoul --sample
```

8곳을 실제 운영하려면 서울 열린데이터광장 키를 환경변수로 넣는다. 로컬 CLI는 프로젝트 루트의 `.env`도 자동으로 읽으며, 이미 설정된 shell/GitHub Actions 환경변수를 덮어쓰지 않는다. 별도 `python-dotenv` 의존성은 없다. 키는 URL·DB·로그에서 `REDACTED` 처리된다.

```bash
# .env를 편집해 SEOUL_OPEN_DATA_KEY를 넣은 뒤 실행
python3 -m public_data_alpha_engine.cli collect-seoul
```

`.env`는 `.gitignore`에 포함되어 있으며 Git에 커밋하지 않는다. 채팅이나 로그에 노출된 키는 폐기하고 새 키로 교체한다.

공공데이터포털 전체 목록은 활용신청 키를 사용한다. 공식 테스트 키는 조건 없는 10건만 반환한다.

```bash
export DATA_GO_KR_SERVICE_KEY="발급받은_키"
python3 -m public_data_alpha_engine.cli mirror-odcloud
python3 -m public_data_alpha_engine.cli watch-nia
```

공공데이터포털에서 내려받은 현재 목록 또는 범정부 개방예정 CSV도 같은 mirror로 읽을 수 있다.

```bash
python3 -m public_data_alpha_engine.cli mirror-csv current.csv
python3 -m public_data_alpha_engine.cli mirror-csv planned.csv --planned
```

Airport Friction의 실제 운영 준비는 [전용 runbook](docs/airport_friction_runbook.md), 공식 API 검증은 [source audit](docs/airport_friction_sources.md), 보존 필드는 [normalized schema](docs/airport_friction_schema.md)에 정리했다. 공통 운영 절차와 장애 복구는 [runbook](docs/runbook.md), 계산 규칙은 [scoring spec](docs/scoring_spec.md), 전체 테이블은 [data dictionary](docs/data_dictionary.md)를 참고한다.
초기 후보·점수·Seed Queue·서울 cohort의 CSV는 `data/exports/`에 생성된다.

GitHub 운영에서는 `.github/workflows/collect-seoul.yml`이 매시 07·22·37·52분 실행을 요청한다. GitHub 예약 실행은 지연되거나 드물게 누락될 수 있으며, 다음 성공 run이 2.5 cadence를 넘긴 공백과 추정 누락 횟수를 manifest에 기록한다. Repository secret `SEOUL_OPEN_DATA_KEY`가 없으면 공식 sample 지역 1곳, 있으면 seed 8곳을 수집한다. 원문은 매번 커지는 SQLite 대신 재구성 가능한 tar+gzip bundle로 `data` 브랜치에 적립한다. 설정과 object-storage 이관 gate는 [GitHub operations](docs/github_operations.md)에 있다.

Airport Friction workflow는 `workflow_dispatch`만 제공하며 검증된 외부 scheduler가 15분마다 호출한다. 중복 API 호출을 피하기 위해 GitHub 내부 `schedule`은 2026-08-29에 제거했다. Airport 데이터는 `bundles/airport_friction/`, `runs/airport_friction/`, `state/airport_friction/`에만 기록되어 기존 서울 자산과 충돌하지 않는다.

## 공식 근거

- [공공데이터포털 목록조회서비스](https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15077093)
- [범정부 미제공(개방예정데이터) 목록](https://www.data.go.kr/data/15127106/fileData.do)
- [NIA 입찰공고·사전규격](https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=78336)
- [서울 실시간 도시데이터](https://data.seoul.go.kr/dataList/OA-21285/F/1/datasetView.do)
- [서울 실시간 상권현황데이터](https://data.seoul.go.kr/dataList/OA-22385/F/1/datasetView.do)
- [서울 실시간 도시데이터 매뉴얼 v8.5](https://data.seoul.go.kr/SeoulRtd/downloads/%EC%8B%A4%EC%8B%9C%EA%B0%84_%EB%8F%84%EC%8B%9C%EB%8D%B0%EC%9D%B4%ED%84%B0_%EB%A7%A4%EB%89%B4%EC%96%BC.pdf)
- [한국공항공사 공항 소요시간 정보 GW](https://www.data.go.kr/data/15158950/openapi.do)
- [한국공항공사 공항 혼잡도 정보 GW](https://www.data.go.kr/data/15159598/openapi.do)
- [한국공항공사 전국공항 실시간 주차정보 GW](https://www.data.go.kr/data/15158681/openapi.do)
- [한국공항공사 전국공항 주차장 혼잡도 GW](https://www.data.go.kr/data/15158689/openapi.do)
- [한국공항공사 김포공항 실내주차장 빈 주차면 GW](https://www.data.go.kr/data/15158508/openapi.do)
- [한국공항공사 실시간 운항정보 GW](https://www.data.go.kr/data/15158625/openapi.do)
- [한국공항공사 항공기 운항 스케줄 정보 GW](https://www.data.go.kr/data/15158949/openapi.do)
- [기상청 API허브 국내항공 METAR/SPECI](https://apihub.kma.go.kr/apiList.do?seqApi=14)

## 범위 밖

Event Economic Impact, Pop-up Site Intelligence, Seoul Now 같은 상품은 만들지 않았다. `event_annotations`와 `snapshot_features`만 비어 있는 확장 공간으로 두었다. 상품성은 Seed 적립 판정과 별도다.
