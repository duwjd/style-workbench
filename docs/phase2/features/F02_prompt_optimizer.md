# F02 — Prompt Optimizer

| 항목 | 값 |
|---|---|
| Feature ID | F02 |
| Phase | 2 |
| Priority | **P0** (Axis B Closed-Loop Quality — F01 retry 효과 실현) |
| Owner | 김정원 |
| 작성일 | 2026-05-12 |
| 상태 | Draft v1 |
| Estimated effort | 1주 (PRD §9 W5 마일스톤) |
| 부모 문서 | `docs/phase2/PRD.md` §3 Axis B, §5 Feature Index, §9 W5 |
| Dependencies | **F05 (PromptService.create_version)**, **F01 (PromptModifier Protocol + AutoLoopOrchestrator)** |
| Closes (Phase 1 deferred) | (해당 없음 — F02는 새 axis 작업) |

---

## 1. Problem

### 1.1 사용자 식별 이슈

> "평가 fail 시 prompt를 직접 고치는데, 매번 같은 차원에서 같은 실수를 반복한다. 자동으로 수정해주면 좋겠다." — Pilot user, 2026-05 (이슈 1 보강, PRD §1.2)

### 1.2 현재 코드 증거

F01 단계 1~4 완료 시점에서 `AutoLoopOrchestrator`가 retry FAIL 시 `PromptModifier.modify(...)` 를 호출하지만, 운영에 주입되는 구현체는 `NoopPromptModifier` 뿐이다.

- `backend/src/style_workbench/domain/prompt/modifier.py:74-81` — `NoopPromptModifier.modify()` 가 `("", prompt_version_id)` 만 반환 → same prompt로 재실행.
- `backend/src/style_workbench/engine/auto_loop.py:265-269` — `_modifier.modify()` 호출 후 `new_version_id is not None` 일 때 새 PromptVersion 으로 다음 attempt 실행. F02 부재 상태에서는 항상 `new_version_id is None` → retry가 실질적 변화를 만들지 않음.
- `backend/tests/golden/auto_loop/test_pass_rate.py` — F01 W4 golden 측정에서 `pass_at_attempt` 시나리오를 mock evaluator로 강제. PASS 비율 80%는 fixture 설계 결과이지 실 LLM 측정값이 아님.
- 결과: F01의 retry 메커니즘은 작동하지만 **retry 효과는 0** (same prompt → same output, 단 LLM 비결정성으로 약간의 variance).

### 1.3 결과적 한계

| 영향 | 측정 |
|---|---|
| retry 효과 (attempt 1~3 PASS 비율 향상폭) | 0% (NoopPromptModifier — same prompt 재실행) |
| retry_guidance 활용도 | DB 저장만, prompt 수정에 미반영 |
| `prompt_versions.parent_version_id` 계보 활용 | 0건 (F02 부재로 자동 분기 0건) |
| 디자이너 수동 prompt 수정 빈도 | 100% (FAIL 시 모두 사람 개입) |
| F01 W4 golden 측정의 신뢰도 | mock 기반 — 운영 환경 신뢰도 검증 불가 |

### 1.4 Closed-Loop의 사전 조건

PRD §3 Axis B 인용: "생성·평가·수정이 자동으로 회전". 현재는 생성(F05)·평가(F01 evaluator)는 되지만 **수정 단계가 사람**. F02가 prompt body 자동 수정 단계를 담당해야 Closed-Loop가 완성된다. F02 도입 후에야 F01 golden을 실 LLM 기반(`@pytest.mark.golden_live`)으로 측정해 W4 마일스톤 출구 기준이 진정 운영 환경에서 유효한지 검증 가능.

---

## 2. Goals / Non-Goals

### 2.1 Goals (모두 측정 가능)

