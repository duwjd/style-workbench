# Style Workbench Phase 2 PRD — Closed-Loop Style Production

| 항목 | 값 |
|---|---|
| 작성일 | 2026-05-08 |
| 작성자 | 김정원 |
| 상태 | Draft v1 |
| Pilot user | 디자이너 (Phase 1과 동일) |
| 코드네임 | Style Workbench |
| 부모 문서 | `docs/STYLE_WORKBENCH_PRD.md`, `docs/SYSTEM_ARCHITECTURE.md` |
| 기간 | 8주 (Phase 1 종료 시점부터) |

---

## 1. Context — Phase 1 회고와 Phase 2 진입 동기

### 1.1 Phase 1 결과 요약 (2026-05-08 시점)

`docs/GETTING_STARTED.md` §9의 Phase 1 출구 기준이 모두 통과 가능 상태에 도달했다.

- 비즈니스 포트레이트 Style 1개를 디자이너가 6시간 내로 제작 가능 (DAG 빌더 + Variant Generator + Comparison Grid 동작)
- 시안 5종 자동 생성 → 디자이너가 1개 이상 채택 가능
- backend / frontend CI 그린, e2e happy path 1건 통과
- 모든 외부 모델 호출이 `adapters/` 경유 (Claude / OpenAI / Replicate)
- golden 회귀 (variant 생성 + 4개 evaluator) 안정

직전 세션에서 보강한 12건은 변경 이력(commit log)으로 추적된다. 본 PRD는 그 결과 위에서 출발한다.

### 1.2 Phase 1에서 노출된 4가지 한계

Phase 1을 사용해본 결과, "Time-to-Style 6h" 안에서도 디자이너 손이 가장 많이 가는 구간이 명확해졌다. 네 가지로 정리한다.

1. **자동 평가 결과를 받아도 prompt 수정은 사람이 한다.** Step Evaluator가 `retry_guidance` 필드를 산출하지만, 현재는 화면에 텍스트로만 표시된다. 디자이너가 Inspector에서 prompt를 손으로 고치고 다시 실행한다.
2. **회귀 검증을 매번 사람이 호출한다.** Test Set 개념이 데이터 모델에는 있지만 batch 회귀 트리거 / 분포 차트 / 회귀 게이트가 없다. 디자이너가 카테고리당 1~2장으로만 검증한다.
3. **Run 1개 = HTTP 1요청.** `BackgroundTasks` 기반이라 동시 실행 한계가 좁다. 5종 시안을 동시에 돌리면 backend 단일 프로세스가 큐 역할을 겸한다. 회귀 batch (K=10×카테고리 N개)로 확장하면 즉시 막힌다.
4. **Prompt 재사용·버전 관리 불가.** Prompt가 Style DAG 노드의 `prompt_template` 필드에 인라인 저장된다. 같은 프롬프트가 N개 Style에 복제되어 흩어지고, 회귀 알림이 와도 모든 Style을 손으로 갱신한다. 사용자가 직접 "프롬프트 관리 시스템이 미흡함"으로 식별한 이슈다.

### 1.3 Phase 2 비전 — Closed-Loop Style Production

> "AI가 항상 내가 요구한 품질의 결과를 내지 않기 때문에 그렇고, 최적화된 프롬프트를 만들기 어려운 것도 이유야. 시스템에서 사용되는 스타일 제작을 자동화할 수 있을까? 물론 다양한 주제의 스타일 뿐만 아니라, 생성된 영상 품질을 평가해서 스타일에 적용된 모델이나 프롬프트를 최적화하는 루틴이 있어야 할 것 같아." — Pilot user, 2026-05

Phase 2는 위 비전을 **닫힌 루프(Closed Loop)** 로 구현한다. 생성 → 평가 → prompt 수정이 자동으로 회전하고, 디자이너는 verdict와 채택만 본다. 자동화율은 100%가 아니라 **80%**(평가) / **70%**(prompt 수정)를 목표로 한다 — 사람의 미감 판단은 의도적으로 남긴다.

