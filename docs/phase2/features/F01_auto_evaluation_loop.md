# F01 — Auto Evaluation Loop

| 항목 | 값 |
|---|---|
| Feature ID | F01 |
| Phase | 2 |
| Priority | **P0** (Axis B Closed-Loop Quality 핵심 — F02·F03·F04의 진입 토대) |
| Owner | 김정원 |
| 작성일 | 2026-05-08 |
| 상태 | Draft v1 |
| Estimated effort | 1주 (PRD §9 W4 마일스톤) |
| 부모 문서 | `docs/phase2/PRD.md` §3 Axis B, §5 Feature Index, §9 W4 |
| Dependencies | F05 (`prompt_version_id` 발행), **W1 closed**, **W2 closed** |
| Closes (Phase 1 deferred) | (해당 없음 — W1·W2는 본 spec 작성 직전 PR에서 closing 완료) |

---

## 1. Problem

### 1.1 사용자 식별 이슈

> "평가 결과를 보고 prompt를 사람이 직접 고쳐서 다시 돌려야 한다. 한 Style 만드는 데 24시간이 걸리는 가장 큰 이유" — Pilot user, 2026-05 (이슈 1, PRD §1.2)

### 1.2 현재 코드 증거

Phase 1 종료 시점에 evaluator(`services/evaluation_service.py`)가 `retry_guidance` / `failed_dimensions`를 산출하지만, 이 값을 운영 path에서 자동 적용하는 경로가 끊겨 있었다.

- `backend/src/style_workbench/services/run_service.py:execute()` — eval+retry 루프 골격(L151–205)은 이미 존재. `engine/retry.py`의 `RetryPolicy` / `RetryState`도 마련되어 있음.
- 그러나 직전까지 **W1**(`cost_budget_won` 가드가 `execute()` 경로에 미적용)과 **W2**(`api/deps.py:get_run_service()` 가 `eval_service=None` 주입)가 미해결 상태로 둘 다 F01 진입 차단(PRD §11).
- **W1·W2는 본 spec 직전 PR(`Closes W1·W2 — cost_budget_won guard in execute() + eval_service DI wiring`)에서 closing 완료** — `RunService.execute()`는 이제 운영에서 항상 평가 경로를 타고, budget 초과 시 즉시 abort된다.
- 추가로 `retry_guidance`를 evaluation row에 영구 저장하는 schema, retry attempt 단위 추적 테이블, F02 Optimizer와의 인터페이스가 부재 — 이 세 가지가 본 feature의 신규 작업이다.

### 1.3 결과적 한계

| 영향 | 측정 |
|---|---|
| 평가 FAIL 시 사람 개입 빈도 | 100% (모든 retry는 디자이너가 직접 prompt 수정 후 재실행) |
| 1 Style 제작 cycle time | ~24시간 (평가 → 사람 → 재실행 직렬) |
| retry attempt 추적 가능성 | 불가 — 각 시도가 별도 Run으로 기록되어 "같은 노드의 N번째 attempt" 단위 분석 불가 |
| `retry_guidance` 휘발성 | API 응답에만 존재, DB 미저장 — 회귀 분석 불가 |
| F02 Prompt Optimizer 진입 가능성 | **불가** — retry_guidance를 받아 prompt를 수정할 trigger 인터페이스 부재 |

### 1.4 Closed-Loop의 사전 조건

F02 Prompt Optimizer는 "FAIL → retry_guidance → prompt body 수정 → 새 prompt_version → 재실행"의 마지막 단계만 담당한다. 이 체인이 작동하려면 **retry 오케스트레이션**(언제 멈출지, 비용 한도, attempt별 prompt_version 추적)이 먼저 정의돼야 한다. 따라서 F01은 F02·F03·F04에 선행한다.

---

## 2. Goals / Non-Goals

### 2.1 Goals (모두 측정 가능)

| 지표 | Phase 2 목표 | 측정 |
|---|---|---|
| retry attempt 1~3 안에 PASS 비율 | **≥60% on golden suite** (PRD §9 W4 출구 기준 그대로) | `tests/golden/auto_loop/` 회귀 |
| max_retry 초과 시 자동 abort | **100%** | unit + integration |
| `cost_budget_won` 가드 적용률 | **100%** (운영 path) | static check + integration |
| retry 시도별 row 기록 | **100%** | `retry_attempts` row count vs RetryState.attempt 비교 |
| 자동 approved 발생 | **0건** (CLAUDE.md §5 마지막 항목) | E2E + DB constraint |