| 지표 | Phase 2 목표 | 측정 |
|---|---|---|
| LlmPromptModifier 사용 시 F01 golden PASS 비율 (real LLM) | **≥70%** (mock 80%보다 보수적 — real LLM noise 반영) | `tests/golden/auto_loop/test_pass_rate_live.py` + `@pytest.mark.golden_live` |
| `safe_substitute` placeholder 보호 (CLAUDE.md §5.5) | **100% — 새 body의 `{name}` 등 placeholder 누락 0건** | unit 검증 + 정적 검증 |
| Evaluator ↔ Optimizer system prompt 분리 (CLAUDE.md §5 1번) | **system prompt 파일 별도 + 공유 0건** | 정적 검증 (`rg` import 그래프) |
| `parent_version_id` 자동 계보 추적 | **100% — F02 생성 모든 PromptVersion이 parent 보유** | integration 검증 |
| F02 호출당 평균 비용 | **≤500원 / call** (Claude Opus 입력 ~2K + 출력 ~500 토큰 기준) | `prompt_optimizations.cost_won` 집계 |

### 2.2 Non-Goals

- **전체 prompt 재생성** — Variant Generator(F05 단계 외)가 담당. F02는 retry_guidance 기반 *수정*만.
- **여러 노드 동시 수정** — 한 retry attempt당 한 노드만 수정 (F01 AutoLoopOrchestrator 노드별 직렬 처리).
- **Optimizer가 evaluator 결과 신뢰도까지 판단** — F02는 evaluator 출력을 그대로 받음. 평가 자체 개선은 F06+ 영역.
- **수동 모드와 자동 모드 분리** — 본 feature는 자동 모드(F01 호출 경유)만. 수동 "Optimize" 버튼은 옵션 (FR-7 참조).
- **prompt 본문 외 메타 변경** — `tags`, `model_default` 등 메타는 사람만 수정.
- **자동 promote** — F02가 새 PromptVersion 생성해도 `current_version_id`로 자동 promote 0건. 디자이너 사람 verdict 필수 (F05 §6 promote 흐름 유지).
- **OpenAI / Replicate 기반 Optimizer** — 본 Phase 2는 Claude만. 멀티 vendor는 Phase 3.

---

## 3. User Stories

| ID | 페르소나 | 시나리오 |
|---|---|---|
| **US-1** | 시스템 (F01) | AutoLoopOrchestrator가 retry FAIL 시 `LlmPromptModifier.modify(retry_guidance, failed_dimensions)` 호출 → F02가 Claude를 호출해 prompt body 수정 → 새 PromptVersion 생성 → 다음 attempt가 새 버전으로 실행. |
| **US-2** | 디자이너 | F01이 자동 retry로 PASS한 Run을 보고 `/prompts/:id/compare?from=v1&to=v2` 진입 → v1(원본)과 v2(F02 자동 수정)의 diff를 확인 → "v2 promote" 또는 "v1 유지" 사람 verdict. |
| **US-3** | 디자이너 | 특정 prompt의 회귀 점수가 떨어진 것을 F06이 알려줘 → `/prompts/:id` 페이지의 "Optimize" 수동 버튼 클릭 → 최근 FAIL evaluation의 retry_guidance를 입력으로 F02 호출 → 새 PromptVersion 생성 후 compare 화면으로 자동 이동. |
| **US-4** | 시스템 (F06) | 회귀 감지 시 자동 알림 + F02 자동 호출 옵션(Phase 2 후반). 본 spec 범위에서는 *F06에서 호출 가능한 service 인터페이스*만 정의. |
| **US-5** | 운영자 | F02 비용 누적이 F01 budget(`cost_budget_won`)에 포함됨 → budget 초과 시 F02 호출도 abort. |

---

## 4. Functional Requirements (FR)

### FR-1: PromptModifier Protocol 구현 — `LlmPromptModifier`

F01 spec §4 FR-8의 `PromptModifier` Protocol (`backend/src/style_workbench/domain/prompt/modifier.py:25-63`) 그대로 구현:

```python
class LlmPromptModifier:
    """F02 Prompt Optimizer — Claude 기반 prompt body 자동 수정."""

    def __init__(
        self,
        claude: ClaudeAdapter,
        prompt_service: PromptService,
        optimization_repo: PromptOptimizationRepo,
        model_id: str = "claude-opus-4-7",
    ) -> None: ...

    async def modify(
        self,
        prompt_version_id: str | None,
        retry_guidance: dict[str, Any],
        failed_dimensions: list[str],
    ) -> tuple[str, str | None]:
        """Return (new_prompt_text, new_prompt_version_id)."""
```

`NoopPromptModifier`와 동일 Protocol 시그니처로 AutoLoopOrchestrator 코드 무변경.

