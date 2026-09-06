# GitHub Operations

## 역할 분리

- `main`: 코드, schema, seed metadata, tests, 문서, GitHub Actions
- `data`: 재구성 가능한 서울·Airport Friction 원문 run bundle, run manifest, latest hash state
- 로컬 `data/alpha_engine.sqlite`: 분석·개발용 SQLite. 매 실행마다 Git에 커밋하지 않는다.

SQLite를 15분마다 커밋하면 DB 전체의 binary history가 누적된다. GitHub 운영판은 매 run의 새 원문만 gzip으로 넣은 tar bundle과 provenance manifest를 `data` 브랜치에 추가한다. SQLite는 bundle에서 다시 만들 수 있는 derived index로 취급한다.

## 자동화

`.github/workflows/collect-seoul.yml`은 검증된 외부 scheduler가 15분마다 `workflow_dispatch`로 호출한다. 기존 GitHub 내부 `schedule`은 외부 dispatch와 함께 실행되어 과수집을 만들었기 때문에 2026-09-03에 제거했다. 다음 실행은 직전 run과의 간격이 37분 30초를 넘으면 manifest `health.schedule`에 `WARNING`, 지연 초, 추정 누락 횟수를 기록한다.

Repository secret `SEOUL_OPEN_DATA_KEY`가 있으면 8개 seed 장소를 수집한다. 없으면 workflow가 중단되지 않고 공식 `sample` 키로 광화문·덕수궁 한 곳만 수집하며 Actions summary에 경고를 남긴다. Secret 값은 저장하거나 로그에 출력하지 않고 endpoint에는 `REDACTED`만 남긴다.

`.github/workflows/collect-airport-friction.yml`은 검증된 외부 scheduler용 `workflow_dispatch`만 제공한다. 중복 API 호출을 만들던 GitHub 내부 backup schedule은 2026-08-29에 제거했다. Airport live mode는 `DATA_GO_KR_SERVICE_KEY`와 `KMA_API_HUB_KEY`가 모두 필요하며, key가 없으면 fixture로 대체하지 않고 실패 manifest를 남긴다. Fixture는 수동 `mode=fixture`에서만 가능하다.

Airport와 Seoul은 서로 다른 workflow concurrency group을 사용한다. GitHub는 같은 group에 실행이 몰리면 기존 pending run을 교체할 수 있으므로, 공유 group은 Airport 15분 run을 누락시킬 수 있다. 두 workflow가 동시에 `data`를 갱신할 때의 충돌은 `scripts/push_data_branch.sh`가 최신 branch 위로 rebase한 뒤 최대 4회 재시도한다.

서울과 Airport workflow는 서로 다른 namespace를 쓰지만 하나의 `data` 브랜치에 append한다. 따라서 둘 다 `public-data-time-axis-writer` concurrency group을 공유해 저장을 직렬화한다. 드물게 다른 writer가 중간에 branch를 갱신해도 push helper가 최신 `origin/data` 위로 수집 commit을 rebase하고 최대 4회 재시도한다. 이 때문에 정상 수집 manifest가 단순 push race로 유실되지 않는다.

## 최근 운영 판정 (2026-09-06)

- Seoul 최근 24시간 97회는 모두 외부 `workflow_dispatch`와 `cdbe912`로 실행됐다. 성공 94회와 `data` manifest 94개가 1:1로 대응하며 모두 `SEED_COHORT` 8/8, `errors=0`, `missing_sections=0`이고 latest-hash pointer와 bundle도 정상이다.
- 수집 단계가 workflow의 10분 상한에 걸려 3회 취소됐고, 그 결과 약 30분의 manifest 간격이 3번 생겼다. 37분 30초 초과 공백은 없었다. 8개 지역을 순차 호출하는 현재 기본값(`timeout=25`, `max_retries=2`)은 상류 지연이 겹치면 hard timeout 전에 manifest를 남기지 못할 수 있다. 재정비 시 최소 변경 후보는 Seoul HTTP budget을 `timeout=8`, `max_retries=1`로 제한하는 것이다.
- Airport 최신 run은 scheduler와 workflow가 정상(`schedule=OK`, `workflow.failure=false`)이지만 provider 응답 노후화로 manifest가 `FAILED`이고 unresolved stale source gap이 16개다. provider `PARTIAL`/`FAILED`는 현재 정책대로 collector 장애로 보지 않는다.