### 2.2 Non-Goals

- **prompt 본문 LLM 수정** — F02 Prompt Optimizer 영역. F01은 retry_guidance를 emit하고 modifier 인터페이스만 정의한다. F02 부재 시 same `prompt_version_id`로 재실행(no-op modifier).
- **큐 기반 비동기 실행 / 워커 분리** — F03 영역. F01은 동일 프로세스 내 직렬 retry만.
- **batch 회귀 (K개 Test Set 병렬)** — F04 영역.
- **Slack / Email 알림** — F06 영역.
- **사람 verdict 없는 자동 approved** — Phase 3 이전 금지(CLAUDE.md §5). 본 feature는 PASS 시에도 Style.status='reviewing'까지만.
- **per-node 동적 max_retry 정책** — Phase 2 초기는 글로벌 디폴트 3 + per-node override(설정값)까지만. 평가 점수 기반 동적 조정은 Phase 3.
- **`run.status='budget_exceeded'` 별도 enum 분리** — 본 feature 범위에서는 기존 `'failed'`로 분류 유지. F06 observability 시점에 분리 검토(PRD §11 W3와 함께).

---

## 3. User Stories

| ID | 페르소나 | 시나리오 |
|---|---|---|
| **US-1** | 디자이너 | 새 Style 변주 1건을 선택해 Run 시작 → 평가 FAIL 발생 → 자동으로 prompt가 수정되어(F02 연동) 재실행 → 3회 안에 PASS 시 검수 화면(`Style.status='reviewing'`)으로 직행. 1 Style 평균 제작 시간이 24h → 6h로 단축. |
| **US-2** | 시스템 (F01) | 노드별 retry attempt 1~3을 실행하며 매 시도의 `prompt_version_id_used` / `retry_guidance` / `evaluation_id`를 `retry_attempts` 테이블에 기록. attempt 3에서도 FAIL → run.status='failed' + abort + 'run_failed' 이벤트 발행. |
| **US-3** | 시스템 (F02 인터페이스) | F01이 evaluator의 `retry_guidance`를 modifier 인터페이스로 전달 → F02가 prompt body를 수정해 새 `prompt_version`을 생성 후 다음 attempt에서 사용. F02 미도입 단계에서는 same `prompt_version_id`로 재실행(no-op). |
| **US-4** | 운영자 | retry 누적 비용이 `cost_budget_won` 초과 → evaluator 호출 전 즉시 abort + `run_budget_exceeded` SSE 이벤트 발행 → run.status='failed'. 비디오 모델 retry 폭주 차단(PRD §10 Risk 1). |
| **US-5** | 디자이너 | Run detail 화면(`/runs/:run_id`)에서 retry timeline을 본다. 각 attempt 카드에 prompt_version_id, retry_guidance, eval 점수 표시. attempt 간 prompt body diff 토글 가능. |

---

## 4. Functional Requirements (FR)

### FR-1: Retry 정책 — `max_retry` 글로벌 + per-node override

- 글로벌 디폴트 `max_retry=3` (`core/config.py:AUTO_LOOP_MAX_RETRY`).
- per-node override는 DAG node schema에 optional `max_retry: int | null` 필드로 추가(향후, 본 feature에서는 글로벌만 강제).
- attempt counter는 0부터 시작, `attempt > max_retry` 시 abort.

### FR-2: `cost_budget_won` 가드 (W1 closed 의존)

- `RunService.execute()`의 eval+retry 루프에서 매 노드 실행 후 `total_cost_won = total_cost_usd × _USD_TO_WON` 가 `self._budget_won`을 초과하면 evaluator 호출 전 `RunAbortedError` raise.
- 가드는 retry iteration 경계와 무관하게 **최우선 종료 조건**으로 동작 — attempt 2/3 진행 중에도 즉시 abort.
- `_USD_TO_WON = 1_400.0` 상수는 `services/run_service.py:30` 그대로 사용.

### FR-3: PASS 기준 = Evaluator의 `overall_passed`

- `EvaluationService.evaluate(node_execution_id, brief_summary)` 의 반환 객체에 `overall_passed: bool` 필드가 이미 존재(Phase 1 산출).
- F01은 이 boolean 만으로 PASS/FAIL 판단. 차원별 점수는 `failed_dimensions` JSONB로 retry_guidance와 함께 저장(FR-5).