### FR-2: LLM 선택 — Claude Opus 4.7

- `model_id = "claude-opus-4-7"` 디폴트. `core/config.py`에 `PROMPT_OPTIMIZER_MODEL` 환경 변수로 override 가능.
- **Evaluator와 다른 모델 권장** — evaluator는 `claude-opus-4-6`(Phase 1 결정), optimizer는 `claude-opus-4-7`로 분리해 자기확증편향 차단(CLAUDE.md §5 1번).
- temperature는 낮게(0.2) — 결정적 수정.

### FR-3: System prompt — `prompts/prompt_optimizer.py`

별도 system prompt 파일. **Variant Generator / Evaluator의 system prompt 재사용 금지** (CLAUDE.md §5 1번 — 자기확증편향 차단).

입력:
- 원본 prompt body
- declared_variables (name / role / required)
- retry_guidance dict (evaluator가 출력한 instruction)
- failed_dimensions list (예: `["composition", "lighting"]`)
- node_type (text / image / video / composition)

출력 (JSON mode 강제):
```json
{
  "new_body": "수정된 prompt body — placeholder 보존 필수",
  "change_summary": "1-2문장 변경 요약 (한국어)",
  "preserved_placeholders": ["name", "role"]
}
```

작성자: **`prompt-engineer` 서브에이전트** (CLAUDE.md §1 prompts/ 행).

### FR-4: Placeholder 보호 (CLAUDE.md §5.5)

- F02 출력의 `new_body`는 입력 `declared_variables[].name` 의 모든 placeholder를 포함해야 함 (`required=true` 항목 100%, `required=false`는 옵션).
- `LlmPromptModifier.modify()` 내부에서 `extract_placeholders(new_body)` 호출 → `declared_variables` 와 비교 검증.
- 누락 시 → `PromptOptimizerInvalidOutputError` raise → AutoLoopOrchestrator는 same prompt로 재실행(fallback).
- **Claude 응답이 `{name}` 등 placeholder를 LLM 치환한 채로 반환할 가능성** → system prompt가 명시적으로 "placeholder를 literal `{name}` 형태로 유지하라" 지시 + 응답 검증.

### FR-5: 새 PromptVersion 생성

`PromptService.create_version` (F05 단계 1, `services/prompt_service.py:201-244`) 호출:
- `body = new_body` (F02 출력)
- `declared_variables` = 원본 그대로 (스키마 변경 금지)
- `parent_version_id` = 입력 `prompt_version_id` (자동 계보)
- `change_note = f"auto:F02 — {change_summary}"` (사람이 읽는 변경 사유)
- `created_by = "auto:F02"`
- `model_default` = 원본 그대로

F02는 새 PromptVersion 생성만 — promote는 사람 (FR Non-Goals).

### FR-6: `prompt_optimizations` 테이블 기록

각 F02 호출당 1 row:
- 입력: prompt_version_id(원본), retry_guidance, failed_dimensions, eval_evidence(연관 evaluation_id)
- 출력: new_prompt_version_id, cost_won, latency_ms, succeeded(bool)
- 실패 케이스(invalid output / API error)도 row 1건 + succeeded=false

회귀 분석, F06 알림 trigger 데이터로 활용.

### FR-7: 수동 "Optimize" endpoint (옵션)

`POST /api/prompts/{id}/optimize`:
- 입력: `{retry_guidance, failed_dimensions, evaluation_id?}` (evaluation_id 지정 시 그 evaluation의 retry_guidance/failed_dimensions 자동 추출)
- 동작: `LlmPromptModifier.modify()` 호출 → 새 PromptVersion → 응답에 `new_version_id` 반환.
- 응답: `{prompt_id, new_version_id, change_summary, cost_won}`
- 인증: API key (admin scope 불필요 — 일반 디자이너 흐름)

UI에서는 PromptDetail 화면 "Optimize" 버튼 (FR §7.1 참조).

### FR-8: AutoLoopOrchestrator 통합

- `api/deps.py:get_run_service()` 의 `prompt_modifier` 인자에 `LlmPromptModifier` 주입 (현재 디폴트 `NoopPromptModifier()`).
- 환경 변수 `PROMPT_OPTIMIZER_ENABLED=true|false` (디폴트 true) — false면 Noop fallback.
- **F02 부재 회귀**: `PROMPT_OPTIMIZER_ENABLED=false` 시 F01 W4 golden(mock 기반) 결과 그대로 유지.

