# Runbook

## 1. 최초 설정

```bash
cd public_data_alpha_engine
export PYTHONPATH="$PWD/src"
python3 -m public_data_alpha_engine.cli bootstrap
python3 -m unittest discover -s tests -v
python3 -m public_data_alpha_engine.cli check
```

`bootstrap`은 idempotent다. 공식 근거로 검토한 초기 registry, signal, HUMAN override, collector/place registry를 넣고 재점수한다.

## 2. 자격정보

- `SEOUL_OPEN_DATA_KEY`: 서울 열린데이터광장 실시간 도시데이터 키
- `DATA_GO_KR_SERVICE_KEY`: 공공데이터포털 목록조회 및 활용신청한 KAC GW API 키
- `KMA_API_HUB_KEY`: 기상청 API허브 국내항공 METAR/SPECI·공항특보 키

키는 설정파일이나 DB에 넣지 않는다. 서울 key는 실제 요청 URL에 필요하지만 저장 endpoint에서는 `REDACTED`로 바꾼다.

로컬 CLI는 프로젝트 루트 `.env`에서 위 세 이름만 자동으로 읽는다. shell에 이미 존재하는 환경변수가 우선하며, `.env`는 `.gitignore`에 포함되어 있다. GitHub Actions는 repository secret을 환경변수로 주입하므로 이 로컬 편의 기능의 영향을 받지 않는다.

## 3. Schedule

### 매일 1회 CORE

```bash
scripts/run_core_daily.sh
```

현재 목록은 실제로 자주 바뀌어도 메타데이터 발견 목적에는 하루 1회면 충분하다. 개방예정 목록은 공식 갱신이 연간이므로 새 CSV가 발행됐을 때 또는 주 1회 확인만 한다. NIA는 하루 1회다.

### 15분마다 서울

```bash
scripts/run_seoul_15min.sh
```

cron 예시:

```text
*/15 * * * * /absolute/path/public_data_alpha_engine/scripts/run_seoul_15min.sh
15 3 * * * /absolute/path/public_data_alpha_engine/scripts/run_core_daily.sh
```

15분 주기는 8곳×96=768 calls/day다. 서울 공식 매뉴얼상 실시간 인구의 기준 시각은 5분 단위지만 보정 후 사용자 제공까지 약 15분이 걸린다. 따라서 15분 polling은 새 정보의 제공 지연과 균형이 맞고, 10분 polling은 1,152 calls/day와 중복 manifest를 늘리는 데 비해 시간 우위가 제한적이다. 30분은 유효 시점 일부를 놓쳐 Data Time Advantage를 약화하므로 v1은 15분을 유지한다.

GitHub `schedule`은 정확한 cron 서비스가 아니라 best-effort다. 지연 또는 누락될 수 있으므로 cloud manifest의 `health.schedule`은 직전 run 이후 2.5 cadence(37분 30초)를 넘으면 `WARNING`과 추정 `missed_intervals`를 기록한다. 워크플로 자체가 실행되지 않는 동안에는 기록할 수 없고 다음 실행에서 사후 감지한다.

### 15분마다 Airport Friction

```bash
scripts/run_airport_friction.sh /absolute/path/to/data-branch-checkout
```

KAC는 15분, KMA METAR/특보는 30분 간격이다. `workflow_dispatch` 외부 호출과 임시 GitHub backup schedule, 필요한 두 secret, quota와 복구 절차는 [Airport Friction runbook](airport_friction_runbook.md)에 있다.

## 4. 상태 확인

```bash
python3 -m public_data_alpha_engine.cli status
python3 -m public_data_alpha_engine.cli health
python3 -m public_data_alpha_engine.cli check
```

`health`는 마지막 성공 관측(raw payload, 중복 포함)이 cadence의 2.5배보다 오래된 장소를 gap으로 기록한다. 같은 unresolved gap을 반복 생성하지 않으며 새 관측이 들어오면 해결 시각을 남긴다. `status`는 Seed Queue와 PRA 순위를 보여준다.

## 5. 실패 처리

### 인증키 없음/권한 오류

- 서울: `SEOUL_OPEN_DATA_KEY`와 해당 API 이용신청 상태 확인
- sample 키: `collect-seoul --sample`만 사용. 다른 7곳은 sample로 호출하지 않는다.
- 공공데이터포털: 목록조회 API 활용신청 키를 사용. 테스트 키는 10건 제한
- Airport Friction: KAC 7개 GW API가 모두 사용 가능 상태인지와 `DATA_GO_KR_SERVICE_KEY` 확인
- 기상청 항공기상: API허브 활용신청과 `KMA_API_HUB_KEY` 확인. 폐기된 임시 test key 대신 offline fixture 사용

### TLS certificate 오류

이 로컬 실행환경의 첫 ODCloud/NIA smoke test는 Python이 CA bundle을 찾지 못해 실패했다. client는 `/etc/ssl/cert.pem`이 있으면 명시적으로 사용하도록 수정했다. 다른 환경에서는 다음을 확인한다.

```bash
python3 -c "import ssl; print(ssl.get_default_verify_paths())"
```

검증을 끄는 insecure TLS fallback은 구현하지 않았다. 조직 proxy의 루트 인증서가 필요하면 시스템 trust store 또는 표준 CA bundle에 설치한다.

### JSON schema 변화

collector는 JSON 실패 시 XML을 재시도한다. 둘 다 실패하면 run은 `PARTIAL/FAILED`이고 원문 오류는 run/health에 남는다. `missing_sections_json`이 늘면 API 명세 변경을 먼저 확인한다.

### 중복 급증

연속 중복은 정상일 수 있다. 1시간 이상 모든 장소가 같은 hash면 upstream stale 가능성을 검토한다. 중복은 raw file과 snapshot을 추가하지 않지만 payload 관측 row는 보존한다.

### 저장량 초과

순서대로 조정한다.

1. 15분→30분 cadence
2. 8곳→5곳 cohort
3. 통합 API 대신 상권/인구 전용 API로 payload 축소
4. raw retention을 바꾸기 전 hash·normalized snapshot·provenance 보존 요구 재검토

## 6. Rights kill switch

서울 데이터의 이용허락이 공공누리 1유형에서 변경되거나 저장/재이용 제한이 명시되면:

1. collector `enabled=0`
2. 새 raw snapshot 중단
3. registry metadata와 변경 이벤트만 유지
4. 기존 raw의 보존·삭제는 새 조건과 법률 검토 후 별도 결정

점수 override로 rights FAIL을 우회하지 않는다.

## 7. 확장

- 공영홈쇼핑 검색어/매출순위와 편성/가격 이벤트는 다음 Collector 검토 후보다.
- 나라장터는 NIA와 같은 `PreReleaseSignal` envelope로 구현한다.
- feature/상품은 최소 8~12주 coverage와 event annotation 품질을 확인한 뒤 별도 Probe로 연다.