### FR-4: `retry_attempts` 테이블 (신규)

각 attempt를 row로 기록 — Run·Node 단위 분석/회귀의 단위.

- 컬럼: `id`(ULID), `run_id` FK, `node_execution_id` FK, `node_id`(DAG node id 문자열), `attempt_number`(0부터), `prompt_version_id_used` FK nullable(인라인 prompt 노드 호환), `retry_guidance` JSONB nullable(첫 attempt는 NULL), `evaluation_id` FK, `started_at`, `finished_at`, `cost_won` numeric.
- 인덱스: `idx_retry_attempts_run_id`, `idx_retry_attempts_node_execution_id` 모두 `CONCURRENTLY` (W5 컨벤션).

### FR-5: `evaluations.retry_guidance` / `failed_dimensions` JSONB

- `evaluations` 테이블에 `retry_guidance JSONB` (nullable, PASS 시 NULL), `failed_dimensions JSONB NOT NULL DEFAULT '[]'` 추가.
- PRD §9 W4 출구 기준 "retry_guidance가 evaluation에 저장되는 schema 확정"을 본 feature가 만족.
- 기존 evaluation 회귀는 nullable 추가이므로 0건 영향.

### FR-6: Style status='reviewing' 강제 (CLAUDE.md §5 보존)

- F01 Auto Loop가 모든 노드 PASS로 종료 → `runs.status='succeeded'` 까지만 변경. **Style entity의 `status`는 자동 전이 금지**.
- 디자이너의 사람 verdict(`POST /api/evaluations/{evaluation_id}/verdict`) 가 입력될 때만 Style.status='approved' 가능(Phase 1 인터페이스 그대로).
- 서비스 레벨 invariant: `RunService` / `engine/auto_loop.py` 어디에서도 `style_repo.update_status(..., 'approved', ...)` 호출 금지(정적 검증).

### FR-7: `engine/auto_loop.py` 신규 모듈 (오케스트레이터)

- `RunService.execute()` L151–205의 eval+retry 블록을 본 모듈로 추출. `RunService.execute()` 는 트랜잭션 경계와 repo 호출에만 집중.
- 모듈 시그니처(예시):

```python
# engine/auto_loop.py
class AutoLoopOrchestrator:
    def __init__(
        self,
        executor: DagExecutor,
        eval_service: EvaluationService,
        retry_repo: RetryAttemptRepo,
        prompt_modifier: PromptModifier,        # F02 인터페이스 (no-op 구현 default)
        max_retry: int = 3,
        cost_budget_won: float = 100_000.0,
        usd_to_won: float = 1_400.0,
        event_bus: RunEventBus | None = None,
    ) -> None: ...

    async def run(
        self,
        dag: DAG,
        user_input: dict[str, Any],
        run_id: str,
        brief_summary: str = "",
    ) -> AutoLoopResult: ...
```

- `engine/auto_loop.py`는 어떤 외부 SDK(`anthropic` / `openai` / `replicate`)도 import 금지(CLAUDE.md §5.2 — 정적 검증).
- 비용 누적은 attempt 단위 `cost_won`을 `retry_attempts.cost_won`에 기록하고 run 전체 누적은 `runs.total_cost`에 기존 방식 유지(retry로 인한 누적 포함).

### FR-8: F02 인터페이스 정의 — `PromptModifier` Protocol

- F01은 retry_guidance를 emit만 한다. prompt body 수정은 F02. 두 feature를 분리하기 위한 Protocol:

```python
# domain/prompt/modifier.py
class PromptModifier(Protocol):
    async def modify(
        self,
        prompt_version_id: str | None,
        retry_guidance: dict[str, Any],
        failed_dimensions: list[str],
    ) -> tuple[str, str | None]:
        """Return (new_prompt_text, new_prompt_version_id). new_prompt_version_id is None if unchanged."""
```

- **F02 부재 시 디폴트 구현** `NoopPromptModifier` — 입력 그대로 반환(기존 prompt body, same `prompt_version_id`). 따라서 F02 도입 전에도 F01은 same prompt로 재실행되어 retry 메커니즘 자체는 작동(다만 PASS 비율은 60% 목표 미달 가능 — golden 측정에서 확인).
- F02 도입 시 `LlmPromptModifier`로 교체 + Protocol 통과(FR-8 회귀 0건).