### FR-9: 비용 누적 (RunService budget)

- F02 호출당 Claude API 비용을 `prompt_optimizations.cost_won`에 기록.
- `LlmPromptModifier.modify()`는 `total_cost_added: float` (USD or won)를 반환 시그니처에 추가하지 않음 — Protocol 호환 유지.
- 대신 `AutoLoopOrchestrator`가 modifier 호출 후 `optimization_repo.get_last(prompt_id)` 또는 modifier 인스턴스의 `last_cost_won` 속성 조회로 비용 가산.
- **단순화 결정**: F02 호출 비용을 F01 budget guard에 즉시 반영하지 않고 별도 집계만. budget 초과 위험은 F02 1회 비용 ≤500원이라 무시 가능 (F01 한 노드 비디오 ~80,000원). F03 시점에 budget 통합 검토.

### FR-10: 외부 모델 호출 격리 (CLAUDE.md §5.2)

- `engine/prompt_optimizer.py`: `anthropic` / `openai` / `replicate` import **금지**. Claude 호출은 `adapters/claude.py:ClaudeAdapter` 경유만.
- `prompts/prompt_optimizer.py`: 단순 system prompt 문자열 모듈 — SDK import 없음.
- 정적 검증: `rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/engine/prompt_optimizer.py` → 0건.

### FR-11: Evaluator ↔ Optimizer 분리 invariant (CLAUDE.md §5 1번)

- `prompts/prompt_optimizer.py`는 `prompts/evaluator_*.py` 의 system prompt 문자열을 import 또는 substring 재사용 0건.
- 정적 검증: `rg "from .evaluator|EVALUATOR_SYSTEM_PROMPT" backend/src/style_workbench/prompts/prompt_optimizer.py` → 0건.

---

## 5. Data Model

### 5.1 신규 테이블 — `prompt_optimizations`

```sql
CREATE TABLE prompt_optimizations (
  id                       TEXT PRIMARY KEY,                       -- ULID
  prompt_id                TEXT NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  parent_version_id        TEXT NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
  new_version_id           TEXT REFERENCES prompt_versions(id) ON DELETE SET NULL,
  retry_guidance           JSONB NOT NULL,
  failed_dimensions        JSONB NOT NULL DEFAULT '[]',
  eval_evidence            JSONB,                                   -- {evaluation_id, run_id, node_execution_id}
  change_summary           TEXT,                                    -- F02 LLM 출력의 1-2문장 요약
  cost_won                 NUMERIC(12,2) NOT NULL DEFAULT 0,
  latency_ms               INT,                                     -- F02 호출 응답 시간
  succeeded                BOOLEAN NOT NULL,                        -- false면 invalid output 또는 API error
  failure_reason           TEXT,                                    -- succeeded=false 시 사유
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY idx_prompt_optimizations_prompt_id
  ON prompt_optimizations (prompt_id);
CREATE INDEX CONCURRENTLY idx_prompt_optimizations_parent_version_id
  ON prompt_optimizations (parent_version_id);
CREATE INDEX CONCURRENTLY idx_prompt_optimizations_created_at
  ON prompt_optimizations (created_at DESC);
```

### 5.2 기존 테이블 변경 — 없음

`prompt_versions.parent_version_id` 는 F05 단계 1에서 이미 존재. F02는 그 컬럼을 활용만.

### 5.3 ER 다이어그램

```
prompts ──< prompt_versions ──< prompt_optimizations
                  ↑                       │
                  │ parent_version_id     │ new_version_id
                  └───────────────────────┘

prompt_optimizations ── eval_evidence ──> evaluations ── node_executions ── runs
```

`eval_evidence` JSONB는 F02 호출의 원천이 된 evaluation을 가리키는 ID 묶음 — 회귀 분석 시 "어떤 FAIL 평가가 어떤 수정으로 이어졌는가" 추적.

---

## 6. API Surface

모든 응답은 snake_case (CLAUDE.md §3.3).

### 6.1 엔드포인트 목록