데이터 프로젝트는 수집을 그대로 유지하는 maintenance-only 상태다. 별도 반복 검증 작업은 두지 않으며, 제품 개발 자원은 REALWORLD WEIRDO 세계관·challenge/game launch 준비에 집중한다.

## Data branch layout

```text
bundles/YYYY/MM/DD/<run-id>.tar
  manifest.json
  payloads/<area>-<sha256>.json.gz
runs/YYYY/MM/DD/<run-id>.json
state/latest_hashes.json

bundles/airport_friction/YYYY/MM/DD/<run-id>.tar
  manifest.json
  payloads/<source>-<sha256>.json.gz
runs/airport_friction/YYYY/MM/DD/<run-id>.json
state/airport_friction/latest_hashes.json
```

각 run manifest에는 수집시각, source timestamp, 장소, redacted endpoint/query, SHA-256, 원문·gzip byte, HTTP/retry/latency, missing section, schedule health와 상태가 있다. 이전 hash와 같으면 새 raw payload를 bundle에 넣지 않지만 run manifest는 보존한다.

Airport namespace는 기존 서울 경로를 변경하지 않는다. 각 run에는 5개 공항 normalized records와 quota proof, source별 gap, trigger provenance도 함께 남는다.

## 반드시 필요한 운영 설정

1. 서울 열린데이터광장에서 운영 인증키 발급
2. GitHub repository `Settings → Secrets and variables → Actions`에 `SEOUL_OPEN_DATA_KEY` 등록
3. Actions의 첫 수동 실행이 `SEED_COHORT`, 8/8 success인지 확인
4. `data` 브랜치의 bundle과 manifest 생성 확인

Airport Friction은 별도로 [전용 runbook](airport_friction_runbook.md)의 KAC 7개 사용 가능 상태 확인, KMA API허브 키, repository secret 2개 등록만 수행한다.

저장소 공개 설정은 15분마다 실행되는 standard GitHub-hosted runner 비용을 피하기 위한 MVP 선택이다. 30일 기준 예약 job은 최대 2,880회다. 각 job이 1분 미만이어도 유료 계산에서는 job별 올림 때문에 최대 2,880분으로 본다. 현재처럼 public repository + standard Linux runner이면 Actions 시간 비용은 $0다. 비공개 GitHub Free로 전환하면 2,000분 포함량을 약 880분 초과하며, 2026-08 기준 Linux $0.006/분이면 약 $5.28/월이다. 이 workflow는 Actions artifact/cache를 만들지 않으며 `data` 브랜치 저장량은 Actions artifact 과금과 별개다.

서울 공식 OpenAPI endpoint가 HTTP를 사용하므로 인증키는 URL path에 들어간다. workflow와 Python client는 URL을 로그에 출력하지 않지만 전송계층 자체는 서울 공식 endpoint 조건을 따른다.

## 저장소 한계와 이관 gate

sample 1곳의 최근 실측 gzip 32,452 bytes 기준 raw는 약 3.12MB/day, 0.093GB/30일이며 manifest/Git overhead를 포함해 약 0.10~0.12GB/월로 본다. 8곳은 기존 실측 평균 31,875 bytes/장소 기준 약 24.48MB/day, 0.734GB/30일이고 overhead 포함 약 0.75~0.85GB/월로 예상한다. Git은 장기 object storage가 아니므로 다음 중 하나가 먼저 발생하면 S3-compatible object storage로 bundle target을 이관한다.

- 누적 bundle 500MB
- `data` checkout/commit 2분 초과
- 파일/commit 수 때문에 workflow failure 또는 지연 증가
- 최초 30일 운영 완료

이관 후 `data` 브랜치에는 manifest와 object URI/hash만 남긴다. GitHub Actions 자체는 orchestrator로 유지한다.
