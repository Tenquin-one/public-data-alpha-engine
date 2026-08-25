# GitHub Operations

## 역할 분리

- `main`: 코드, schema, seed metadata, tests, 문서, GitHub Actions
- `data`: 재구성 가능한 서울 원문 run bundle, run manifest, 장소별 latest hash state
- 로컬 `data/alpha_engine.sqlite`: 분석·개발용 SQLite. 매 실행마다 Git에 커밋하지 않는다.

SQLite를 15분마다 커밋하면 DB 전체의 binary history가 누적된다. GitHub 운영판은 매 run의 새 원문만 gzip으로 넣은 tar bundle과 provenance manifest를 `data` 브랜치에 추가한다. SQLite는 bundle에서 다시 만들 수 있는 derived index로 취급한다.

## 자동화

`.github/workflows/collect-seoul.yml`은 UTC 매시 07·22·37·52분, 즉 15분 간격으로 실행한다. GitHub가 매시 정각에 혼잡할 수 있어 정각을 피했다.

Repository secret `SEOUL_OPEN_DATA_KEY`가 있으면 8개 seed 장소를 수집한다. 없으면 workflow가 중단되지 않고 공식 `sample` 키로 광화문·덕수궁 한 곳만 수집하며 Actions summary에 경고를 남긴다. Secret 값은 저장하거나 로그에 출력하지 않고 endpoint에는 `REDACTED`만 남긴다.

## Data branch layout

```text
bundles/YYYY/MM/DD/<run-id>.tar
  manifest.json
  payloads/<area>-<sha256>.json.gz
runs/YYYY/MM/DD/<run-id>.json
state/latest_hashes.json
```

각 run manifest에는 수집시각, source timestamp, 장소, redacted endpoint/query, SHA-256, 원문·gzip byte, HTTP/retry/latency, missing section과 상태가 있다. 이전 hash와 같으면 새 raw payload를 bundle에 넣지 않지만 run manifest는 보존한다.

## 반드시 필요한 운영 설정

1. 서울 열린데이터광장에서 운영 인증키 발급
2. GitHub repository `Settings → Secrets and variables → Actions`에 `SEOUL_OPEN_DATA_KEY` 등록
3. Actions의 첫 수동 실행이 `SEED_COHORT`, 8/8 success인지 확인
4. `data` 브랜치의 bundle과 manifest 생성 확인

서울 공식 OpenAPI endpoint가 HTTP를 사용하므로 인증키는 URL path에 들어간다. workflow와 Python client는 URL을 로그에 출력하지 않지만 전송계층 자체는 서울 공식 endpoint 조건을 따른다.

## 저장소 한계와 이관 gate

8곳 실측 기준 약 24.48MB/day, 0.734GB/30일이다. Git은 장기 object storage가 아니므로 다음 중 하나가 먼저 발생하면 S3-compatible object storage로 bundle target을 이관한다.

- 누적 bundle 500MB
- `data` checkout/commit 2분 초과
- 파일/commit 수 때문에 workflow failure 또는 지연 증가
- 최초 30일 운영 완료

이관 후 `data` 브랜치에는 manifest와 object URI/hash만 남긴다. GitHub Actions 자체는 orchestrator로 유지한다.