| Method | Path | 설명 | Auth |
|---|---|---|---|
| `POST` | `/api/prompts/{id}/optimize` | 수동 트리거 (FR-7) | API key |
| `GET` | `/api/prompts/{id}/optimizations?limit=&offset=` | 해당 prompt의 F02 호출 이력 (회귀 분석) | API key |

자동 호출(F01 경유)은 별도 endpoint 없음 — `AutoLoopOrchestrator` 내부 호출만.

### 6.2 요청 예시 — `POST /api/prompts/{id}/optimize`

```json
{
  "evaluation_id": "eval_01J7YK..."
}
```

또는 직접 지정:
```json
{
  "retry_guidance": {"instruction": "주광원 변경", "confidence": 0.82},
  "failed_dimensions": ["composition", "lighting"],
  "parent_version_id": "pmv_01J7YK..."
}
```

`evaluation_id` 지정 시 서버가 해당 evaluation의 `retry_guidance` / `failed_dimensions` / `node_execution_id` → 원본 prompt_version 자동 추출.

### 6.3 응답 예시 — `POST /api/prompts/{id}/optimize`

```json
{
  "optimization_id": "po_01J7YK...",
  "prompt_id": "prm_01J7YK...",
  "parent_version_id": "pmv_01J7YK...",
  "new_version_id": "pmv_01J7ZZ...",
  "change_summary": "lighting 관련 추가 지시 + 주광원 방향 명시",
  "cost_won": 312.50,
  "latency_ms": 4523,
  "succeeded": true
}
```

실패 시 (FR-4 placeholder 위반 등):
```json
{
  "optimization_id": "po_01J7YK...",
  "prompt_id": "prm_01J7YK...",
  "parent_version_id": "pmv_01J7YK...",
  "new_version_id": null,
  "change_summary": null,
  "cost_won": 312.50,
  "latency_ms": 4523,
  "succeeded": false,
  "failure_reason": "PromptOptimizerInvalidOutputError: missing placeholder {role}"
}
```

200 응답 + `succeeded=false` (422가 아닌 이유: F02 호출 자체는 성공, LLM 출력만 부적합).

### 6.4 ETag

read-only `GET` endpoint만 — ETag 불필요. `POST /optimize`는 새 PromptVersion 생성 mutation이지만 prompt 자체의 락은 F05 단계 2 ETag로 보호 (해당 prompt의 다른 mutation과 동시 발생 회피).

---

## 7. UI / UX

수동 트리거 + compare 화면 통합. 별도 신규 화면 없음.

### 7.1 `/prompts/:id` PromptDetail — "Optimize" 버튼 (FR-7)

- 위치: "A/B" 버튼(F05 단계 5) 옆.
- 클릭 → 다이얼로그:
  - Mode 1: "최근 FAIL evaluation 자동 선택" — 해당 prompt 사용처(`prompt_usages`)의 최근 Run의 FAIL evaluation 자동 첨부. 단순한 흐름.
  - Mode 2: "직접 입력" — retry_guidance text + failed_dimensions chip 입력. 디자이너가 의도적으로 수정 방향 지시.
- "Optimize 실행" 버튼 → `POST /api/prompts/{id}/optimize` 호출 → 응답에 `new_version_id` 받으면 `/prompts/:id/compare?from=parent&to=new&optimization=po_...` 자동 navigate.
- 실패 시 (succeeded=false): toast 에러 + 다이얼로그 유지 + "다시 시도" 옵션.

### 7.2 `/prompts/:id/compare` 보강 (F05 단계 5 산출물)

- query param `optimization=po_...` 추가 시 화면 상단에 "F02 자동 수정 결과" 배지 표시.
- `change_summary` 표시.
- `eval_evidence.evaluation_id` 클릭 → 해당 evaluation 상세로 navigate.

### 7.3 `/prompts/:id` Optimizations 이력 패널 (옵션)

PromptDetail 사이드패널에 "최근 F02 호출 이력" 섹션 (≤5건). 각 row: 시점, succeeded, cost, change_summary.

`GET /api/prompts/{id}/optimizations?limit=5` 호출.

### 7.4 디자인 토큰

- 임의 hex/px 0건 (CLAUDE.md §5.3).
- F02 자동 수정 배지: `var(--color-info)` 배경 + `var(--space-2)` padding + `var(--radius-md)`.
- "Optimize" 버튼: `var(--color-primary)` (디자이너의 의도적 액션).