---

## 2. Goals / Non-Goals

### 2.1 Goals (모두 측정 가능)

| 지표 | Phase 1 도달 | Phase 2 목표 |
|---|---|---|
| Time-to-Style | 6h | **4h** |
| 시안 채택률 | ≥60% | **≥80%** |
| 단계별 평가 자동화율 | 50% | **80%** |
| 디자이너 월 생산량 | 20개 | **30개+** |
| Prompt 재사용율 (Library 참조 / 전체 prompt) | 0% | **≥70%** |
| 자동 retry 성공률 (max retry 안에 PASS) | n/a | **≥60%** |
| K=10 batch 평균 점수 (카테고리별) | n/a | **≥0.75 + 분산 ≤0.15** |
| Run job 큐 대기 시간 P95 | n/a | **≤30s** |

### 2.2 Non-Goals

- 100% 무인 운영 — 디자이너 verdict는 의도적으로 유지
- gemgem 운영 시스템(NestJS → SQS → Python Worker) 자체 변경
- end-user(영상 생성 사용자)의 Style 직접 편집
- prompt 마켓플레이스, 다국어 자동 번역 (Phase 3+)
- 멀티테넌시 / OAuth / RBAC (Phase 3+)
- prompt_optimizer 자체 폐기 — 자산 import 후에도 read-only로 보존

---

## 3. 4개 신규 Axis

Phase 2는 4개 axis로 구성된다. 각 axis는 1~2개 feature를 갖는다.

### Axis A — Prompt as First-Class Entity

- 모든 자동화의 데이터 기반. Prompt를 Style과 분리된 1급 엔티티로 승격.
- Feature: **F05 Prompt Library**
- 의존성: 없음. 가장 먼저 진입.

### Axis B — Closed-Loop Quality

- 생성·평가·수정이 자동으로 회전.
- Feature: **F01 Auto Evaluation Loop**, **F02 Prompt Optimizer**
- 의존성: F05 (prompt_version_id를 발행해야 retry로 새 버전 생성 가능)

### Axis C — Scale Infrastructure

- 동시성·회귀·budget 가드.
- Feature: **F03 arq Queue + Worker Pool**, **F04 Test Set Manager + Regression Batch**
- 의존성: F01·F02 (auto loop가 큐 위에서 도는 것이 자연스러움)

### Axis D — Observability

- 의사결정 데이터.
- Feature: **F06 Cost & Quality Analytics**
- 의존성: F03·F04 (대량 실행 데이터가 있어야 의미 있는 차트)

---

## 4. North-Star Metrics

Phase 1의 §8 표에 행을 추가한 형태.

| 지표 | 현재 (Phase 1 종료) | Phase 2 목표 | 측정 위치 |
|---|---|---|---|
| Time-to-Style | 6h | 4h | UI 세션 측정 |
| 디자이너 월 생산량 | 20개 | 30개+ | `styles.status='approved'` count by month |
| Style 1개 검증 비용 | ~8천원 | ~8만원 (회귀 포함) | `runs.total_cost` 합계 |
| 시안 채택률 | ≥60% | ≥80% | `evaluations.human_verdict='accept'` 비율 |
| 단계별 평가 자동화율 | 50% | 80% | `evaluations` 중 자동 PASS/FAIL 산출 비율 |
| Prompt 재사용율 | 0% | ≥70% | `nodes[].prompt_id IS NOT NULL` 비율 |
| 자동 retry 성공률 | n/a | ≥60% | `evaluations.retry_attempt>0` 중 최종 PASS |
| K=10 batch 평균 점수 | n/a | ≥0.75 / 분산 ≤0.15 | F04 분포 차트 |
| Run job 큐 대기 시간 P95 | n/a | ≤30s | F03 worker 메트릭 |

---

## 5. Feature Index

각 feature는 별도 spec 문서를 가진다. 본 PRD는 한 줄 정의 + 의존성 + spec 경로만 제공한다.

