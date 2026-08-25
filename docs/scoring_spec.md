# Scoring Specification

모든 차원 rating은 0~10이고, 총점은 `Σ(rating × weight / 10)`이다. 계산 버전은 `foundry-v0.3-rules-1`이다.

## PRA

| Dimension | Weight | 10점 의미 |
|---|---:|---|
| existing_payment_evidence | 20 | 현재 이 정보/업무에 실제 지출이 명확 |
| cost_substitution | 15 | 유료데이터·수작업·스크래핑을 크게 대체 |
| join_amplification | 15 | 다른 데이터와 결합해 원자료에 없는 신호 생성 |
| release_probability | 10 | 예산·발주 또는 실제 공개까지 확인 |
| lead_time | 10 | 공개 전 수개월 준비우위 |
| data_time | 10 | 오늘 상태를 나중에 복원하기 어려움 |
| distribution_payer | 10 | 구매자와 도달·결제 경로가 명확 |
| machine_processability | 5 | API/정형파일/안정 ID |
| non_obviousness | 5 | 동일 상품·활용이 널리 포화되지 않음 |

공개 dataset은 release probability가 높지만 lead time은 낮다. 사전규격 signal은 반대로 lead time이 높고 schema·권리·기계가공은 보수적으로 낮게 둔다.

## Data Accumulation / Seed Score

| Dimension | Weight | 10점 의미 |
|---|---:|---|
| past_reconstruction_impossibility | 25 | 원소스에서 과거 snapshot 재생성 불가 |
| direct_money_link | 20 | 가격·구매·거래·계약과 직접 연결 |
| multi_source_join_value | 15 | A+B+C 결합으로 새 상태 생성 |
| automated_collection | 15 | 사람 없이 안정적으로 지속 수집 |
| update_frequency | 10 | 일·주 또는 그보다 빠른 사건 반복 |
| ground_truth_possible | 10 | 이후 실제 결과로 라벨링 가능 |
| storage_operations_cost | 5 | 소형 로컬/오브젝트 스토리지 수준 |

## Ephemeral Score

v0.3의 Data Time 질문을 빠르게 정렬하기 위한 구현 점수다. Foundry 원문의 별도 가중치가 아니므로 version을 분리했다.

| Dimension | Weight | 의미 |
|---|---:|---|
| overwrite_risk | 30 | 빠른 갱신과 history 부재의 결합 |
| historical_absence | 25 | 공식 replay/history 부재 |
| refresh_velocity | 15 | 분·일·주 단위 상태변화 |
| economic_state | 20 | 소비·가격·거래·재고 등 돈과 연결 |
| machine_capture | 10 | API/file로 무인 capture 가능 |

## 자동 규칙

- cadence: 실시간/분=10, 일/수시=8, 주=6, 월=4, 연/1회=1
- history: `NONE/NOT_PROVIDED`=10, `LIMITED`=7, `AVAILABLE`=1, unknown은 cadence로 보수 추정
- machine: API=10, file=7, 둘 다 없음=2
- money/JOIN/outcome: 제목·설명·키워드에서 제한된 사전의 distinct term 수로 계산
- storage: 명시 추정치 <10MB/day=10, <100MB/day=8, 그 이상=4
- popularity: 활용신청 수가 많을수록 non-obviousness 하향

이 규칙은 screening이다. Wallet Proof나 구매자 검증을 대체하지 않는다.

## Override 계약

`score_overrides`에는 다음을 필수 저장한다.

- candidate type/id와 score kind/dimension
- 0~10 rating
- `HUMAN` 또는 `AI`
- source name, rationale, timestamp, active flag

동일 차원의 최신 active override만 effective rating으로 사용한다. `scoring_dimensions.auto_rating`은 보존된다. 초기 서울 override는 공식 문서 검토를 근거로 한 HUMAN 값이다.

## Gate

```text
if rights == RESTRICTED: METADATA_ONLY
else if seed >= 75 and rights == ALLOW and cost in {FREE, NEAR_ZERO}: COLLECT_NOW
else if seed >= 75 and rights/cost unknown: REVIEW_RIGHTS_COST
else: HOLD
```

PRA는 연구 우선순위이며 BUILD 판정이 아니다. Seed의 `COLLECT_NOW`도 데이터 적립 허용일 뿐 상품 BUILD가 아니다.