---

## 8. Non-Functional Requirements

### 8.1 성능

| 지표 | 목표 |
|---|---|
| F02 호출 latency (Claude Opus 4.7) | P95 ≤8초 |
| `POST /api/prompts/{id}/optimize` 응답 시간 | P95 ≤10초 (F02 호출 + 새 버전 생성) |
| `GET /api/prompts/{id}/optimizations` | P95 ≤200ms (인덱스 활용) |
| F01 retry 1회당 F02 호출 overhead | ≤8초 (직렬 1회) |

### 8.2 보안

- API key 인증.
- `retry_guidance` 본문에 PII 가능성 → 로그는 hash, 본문은 DB만 (CLAUDE.md §9, B3).
- Claude API 호출은 어댑터(`adapters/claude.py`) 경유 — API key는 `core/config.py:ANTHROPIC_API_KEY`.

### 8.3 동시성

- `LlmPromptModifier`는 stateless — 같은 prompt에 대한 동시 F02 호출은 두 새 버전 생성 (의도된 race 허용).
- F05 단계 1의 `prompt_versions.UNIQUE (prompt_id, version)` 가 race 시 자동 충돌 처리(transaction retry 또는 errors.ConflictError).

### 8.4 외부 모델 호출 격리

- `engine/prompt_optimizer.py`에서 `anthropic` / `openai` / `replicate` import 0건 (FR-10).
- 정적 검증: 본 spec §10.5.

### 8.5 마이그레이션 안전성

- `prompt_optimizations` 신규 테이블 — 기존 데이터 영향 0.
- 인덱스 모두 `postgresql_concurrently=True` (W5 컨벤션).
- downgrade는 정확히 reverse.

---

## 9. Acceptance Criteria

세션 종료 시 아래 모두 통과해야 F02 status='Done'.

- [ ] **AC-1**: `LlmPromptModifier` 사용 시 F01 golden_live suite(`tests/golden/auto_loop/test_pass_rate_live.py`)에서 retry_attempt 1~3 PASS 비율 ≥70% (real Claude API 호출).
- [ ] **AC-2**: F02 출력 `new_body`가 `declared_variables[].name`의 모든 `required=true` placeholder를 보존 (`PromptOptimizerInvalidOutputError` 회귀 0건 on golden_live).
- [ ] **AC-3**: F02 생성 모든 `prompt_versions`가 `parent_version_id` 보유 (NULL 0건). 회귀 분석에서 lineage 추적 가능.
- [ ] **AC-4**: `prompt_optimizations` 테이블에 모든 F02 호출이 row 1건 (성공/실패 무관). `succeeded=false` row의 `failure_reason` 필수.
- [ ] **AC-5**: Evaluator ↔ Optimizer system prompt 분리 — `rg` 정적 검증 0건.
- [ ] **AC-6**: 외부 SDK import 격리 — `engine/prompt_optimizer.py`에서 anthropic/openai/replicate 0건.
- [ ] **AC-7**: F02 자동 호출이 Style status='approved' 전이 0건 (CLAUDE.md §5 invariant 보존).
- [ ] **AC-8**: `mypy backend/src` strict 0건, `ruff check` 0건, 신규 인덱스 `postgresql_concurrently=True` 100% (W5 컨벤션).
- [ ] **AC-9**: `PROMPT_OPTIMIZER_ENABLED=false` 시 F01 회귀 0건 (NoopPromptModifier fallback) — mock 기반 golden 80% 그대로 유지.
- [ ] **AC-10**: `POST /api/prompts/{id}/optimize` 시나리오 통합 테스트: evaluation_id 자동 추출 + 새 버전 생성 + compare 화면으로 redirect.
- [ ] **AC-11**: F02 호출당 평균 비용 ≤500원 (golden_live suite 측정값).

---

## 10. Test Plan

### 10.1 Unit (`backend/tests/unit/`)

- `engine/test_prompt_optimizer.py` — `LlmPromptModifier` 단위 테스트 (ClaudeAdapter mock, PromptService mock):
  - Valid output → 새 PromptVersion 생성, `succeeded=true`.
  - Invalid output (placeholder 누락) → `PromptOptimizerInvalidOutputError`, succeeded=false row.
  - ClaudeAdapter API error → fallback 동작 (Protocol return 그대로 — `(_, None)`).
  - Evaluator/Optimizer system prompt 분리 (직접 import 회귀 0건).