| ID | 이름 | 한 줄 문제 / 한 줄 솔루션 | Spec | 의존성 | 우선순위 |
|---|---|---|---|---|---|
| **F05** | Prompt Library | Prompt가 Style 노드에 인라인되어 재사용·버전관리 불가 → 1급 엔티티로 승격 | [`features/F05_prompt_library.md`](features/F05_prompt_library.md) | 없음 | P0 |
| **F01** | Auto Evaluation Loop | retry_guidance를 사람이 적용 → 자동 retry 루프 + max budget + 합격 기준 | (다음 세션) `features/F01_auto_evaluation_loop.md` | F05, W1, W2 | P0 |
| **F02** | Prompt Optimizer | 평가 fail 시 전체 재생성 → retry_guidance로 문제 노드 prompt만 수정 | (다음 세션) `features/F02_prompt_optimizer.md` | F05, F01 | P0 |
| **F03** | arq Queue + Worker Pool | BackgroundTasks 한계 → arq + Redis로 동시 Run ≥50, idempotency | `features/F03_arq_queue.md` | F01·F02 안정, W4 | P1 |
| **F04** | Test Set Manager + Regression Batch | 카테고리당 1~2장 검증 → K=10 batch + 분포 차트 + 회귀 게이트 | `features/F04_regression_batch.md` | F03 | P1 |
| **F06** | Cost & Quality Analytics | 측정 데이터 흩어짐 → run·node·prompt 단위 시계열 + 회귀 알림 | `features/F06_analytics.md` | F03·F04, W3 | P2 |

**구현 순서**: F05 → F01 → F02 → F03 → F04 → F06. F05가 다른 모든 feature의 데이터 기반이며, F01·F02·F03가 Closed-Loop의 핵심이다.

---

## 6. Phase 2 사용 시나리오

### 6.1 신규 Style 제작 (Day 1, ~4시간)

```
[Step 1] Brief 입력 (10분)
  - 컨셉/버티컬 + 단계 구성 + 톤 가이드
  - Phase 1과 동일

[Step 2] 5종 자동 생성 (≤30s)
  - Variant Generator가 5개 변주 산출
  - 각 변주의 prompt는 자동으로 Library에 저장 (F05 → draft 상태)

[Step 3] 자동 batch 회귀 (5~15분, 백그라운드)
  - 카테고리 매칭 Test Set이 있으면 K=10장 batch (F04)
  - F03 큐에 5개 변주 × 10장 = 50개 Run job 투입
  - F01 Auto Loop가 평가 FAIL 시 retry_guidance를 prompt로 변환
  - F02 Prompt Optimizer가 문제 노드 prompt만 수정 → 새 prompt_version 생성
  - max retry=3 + cost_budget_won 가드 (W1) 위반 시 자동 abort

[Step 4] 분포 + 디자이너 verdict (10분)
  - F04 분포 차트로 5개 변주 비교 (점수 평균/분산/회귀 차이)
  - F06 대시보드에서 비용·자동 retry 횟수 확인
  - 디자이너가 1개 채택 → status='approved'
  - 채택된 prompt는 Library에서 status='approved'로 승격

[Step 5] Export
  - Phase 1과 동일
```

### 6.2 운영 중 Style 개선 (회귀 알림 발생 시)

```
[알림] F06이 prompt P-123의 평균 점수가 -0.10 회귀했다고 알림
  ↓
[디자이너] /prompts/P-123 페이지 진입 → "Optimize" 버튼 클릭
  ↓
[F02] retry_guidance와 최근 fail 케이스 N건을 컨텍스트로 새 버전 v2 생성
  ↓
[F04] v1 vs v2를 같은 K=10 Test Set으로 A/B 자동 실행
  ↓
[디자이너] 점수 diff 확인 → v2 promote → P-123을 참조하던 모든 Style이 자동 갱신
       (단, prompt_pinned=true인 Style은 v1 고정 유지)
```

---

## 7. 데이터 모델 변경 요약

자세한 schema는 각 feature spec에 있다. 본 PRD는 영향 범위만 적는다.