### FR-9: 외부 모델 호출 격리 (CLAUDE.md §5.2)

- `engine/auto_loop.py`, `services/run_service.py`, `services/evaluation_service.py`(이미 그대로) 어느 곳에서도 `anthropic` / `openai` / `replicate` import 금지. 모델 호출은 모두 `adapters/`에서.
- 정적 검증: `rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/engine/auto_loop.py` → 0건.

### FR-10: Event Bus 멱등성 invariant (W1 closing 후 발견 사항)

- `RunEventBus.close_run(run_id)` 는 **이미 닫힌 run에 대해 no-op**이어야 한다(W1 closing 시 backend-engineer가 식별). `run_service.execute()`의 `except RunAbortedError:` 블록과 `finally:` 블록 양쪽에서 `close_run`이 호출될 수 있다.
- 본 feature 진입 시 `engine/run_events.py`의 `close_run` 구현을 멱등하게 유지(이중 호출 안전). 이중 호출 회귀 발견 시 unit 회귀로 차단.

---

## 5. Data Model

### 5.1 신규 테이블 — `retry_attempts`

```sql
CREATE TABLE retry_attempts (
  id                       TEXT PRIMARY KEY,                         -- ULID
  run_id                   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  node_execution_id        TEXT NOT NULL REFERENCES node_executions(id) ON DELETE CASCADE,
  node_id                  TEXT NOT NULL,                            -- DAG 안의 node id 문자열
  attempt_number           INT  NOT NULL,                            -- 0,1,2,3 (max_retry=3이면 최대 3)
  prompt_version_id_used   TEXT REFERENCES prompt_versions(id),       -- nullable: 인라인 prompt 노드 호환
  retry_guidance           JSONB,                                     -- nullable: attempt 0 (첫 시도)는 NULL
  evaluation_id            TEXT REFERENCES evaluations(id),           -- 이 attempt의 평가 결과
  cost_won                 NUMERIC(12,2) NOT NULL DEFAULT 0,          -- 이 attempt의 비용 (재시도 누적은 runs.total_cost)
  started_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at              TIMESTAMPTZ,
  CONSTRAINT retry_attempts_attempt_chk CHECK (attempt_number >= 0),
  UNIQUE (node_execution_id, attempt_number)
);

CREATE INDEX CONCURRENTLY idx_retry_attempts_run_id ON retry_attempts (run_id);
CREATE INDEX CONCURRENTLY idx_retry_attempts_node_execution_id ON retry_attempts (node_execution_id);
```

### 5.2 기존 테이블 변경 — `evaluations`

```sql
ALTER TABLE evaluations
  ADD COLUMN retry_guidance      JSONB,                                -- nullable: PASS 시 NULL
  ADD COLUMN failed_dimensions   JSONB NOT NULL DEFAULT '[]';
```

- 마이그레이션 안전: 둘 다 nullable 또는 default — 기존 row 0 영향.
- PRD §9 W4 출구 기준("retry_guidance가 evaluation에 저장되는 schema 확정") 만족.

### 5.3 기존 테이블 변경 — `runs`

본 feature 범위에서 `runs.status` enum 변경 **없음**.

- budget 초과는 기존 `'failed'` 분류로 처리(FR-2). 이는 user-facing UI에서 SSE 이벤트(`run_budget_exceeded`)로 구분 가능.
- `'budget_exceeded'` 별도 enum 분리는 F06 observability 시점에 검토 — 본 feature는 minimum scope.

### 5.4 ER 다이어그램

```
runs ──< node_executions ──< retry_attempts >── evaluations
                  │                                     │
                  └─────────── (1:1 최종 attempt) ──────┘

retry_attempts ── prompt_version_id_used ──> prompt_versions   (F05)
```

---

## 6. API Surface

모든 응답은 snake_case (CLAUDE.md §3.3). 본 feature는 신규 read-only 엔드포인트 1개와 SSE 이벤트 2종 추가. 기존 `POST /api/runs`는 행동 변경(자동 retry 활성)이지만 schema는 호환.

### 6.1 엔드포인트 목록

| Method | Path | 설명 | Auth |
|---|---|---|---|
| `GET` | `/api/runs/{run_id}/retry-attempts` | run의 모든 attempt 목록 (FR-4 기록 기반) | API key |
| `GET` | `/api/runs/{run_id}` | (기존) — 응답에 `retry_summary` 필드 추가 (`{"total_attempts": int, "succeeded": bool}`) | API key |
| `POST` | `/api/runs` | (기존) — 호출자에게는 동일, 내부적으로 auto loop 활성 | API key |