- `domain/prompt/test_optimization.py` — `PromptOptimization` entity validation.

### 10.2 Integration (`backend/tests/integration/`)

- `test_prompt_optimize_api.py` (신규):
  - `POST /api/prompts/{id}/optimize` with `evaluation_id` → 200 + 새 버전 생성 + parent_version_id 정합.
  - 직접 `retry_guidance` 입력 → 200 + 새 버전.
  - 잘못된 evaluation_id → 404.
  - F02 invalid output → 200 + `succeeded=false`.
- `test_auto_loop_with_llm_modifier.py` (신규):
  - AutoLoopOrchestrator에 `LlmPromptModifier` 주입 → retry FAIL → F02 호출 → 새 prompt_version으로 next attempt → PASS.

### 10.3 Golden (`backend/tests/golden/`)

- `golden/auto_loop/test_pass_rate.py` (기존, F01 단계 4 산출물) — `PROMPT_OPTIMIZER_ENABLED=false`로 회귀, mock 기반 80% 유지.
- `golden/auto_loop/test_pass_rate_live.py` (신규, `@pytest.mark.golden_live`) — `LlmPromptModifier` + real Claude API 호출, F01의 50 시나리오 fixture를 재측정해 PASS 비율 ≥70% 검증 (AC-1).
  - CI nightly 실행 권장 (Claude API 비용).
- `golden/prompts/test_optimizer_invariants.py` (신규):
  - 10개 prompt body × 5 retry_guidance scenarios → F02 출력의 placeholder 보존 검증 (AC-2 회귀).

### 10.4 E2E (`frontend/tests/e2e/`)

- `prompt_optimizer.spec.ts` (신규):
  - `/prompts/:id` → "Optimize" 버튼 클릭 → 다이얼로그 → 최근 FAIL evaluation 자동 선택 → 실행 → `/prompts/:id/compare?from=...&to=...&optimization=...` 자동 navigate.
  - F02 자동 수정 배지 + change_summary 표시 검증.
  - LLM live call 회피: `page.route()`로 admin endpoint stub.

### 10.5 정적 검증

```bash
# 외부 SDK 격리 (FR-10 / AC-6)
rg "from (anthropic|openai|replicate) import" \
   backend/src/style_workbench/engine/prompt_optimizer.py
# 결과: 0건

# Evaluator ↔ Optimizer 분리 (FR-11 / AC-5)
rg "from \.evaluator|EVALUATOR_SYSTEM_PROMPT" \
   backend/src/style_workbench/prompts/prompt_optimizer.py
# 결과: 0건

# 자동 approved 금지 (AC-7)
rg "update_status.*['\"]approved['\"]" \
   backend/src/style_workbench/engine/prompt_optimizer.py \
   backend/src/style_workbench/services/prompt_service.py
# 결과: 0건 (사람 verdict 외)

# CONCURRENTLY 컨벤션 (AC-8 / W5)
rg "create_index" backend/alembic/versions/*prompt_optimization* | grep -v "postgresql_concurrently=True"
# 결과: 0건

# placeholder 보호 (FR-4 / AC-2)
# golden suite `golden/prompts/test_optimizer_invariants.py` 가 50 케이스 회귀
```

---

## 11. Out of Scope

- 전체 prompt 재생성 (Variant Generator 영역).
- 여러 노드 동시 수정 (F01 노드별 직렬 처리).
- F02 자체의 평가 (메타-평가).
- 자동 promote (사람 verdict 필수 — CLAUDE.md §5).
- OpenAI / Replicate 기반 Optimizer (Phase 3).
- F02 호출 비용을 F01 budget guard에 즉시 반영 (FR-9 단순화 결정 — F03 시점에 통합 검토).
- 멀티 모델 ensemble Optimizer (Phase 3+).
- 의미 기반 prompt 검색으로 유사 prompt 참고 (Phase 3).
- F02가 declared_variables 자체 수정 (스키마 변경 금지).

---

## 12. Dependencies

### 12.1 사전 조건 (확인됨)