### 7.1 신규 테이블

- `prompts` — F05 (id, name, node_type, owner, status, current_version, tags)
- `prompt_versions` — F05 (id, prompt_id, version, body, variables, model_default, parent_version_id, change_note)
- `prompt_usages` — F05 (prompt_id, prompt_version_id, style_version_id, node_id, last_run_score)
- `regression_batches` — F04 (id, prompt_version_id, test_set_id, mean_score, variance, status)
- `prompt_optimizations` — F02 (id, prompt_version_id, parent_version_id, retry_guidance, eval_evidence)

### 7.2 기존 테이블 변경

- `style_versions.dag.nodes[]` — `prompt_id`, `prompt_version_id`, `prompt_pinned` 필드 추가 (F05)
- `runs` — `queue_job_id` 컬럼 + 인덱스 (F03)
- `evaluations` — `retry_attempt` 컬럼 (F01) + `auto_verdict_meta` JSONB (F01)
- `node_executions` — `cost_running_sum` 컬럼 (W1)

### 7.3 마이그레이션 정책

- 신규 인덱스는 모두 `CREATE INDEX CONCURRENTLY` (W5 — Phase 1에서 이연된 컨벤션을 Phase 2 첫 마이그부터 강제)
- backfill은 별도 마이그레이션 (online migration 패턴) — 큰 테이블 차단 금지
- ORM 변경 시 항상 Alembic revision (CLAUDE.md §4 그대로)

---

## 8. 시스템 아키텍처 변경 요약

`docs/SYSTEM_ARCHITECTURE.md` §0의 "Phase 2 추가" 박스를 채우는 형태. 자세한 설계는 F03 spec에서 본 architecture doc을 갱신한다.

```
[Designer Browser] ──HTTPS──> [FastAPI Backend] ──> [PostgreSQL]
                                    │
                                    ├──> [Anthropic / OpenAI / Replicate]
                                    │
                                    ├──> [arq Queue (Redis)] (NEW — F03)
                                    │         │
                                    │         └──> [Worker Pool] (NEW — F03)
                                    │                  │
                                    │                  ├──> DagExecutor
                                    │                  ├──> AutoLoopController (NEW — F01)
                                    │                  └──> PromptOptimizer (NEW — F02)
                                    │
                                    ├──> [PromptService] (NEW — F05)
                                    │
                                    └──> [RegressionBatchScheduler] (NEW — F04)
```

신규 모듈:

- `services/prompt_service.py` — F05
- `engine/auto_loop.py` — F01 (DagExecutor + Evaluator + retry 오케스트레이션)
- `engine/prompt_optimizer.py` — F02 (retry_guidance → 새 prompt_version)
- `infra/queue/arq_settings.py`, `worker.py` — F03
- `services/regression_service.py` — F04
- `services/analytics_service.py` — F06

신규 prompt:

- `prompts/prompt_optimizer.py` — F02의 system prompt (Variant Generator와 다른 모델·다른 system prompt 유지 — CLAUDE.md §5)

### 8.1 절대 금지 사항 영향 분석 (CLAUDE.md §5)

8개 항목 모두 Phase 2에서도 그대로 유효하며, 본 PRD의 어떤 설계도 위반하지 않는다.

| 금지 사항 | Phase 2 영향 |
|---|---|
| Variant Generator와 Step Evaluator를 같은 system prompt에 섞기 | F02 Prompt Optimizer는 **세 번째 역할**로 분리 (Generator ≠ Evaluator ≠ Optimizer). 각자 다른 model + system prompt |
| 외부 SDK를 services/api에서 직접 호출 | F02·F04·F06 모두 `adapters/` 경유. arq worker도 동일 |
| Tailwind 임의 hex/px | F05·F04·F06 신규 화면 모두 디자인 토큰만 사용 |
| JSON 파일 기반 데이터 저장 | F05 Prompt Library도 PostgreSQL. import 도구는 1회성 backfill용 |
| DAG 위상 검증/사이클 감지 누락 | F02가 새 prompt_version을 만들어도 Style의 DAG는 변하지 않음 (prompt 본문만 변경) |
| placeholder `{name}` LLM 치환 가능성 무시 | F05의 모든 prompt 본문이 `safe_substitute` 검증 통과 후 저장 (FR-3) |
| Backend가 운영 시스템에 직접 등록 | Export Adapter는 Phase 1과 동일하게 단일 모듈 |
| 디자이너 검수 없이 Style을 자동 approve | F01 Auto Loop는 PASS 시에도 status='reviewing'까지만 — 'approved'는 사람 verdict (Phase 3 이전 유지) |