신규 SSE 이벤트(기존 `/api/runs/{run_id}/events` 스트림에 추가):
- `node_retry` — `{"node_id": str, "attempt_number": int, "retry_guidance": dict, "failed_dimensions": list[str]}`
- `run_budget_exceeded` — `{"node_id": str, "total_cost_won": float, "budget_won": float}`

### 6.2 응답 예시 — `GET /api/runs/{run_id}/retry-attempts`

```json
{
  "run_id": "run_01J...",
  "attempts": [
    {
      "id": "rta_01J...",
      "node_id": "img1",
      "attempt_number": 0,
      "prompt_version_id_used": "pmv_01J...",
      "retry_guidance": null,
      "evaluation_id": "eval_01J...",
      "cost_won": 12500.00,
      "passed": false,
      "failed_dimensions": ["composition", "lighting"],
      "started_at": "2026-05-08T03:14:22Z",
      "finished_at": "2026-05-08T03:15:01Z"
    },
    {
      "id": "rta_01J...",
      "node_id": "img1",
      "attempt_number": 1,
      "prompt_version_id_used": "pmv_01J...",
      "retry_guidance": {
        "instruction": "주광원을 좌측 45도에서 우측 정면으로 변경, 배경 단순화",
        "confidence": 0.82
      },
      "evaluation_id": "eval_01J...",
      "cost_won": 12500.00,
      "passed": true,
      "failed_dimensions": [],
      "started_at": "2026-05-08T03:15:30Z",
      "finished_at": "2026-05-08T03:16:08Z"
    }
  ],
  "total_attempts": 2,
  "succeeded": true
}
```

### 6.3 SSE 이벤트 페이로드 예시

```json
// event: node_retry
{
  "run_id": "run_01J...",
  "node_id": "img1",
  "attempt_number": 1,
  "retry_guidance": {"instruction": "...", "confidence": 0.82},
  "failed_dimensions": ["composition", "lighting"]
}

// event: run_budget_exceeded
{
  "run_id": "run_01J...",
  "node_id": "img2",
  "total_cost_won": 105000.00,
  "budget_won": 100000.00
}
```

### 6.4 ETag

- `GET /api/runs/{run_id}/retry-attempts` 는 read-only 조회만 — ETag 불필요.

---

## 7. UI / UX

Run detail 화면 한 곳에 retry timeline 섹션 추가. 별도 신규 화면 없음.

### 7.1 `/runs/:run_id` — Run detail에 retry timeline 섹션 추가

- 섹션 위치: 기존 RunStatusPanel 아래, EvaluationPanel 위.
- 노드별 그룹: 각 노드의 attempt들을 vertical timeline으로 표시.
- attempt 카드: `attempt #N` 라벨 + prompt_version_id 링크(F05 `/prompts/:id`로 이동) + 평가 결과 배지(PASS/FAIL + 점수) + retry_guidance 토글(클릭 시 본문 표시).
- attempt 간 prompt body diff 토글: `attempt N+1`의 prompt가 N과 다르면 인라인 diff 보기 버튼(F02 도입 후 의미 있음 — 현재는 same prompt이므로 "변경 없음" 표시).

### 7.2 PASS 시 검수 안내 배너 — 자동 approved 금지 시각화

- run.status='succeeded' && all nodes passed → 화면 상단에 안내 배너:

> "모든 노드 PASS — 디자이너 검수 후 'approved' 버튼으로 운영 승인하세요."

- "검수 시작" CTA → 기존 `/styles/:id/review` 화면으로 이동(Phase 1 인터페이스). 직접 status를 'approved'로 자동 전이하는 UI 경로 0건(CLAUDE.md §5).

### 7.3 디자인 토큰

- 모든 색상은 디자인 토큰만 사용(임의 hex/px 0건, CLAUDE.md §5.3).
- attempt 배지: PASS → `var(--color-success)`, FAIL → `var(--color-warning)`, abort → `var(--color-danger)`.
- budget_exceeded SSE 알림 배너: `var(--color-danger)` + `var(--space-4)` padding.
- retry timeline 카드: `var(--color-surface-2)` 배경, `var(--space-3)` padding, `var(--radius-md)`.