- **F05 Prompt Library 단계 1~5 완료** — `PromptService.create_version` (`services/prompt_service.py:201-244`), `prompt_versions.parent_version_id`, `/prompts/:id/compare` 라우트 모두 존재.
- **F01 Auto Evaluation Loop 단계 1~4 완료** — `PromptModifier` Protocol (`domain/prompt/modifier.py:25-63`), `AutoLoopOrchestrator` (`engine/auto_loop.py:265-269`), `retry_attempts` + `evaluations.retry_guidance`/`failed_dimensions` 모두 존재. F01 W4 마일스톤 통과.
- `adapters/claude.py:ClaudeAdapter.generate()` 안정.
- `core/config.py:ANTHROPIC_API_KEY` 설정.

### 12.2 후속 의존자 (이 feature가 차단)

- **F03 Async Queue** — F02 자동 호출이 큐 worker 안에서 실행됨. F02 호출 시간이 길어지면 큐 비용 증가 — F03 worker 설계 시 F02 latency P95 ≤8초 가정.
- **F04 Regression Batch** — 회귀 게이트에서 F02 자동 수정 → 새 버전 promote 후보 → batch 측정 흐름. F02 출력 신뢰도가 회귀 판단의 입력.
- **F06 Analytics / Alerts** — `prompt_optimizations.succeeded=false` 빈도 추적 + F02 비용 알림.

### 12.3 Phase 1 Deferred

- W3 (raw_response TTL/PII) — F06 시점.
- W4 (Replicate retry + Idempotency-Key) — F03 시점.
- W5 (CONCURRENTLY) — 본 feature의 신규 인덱스부터 강제 (AC-8).

---

## 13. Implementation Phases

총 **1주** (PRD §9 W5 마일스톤). PR description에 `Closes (Phase 1 deferred): W5 from new indexes` 명시.

| 단계 | 기간 | 산출물 | 출구 검증 |
|---|---|---|---|
| **단계 1** | 1일 | `prompts/prompt_optimizer.py` system prompt + `domain/prompt/optimization.py` entity + Repo Protocol | prompt-engineer 통과, mypy 0건 |
| **단계 2** | 2일 | `engine/prompt_optimizer.py` (`LlmPromptModifier`) + `infra/db/models/prompt_optimization.py` + `infra/repositories/prompt_optimization_repo.py` + alembic 마이그 | unit 통과, AC-6, AC-8 통과 |
| **단계 3** | 1일 | `api/prompts.py` (`POST /optimize`, `GET /optimizations`) + `api/schemas/prompts.py` 확장 + `api/deps.py` wiring | integration 통과 (AC-10) |
| **단계 4** | 1일 | `/prompts/:id` UI "Optimize" 버튼 + `/compare` 보강 | e2e `prompt_optimizer.spec.ts` 통과 |
| **단계 5** | 1일 | golden_live suite 측정 + 회귀 검증 | AC-1 통과 (PASS ≥70%), AC-9 회귀 0건 |

---

## 14. 참고

- 부모 PRD: [`../PRD.md`](../PRD.md) §3 Axis B, §5 Feature Index, §9 W5
- 절대 금지 사항: [`/CLAUDE.md`](/CLAUDE.md) §5 (Variant Generator ↔ Evaluator ↔ Optimizer 분리, 외부 SDK 격리, 자동 approved 금지, placeholder 보호)
- Prompt 영역 규칙: [`/backend/src/style_workbench/prompts/CLAUDE.md`](/backend/src/style_workbench/prompts/CLAUDE.md)
- Backend 컨벤션: [`/backend/CLAUDE.md`](/backend/CLAUDE.md)
- 선행 feature: [`F05_prompt_library.md`](./F05_prompt_library.md), [`F01_auto_evaluation_loop.md`](./F01_auto_evaluation_loop.md)
- F01 golden suite: [`/backend/tests/golden/auto_loop/scenarios.py`](/backend/tests/golden/auto_loop/scenarios.py)
- Claude 어댑터: [`/backend/src/style_workbench/adapters/claude.py`](/backend/src/style_workbench/adapters/claude.py)
- 디자인 토큰: [`/docs/DESIGN_SYSTEM.md`](/docs/DESIGN_SYSTEM.md)