---

## 9. 8주 마일스톤

| 주차 | 산출물 | 출구 기준 | 비고 |
|---|---|---|---|
| W1 | F05 백엔드 (schema + repo + service + API) | `pytest tests/unit/services/test_prompt_service.py` 통과, alembic 마이그 적용 | 동시 W5 적용 (CONCURRENTLY) |
| W2 | F05 UI (/prompts + Inspector 통합) + import CLI | e2e: 디자이너가 Library에서 prompt 선택해 Style 노드에 삽입 가능 | prompt_optimizer/modules 81개 import 성공 |
| W3 | Phase 1 deferred W1·W2 closing | `pytest tests/integration/run_eval_flow.py` 통과 (cost guard + eval_service 운영 wiring) | F01 진입 차단 항목 |
| W4 | F01 Auto Evaluation Loop | retry_attempt 1~3 안에 PASS 비율 ≥60% on golden | retry_guidance가 evaluation에 저장되는 schema 확정 |
| W5 | F02 Prompt Optimizer | Optimizer가 retry_guidance로 새 prompt_version 생성. parent_version_id 추적 | Generator/Evaluator/Optimizer 3 분리 검증 |
| W6 | F03 arq + Worker Pool | 동시 Run 50건 처리, P95 큐 대기 ≤30s | W4 (Replicate retry) 동시 적용 |
| W7 | F04 Test Set Manager + Regression Batch | 카테고리 K=10 batch 자동 실행, 분포 차트 표시, 회귀 게이트 동작 | regression_batches 테이블 |
| W8 | F06 Cost & Quality Analytics + Phase 2 출구 검증 | 대시보드 5개 차트, 회귀 알림 1회 이상 트리거 | W3 (raw_response 정책) 동시 적용 |

### 9.1 Phase 2 출구 기준

- [ ] North-Star Metrics 표(§4)의 "Phase 2 목표" 컬럼이 8개 행 모두 측정값 보유 (n/a → 실측값)
- [ ] e2e: brief → 5종 자동 → batch 회귀 → 평가 자동 → 채택 시나리오가 `frontend/tests/e2e/closed_loop.spec.ts`에서 통과
- [ ] 6개 feature spec 문서가 모두 status='Done'
- [ ] W1~W5 5개 deferred 항목이 모두 closing
- [ ] CLAUDE.md §5 절대 금지 사항 8건 정적 검증 (`rg`로 위반 패턴 0건)

---

## 10. 리스크 / 미해결 질문

### Risk 1. 자동 retry로 인한 비용 폭주

F01 Auto Loop가 cost_budget_won 가드 없이 도는 순간, 비디오 모델 retry 1회당 수만 원이 누적될 수 있다.

- 완화: W1(cost_budget_won)을 F01 진입 전(W3) 강제 closing. budget exceed 시 즉시 abort + Run.status='budget_exceeded' 분류.

### Risk 2. Prompt fork 격증

F02가 retry마다 새 prompt_version을 만들면, 1년 뒤 prompt당 versions 수십 개가 쌓인다.

- 완화: F05 §11에 `prompts.gc_policy` 명시 (last 30일 미사용 + status='draft' + parent_used=false → 자동 deprecation). 단, Phase 2 종료 시점에는 GC 비활성, 데이터 누적 후 정책 검토.

### Risk 3. 모델 가격표 변동