---

## 8. Non-Functional Requirements

### 8.1 성능

| 지표 | 목표 |
|---|---|
| retry overhead vs base run time | ≤2× (max_retry=3 평균 1.5 attempt 가정) |
| SSE 이벤트 발행 지연 | ≤500ms (p95) |
| `GET /api/runs/{run_id}/retry-attempts` (attempt ≤30건) | P95 ≤200ms |
| `retry_attempts` 인덱스 | `idx_retry_attempts_run_id` (B-tree), `idx_retry_attempts_node_execution_id` (B-tree) — 모두 CONCURRENTLY (W5) |

### 8.2 보안

- API key 인증 (Phase 1과 동일 헤더 `X-Workbench-Key`).
- `retry_guidance` 본문에 PII 가능성 → 로그는 hash/요약만, 본문은 DB만(CLAUDE.md §9, B3 패턴 유지).
- `engine/auto_loop.py`는 외부 SDK import 금지(FR-9, 정적 검증).

### 8.3 동시성

- 한 run 안의 attempt는 직렬(같은 노드의 N+1 attempt는 N PASS/FAIL 결과 의존).
- 여러 run은 병렬 가능 — `RetryAttemptRepo.create()` 가 unique constraint `(node_execution_id, attempt_number)` 로 보호.
- `RunEventBus.close_run()` 멱등 invariant(FR-10).

### 8.4 외부 모델 호출 격리

- `engine/auto_loop.py` 어느 곳에서도 `anthropic` / `openai` / `replicate` import 금지.
- 정적 검증: `rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/engine/auto_loop.py` → 0건.
- 모델 호출은 `DagExecutor` → `adapters/` 경로만.

### 8.5 마이그레이션 안전성

- `retry_attempts` 신규 테이블 — 기존 데이터 영향 0.
- `evaluations.retry_guidance` 는 nullable, `evaluations.failed_dimensions` 는 default `'[]'` — 기존 row 0 영향, downgrade 안전.
- 신규 인덱스는 모두 `postgresql_concurrently=True`(W5 컨벤션).

---

## 9. Acceptance Criteria

세션 종료 시 아래 모두 통과해야 F01 status='Done'.

- [ ] **AC-1**: golden suite (`tests/golden/auto_loop/`) 에서 retry_attempt 1~3 안에 PASS 비율 ≥60% (PRD §9 W4 출구 기준).
- [ ] **AC-2**: `max_retry=3` 초과 시 `RunAbortedError` raise + run.status='failed' + `run_failed` SSE 이벤트 발행.
- [ ] **AC-3**: `cost_budget_won` 가드 트리거 시 evaluator 호출 전 abort + `run_budget_exceeded` SSE 이벤트 발행 (W1 closed 검증).
- [ ] **AC-4**: `eval_service` 가 `POST /api/runs` 운영 path로 호출됨 — 모든 노드에 대해 evaluation row 1+개 생성 (W2 closed 검증).
- [ ] **AC-5**: 노드의 모든 attempt가 `retry_attempts` 테이블에 row로 기록 — `attempt_number`는 0부터 연속, `(node_execution_id, attempt_number)` unique 위반 0건.
- [ ] **AC-6**: 모든 evaluation row의 `retry_guidance`(FAIL일 때)와 `failed_dimensions`가 정상 저장. PASS 시 `retry_guidance IS NULL`.
- [ ] **AC-7**: 모든 노드 PASS 시 `runs.status='succeeded'` 까지만 변경 — Style entity의 `status` 자동 전이 0건. 정적 검증: `rg "update_status.*approved" backend/src/style_workbench/engine/auto_loop.py services/run_service.py` → 0건.
- [ ] **AC-8**: `engine/auto_loop.py` 외부 SDK import 0건 (FR-9 정적 검증).
- [ ] **AC-9**: `mypy backend/src` strict 0건. `ruff check` 0건. 신규 인덱스 모두 `postgresql_concurrently=True` (W5 컨벤션).
- [ ] **AC-10**: e2e Playwright 시나리오 1건: Run 시작 → eval FAIL → retry → PASS → `/runs/:run_id` 화면에 retry timeline 표시 + PASS 배너 표시 + "approved" 자동 전이 0건.
- [ ] **AC-11**: `RunEventBus.close_run()` 이중 호출 회귀 0건 (FR-10 invariant).

