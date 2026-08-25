# Data Dictionary

SQLite는 UTC ISO-8601 text timestamp를 사용한다. 서울 source timestamp는 `+09:00` offset을 포함한다. JSON 필드는 canonical JSON text다.

## Source와 run

### `sources`

수집원 registry. `source_type`, `base_url`, 권리 상태, 적정 cadence, terms memo, 활성 여부를 저장한다.

### `collection_runs`

한 번의 mirror/watcher/collector 실행. 시작·종료, 성공상태, 요청/수신/삽입/중복/오류 수, 오류문과 health JSON을 저장한다.

### `raw_payloads`

모든 관측의 provenance. `collected_at`, redacted `source_url`, query params, source timestamp, SHA-256, gzip path, 저장 byte, MIME, duplicate 여부와 이전 payload를 저장한다. 동일 content hash는 새 파일을 만들지 않아도 관측 row는 남긴다.

## Registry와 diff

### `datasets`

정규화 registry mirror.

- identity: `dataset_id`, `external_id`, `source_id`
- display: `title`, `description`, `provider`, `category`, keywords
- lifecycle: `public_status`, `expected_release_year`, 등록/수정/최초·마지막 관측시각
- access: API/File 여부, format, cadence, source URL
- governance: license, terms, cost/rights/history status
- reproducibility: `current_hash`, `raw_payload_id`, 원래 필드를 담은 `metadata_json`

### `dataset_events`

dataset별 field diff. event type, field, old/new value, observed run/raw payload를 가진다.

## Pre-release

### `pre_release_signals`

NIA/RFP/발주계획의 공통 envelope. 공고 ID, 제목, 발주기관, 게시일, 공고유형, URL, keyword/entity, hash, raw payload, 원래 metadata를 저장한다.

### `signal_dataset_links`

signal↔current/planned dataset 연결 후보. confidence 0~1, method, matched term, review status를 저장한다.

## Judge와 queue

### `score_overrides`

자동값과 분리된 HUMAN/AI 평가. 기존 active override는 비활성화해 이력을 보존한다.

### `scoring_dimensions`

candidate×score kind×dimension 한 행. weight, auto/override/effective rating, points, rationale, evidence, 계산시각을 저장한다.

### `alpha_scores`

candidate별 PRA/Seed/Ephemeral 총점, rights/cost/accumulation gate, review status, recommendation, calculation version.

### `seed_queue`

dataset별 Seed 판정. `COLLECT_NOW`, `REVIEW_RIGHTS_COST`, `METADATA_ONLY`, `HOLD` 중 하나와 gate reason, 연결 collector를 가진다.

## Collector Factory interface

### `collector_registry`

실행 가능한 collector 계약.

- code: `module`, `collector_id`, `name`
- source: `source_id`, `dataset_id`, endpoint template, auth env
- schedule: cron/cadence
- identity: entity key
- asset: snapshot strategy, bytes/day estimate
- governance: legal memo, terms checked date
- runtime: enabled, config JSON

### `place_registry`

서울 seed cohort. area name/code, cohort tag, commercial 지원 여부, 선정 근거, source URL.

## Snapshot와 future feature

### `snapshots`

collector/entity별 당시 상태. source/collection time, endpoint/query, payload hash/raw path, normalized JSON, 누락 section, quality status. 직전 hash가 같으면 새 snapshot을 만들지 않는다.

### `snapshot_features`

향후 baseline/percentile/abnormality를 위한 versioned sparse feature. MVP에서는 비어 있다.

### `event_annotations`

향후 행사·집회·날씨·프로모션 구간 annotation. entity, start/end, type/title/source, confidence, review status. MVP에서는 상품 feature를 계산하지 않는다.

## Health

### `collector_health_logs`

run별 latency, HTTP status, retry, 기대/성공 entity, 새 snapshot/중복/누락 수와 메시지.

### `data_gap_events`

cadence 2.5배 안에 snapshot이 없을 때 생성. entity, expected/detected time, severity, reason, resolved time을 저장한다.