`core/pricing.py`가 hard-coded이라 vendor 단가 인상 시 cost 추정이 어긋난다.

- 완화: F06 진입 시 pricing.py를 model_profiles 테이블의 `price_per_unit` 필드로 단일화. ADR 별도.

### Risk 4. K=10 batch 비용 누적

K=10 × 카테고리 5개 × 변주 5개 = 250 Run / Style. 비디오 모델 평균 단가 ~3천원/Run 기준 75만원/Style. 월 30개 Style × 75만 = 2,250만 원/월.

- 완화: F04 진입 전 비용 시뮬레이션 ADR. batch 빈도 정책(Style 등록 시 + 분기 회귀)으로 회수. 카테고리당 K를 줄이는 옵션도 검토.

### Risk 5. Phase 1 deferred W3·W4의 Phase 2 합류 여부

W3(raw_response DB 정책), W4(Replicate retry + Idempotency-Key)는 §11 표대로 F06·F03 시점 합류로 잡았지만, F03 시작 전에 idempotency가 없으면 큐 재처리 시 비디오 모델이 중복 호출될 위험이 있다.

- 완화: W4를 F03 W6 첫날 작업으로 강제 (지연 시 F03 일정 압박).

### 미해결 질문

- F02 Prompt Optimizer의 retry_guidance 입력 포맷 — Step Evaluator의 출력 schema가 안정적인가? Phase 1 golden fixture 18개로 안정성 측정 후 결정.
- F04 회귀 게이트의 "회귀" 정의 — 평균 -0.05? 분산 +0.1? 카테고리별로 다르게? F04 spec에서 ADR.
- F06 대시보드 노출 단위 — Style/Prompt/Vertical 어느 축이 1차? 사용 데이터 누적 후 결정 (Phase 2 W4 시점에 사용자 인터뷰).

---

## 11. Phase 1 Deferred 항목 추적 (W1~W5)

직전 세션이 분류한 5건. 본 PRD에서 처리 시기를 강제한다.

| ID | 이슈 | 현재 코드 위치 | Phase 2 처리 시기 | 차단하는 feature |
|---|---|---|---|---|
| **W1** | `cost_budget_won` 가드를 운영 `execute()` 경로에 적용 | `services/run_service.py:execute()` (현재 가드 없음) | **W3** (F01 진입 전) | F01 |
| **W2** | `deps.py`에서 `eval_service` 운영 wiring (현재 None 주입) | `api/deps.py:get_run_service()` | **W3** (F01 진입 전) | F01 |
| **W3** | `raw_response` DB 정책 명문화 (TTL / PII / archive) | `infra/db/models/run.py:NodeExecution.raw_response` | **W8** (F06 시점) | F06 |
| **W4** | Replicate 어댑터 retry + `Idempotency-Key` | `adapters/replicate.py` (retry/header 없음) | **W6 첫날** (F03 시점) | F03 |
| **W5** | 인덱스 마이그레이션 `CONCURRENTLY` 컨벤션 | 모든 신규/기존 마이그 | **W1부터 강제** (F05 첫 마이그부터) | (전 feature 마이그) |

PR마다 closing 항목 ID를 PR description에 명시한다 (예: `Close W2 — wire eval_service in deps.py`).

---

## 12. 다음 액션

1. **본 세션**: F05 Prompt Library spec 작성 → `features/F05_prompt_library.md`
2. **다음 세션**: W1·W2 closing → F01 spec 작성 (`features/F01_auto_evaluation_loop.md`)
3. 그 다음: F02 → F03 (W4 동시 closing) → F04 → F06 (W3 동시 closing)
4. F03 진입 시 `docs/SYSTEM_ARCHITECTURE.md` §0의 Phase 2 박스를 본 PRD §8 다이어그램으로 갱신
5. Phase 2 종료 시 본 문서를 status='Done'으로 변경하고 `docs/STYLE_WORKBENCH_PRD.md` §8 Phase 2 행을 실측값으로 업데이트