---

## 10. Test Plan

### 10.1 Unit (`backend/tests/unit/`)

- `engine/test_auto_loop.py` — 가짜 evaluator로 PASS/FAIL 시퀀스 simulate. `RetryPolicy` / `RetryState` 와의 통합. max_retry=3 경계, attempt counter 정확성, NoopPromptModifier 디폴트 동작.
- `services/test_run_service.py` — 기존 `test_execute_budget_exceeded_aborts` (W1 closing 시 추가) + retry 경로 회귀.
- `domain/prompt/test_modifier.py` — Protocol 준수, NoopPromptModifier 회귀.

### 10.2 Integration (`backend/tests/integration/`)

- `test_run_eval_flow.py` (확장) — eval FAIL → retry → PASS 전체 시나리오. `retry_attempts` row 검증, `evaluations.retry_guidance` 저장 검증.
- `test_runs_eval_wiring.py` (W2 closing 시 신설) — `eval_service` DI graph 회귀.
- `test_auto_loop_budget.py` — budget guard가 evaluator 호출 전 트리거되는지 (mock evaluator의 호출 횟수로 검증).

### 10.3 Golden (`backend/tests/golden/auto_loop/`)

- `tests/golden/auto_loop/test_pass_rate.py` — 사전 정의된 fixture run 50건(다양한 노드 타입 × 다양한 FAIL 시나리오)에서 retry_attempt 1~3 PASS 비율 측정 → ≥60% 통과(AC-1).
- evaluator·variant_generator golden 회귀 무영향(F01은 호출 순서만 바꿈).

### 10.4 E2E (`frontend/tests/e2e/`)

- `auto_loop.spec.ts`:
  1. `/styles/:id` 진입 → 변주 1건 선택 → Run 시작.
  2. SSE 스트림 수신: `node_started` → `node_retry` (1회 이상) → `node_completed` → `run_completed`.
  3. `/runs/:run_id` 진입 → retry timeline 섹션에 attempt 카드 ≥2개 표시.
  4. PASS 배너 표시 + "검수 시작" CTA 클릭 → `/styles/:id/review` 이동(자동 approved 0건).

### 10.5 정적 검증

```bash
# 외부 SDK import 격리 (FR-9)
rg "from (anthropic|openai|replicate) import" \
   backend/src/style_workbench/engine/auto_loop.py
# 결과: 0건

# Style 자동 approved 금지 (FR-6)
rg "update_status.*approved" \
   backend/src/style_workbench/engine/auto_loop.py \
   backend/src/style_workbench/services/run_service.py
# 결과: 0건

# CONCURRENTLY 컨벤션 (W5)
rg "create_index" backend/alembic/versions/*retry_attempt* | grep -v "postgresql_concurrently=True"
# 결과: 0건

# format_map 회귀 방지 (CLAUDE.md §5.5, B3 그대로)
rg "\.format_map\(" backend/src/style_workbench
# 결과: 0건
```

---

## 11. Out of Scope

- prompt body LLM 수정 — F02 Prompt Optimizer.
- 큐/워커 분리 — F03.
- batch 회귀 (K개 Test Set 병렬) — F04.
- Slack / Email 회귀 알림 — F06.
- 사람 verdict 없는 자동 approved — Phase 3 이전 금지(CLAUDE.md §5).
- per-node 평가 점수 기반 동적 max_retry — Phase 3.
- `run.status='budget_exceeded'` 별도 enum 분리 — F06 observability 시점.
- retry attempt 간 prompt body diff UI — F02 도입 후 의미 있음, 본 feature는 placeholder만.

---

## 12. Dependencies

### 12.1 사전 조건 (확인됨)

- **F05 Prompt Library** — `prompt_version_id` 발행 인터페이스 필요. F01 의 `retry_attempts.prompt_version_id_used` FK 가 이를 요구. F05 단계 1·2 완료 후 진입.
- **W1 closed** — `services/run_service.py:execute()` 의 `cost_budget_won` 가드. 본 spec 작성 직전 PR(`Closes W1·W2 — cost_budget_won guard in execute() + eval_service DI wiring`)에서 closing 완료. 검증 결과: `pytest tests/unit/services/test_run_service.py` 11 passed (`test_execute_budget_exceeded_aborts` 포함).
- **W2 closed** — `api/deps.py:get_run_service()` 의 `eval_service` 주입. 위 동일 PR에서 closing 완료. 검증 결과: `pytest tests/integration -k runs` 6 passed (`test_runs_eval_wiring.py` 포함).
- `engine/retry.py:RetryPolicy / RetryState` (Phase 1 산출).
- `services/evaluation_service.py:EvaluationService.evaluate()` (Phase 1 산출).
- DB Alembic 작동 (`backend/alembic/`).

### 12.2 후속 의존자 (이 feature가 차단)

- **F02 Prompt Optimizer** — `PromptModifier` Protocol(FR-8) 의 실 구현체. F01 의 `NoopPromptModifier` 자리에 `LlmPromptModifier`로 교체.
- **F03 Async Queue / Worker** — auto loop를 큐 워커가 실행. F01 의 `AutoLoopOrchestrator` 가 worker 진입점이 됨.
- **F04 Regression Batch** — batch 단위 retry 통계. F01 의 `retry_attempts` 테이블이 회귀 단위.
- **F06 Analytics / Alerts** — `retry_attempts` + `run_budget_exceeded` 이벤트가 alert 트리거 데이터.

### 12.3 Phase 1 Deferred

- **W1 (cost_budget_won 가드)** — 본 spec 작성 직전 PR에서 closing 완료. 본 feature는 W1 의 가드 동작에 의존(FR-2).
- **W2 (eval_service wiring)** — 본 spec 작성 직전 PR에서 closing 완료. 본 feature는 W2 의 DI 그래프에 의존(FR-3, AC-4).
- W3 (`raw_response` TTL/PII 정책) — F06 시점에 closing.
- W4 (Replicate retry + `Idempotency-Key`) — F03 시점에 closing.
- W5 (CONCURRENTLY 인덱스) — 본 feature의 첫 마이그레이션부터 강제 (AC-9).

---

## 13. Implementation Phases

총 **1주** (PRD §9 W4 마일스톤). 각 단계 종료 시 PR 1건. PR description에 `Closes (Phase 1 deferred): W5` 명시. W1·W2 는 본 feature 진입 직전 별도 PR에서 closing 완료.

| 단계 | 기간 | 산출물 | 출구 검증 |
|---|---|---|---|
| **단계 1** | 2일 | `engine/auto_loop.py`(추출 + AutoLoopOrchestrator), `domain/prompt/modifier.py`(Protocol + NoopPromptModifier), `infra/repositories/retry_attempt_repo.py`, alembic 마이그(`retry_attempts` 테이블) | unit 통과, mypy strict 0건, FR-7·FR-8 회귀 |
| **단계 2** | 1일 | `evaluations.retry_guidance` / `failed_dimensions` 컬럼 + alembic 마이그, `services/evaluation_service.py` 저장 로직 | 기존 evaluation 회귀 0건, FR-5 검증 |
| **단계 3** | 1일 | SSE 이벤트(`node_retry`, `run_budget_exceeded`), `GET /api/runs/{run_id}/retry-attempts` 엔드포인트, Run detail UI retry timeline 섹션 + PASS 배너(FR-6 시각화) | e2e `auto_loop.spec.ts` 통과, AC-10 |
| **단계 4** | 1일 | golden W4 milestone fixture 50건 + 측정 스크립트 + 회귀 검증 | AC-1 통과 (PASS 비율 ≥60%) |

---

## 14. 참고

- 부모 PRD: [`../PRD.md`](../PRD.md) §3 Axis B, §5 Feature Index, §9 W4, §10 Risk 1, §11 W1·W2
- 절대 금지 사항: [`/CLAUDE.md`](/CLAUDE.md) §5 (자동 approved 금지, 외부 SDK 격리)
- Backend 컨벤션: [`/backend/CLAUDE.md`](/backend/CLAUDE.md) §5.4 (Engine), §6 (마이그레이션 절차)
- Phase 1 retry 인프라: [`/backend/src/style_workbench/engine/retry.py`](/backend/src/style_workbench/engine/retry.py)
- W1·W2 closing PR: `Closes W1·W2 — cost_budget_won guard in execute() + eval_service DI wiring`
- 선행 feature: [`F05_prompt_library.md`](./F05_prompt_library.md) (prompt_version_id 발행 인터페이스)
- 디자인 토큰: [`/docs/DESIGN_SYSTEM.md`](/docs/DESIGN_SYSTEM.md) §2, §5.3
