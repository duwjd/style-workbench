# System Architecture — Style Workbench

> PRD + TECH_STACK 결정사항을 기반으로 한 시스템 설계 문서. Claude Code가 이 문서만 읽고도 코드 생성에 들어갈 수 있도록 모듈 책임/계약/디렉토리 구조까지 명시한다.

---

## 0. 한 장 요약

```
[Designer Browser] ──HTTPS──> [FastAPI Backend] ──> [PostgreSQL]
                                    │
                                    ├──> [Anthropic API] (Claude — variant gen, eval)
                                    ├──> [OpenAI API]    (gpt-5.4 — text 단계)
                                    └──> [Replicate API] (image / video — nano-banana-pro,
                                                          kling, seedance, runway, sora 등)

Phase 2 추가:
[FastAPI] ──> [arq queue (Redis)] ──> [Worker pool]
```

---

## 1. 전체 컨텍스트

### 1.1 시스템 경계

| 안 (이 시스템이 책임) | 밖 (다른 시스템 책임) |
|---|---|
| Style 정의 CRUD | gemgem.biz 운영 시스템 (영상 실제 사용자 서비스) |
| DAG 실행 (단계별 모델 호출) | NestJS → SQS → Python Worker (운영 영상 생성) |
| Variant 생성 (Claude) | 사용자 인증 (Phase 1은 단순 API key) |
| 단계별 평가 (Claude Vision) | 비즈니스 분석/통계 (BI는 별도) |
| 테스트 사진셋 관리 | end-user 데이터 |
| Style export → 운영 시스템 | 운영 시스템에 등록된 Style 실행 |

### 1.2 외부 인터페이스

- **운영 시스템 export**: 채택된 Style을 운영 시스템이 받을 수 있는 JSON 포맷으로 변환 (Export Adapter)
- **AI vendor API**: Anthropic(직접) / OpenAI(직접) / Replicate(이미지·영상 통합 게이트웨이)
- **prompt_optimizer**: 모델 프로파일 8개를 read-only로 import (초기 시드). 모든 프로파일이 이미 `replicate_model_id` 필드를 보유 → Replicate 어댑터에 그대로 매핑됨

---

## 2. 레이어 구조 (Backend)

Clean Architecture 변형. 의존 방향: `api` → `services` → `domain` ← `infra`. 외부 영향(DB, AI API)은 `infra`에 격리.

```
backend/
├── src/style_workbench/
│   ├── api/                        # FastAPI 라우터 (얇음)
│   │   ├── __init__.py
│   │   ├── deps.py                 # 의존성 주입
│   │   ├── styles.py               # /api/styles
│   │   ├── runs.py                 # /api/runs
│   │   ├── variants.py             # /api/variants
│   │   ├── evaluations.py          # /api/evaluations
│   │   ├── test_sets.py            # /api/test-sets
│   │   ├── models.py               # /api/models (read-only profile)
│   │   ├── exports.py              # /api/exports
│   │   └── uploads.py              # /api/uploads
│   │
│   ├── services/                   # 유스케이스 (오케스트레이션)
│   │   ├── style_service.py
│   │   ├── variant_service.py      # Claude로 5종 변주 생성
│   │   ├── run_service.py          # DAG 실행 시작
│   │   ├── evaluation_service.py   # 단계별 평가
│   │   ├── export_service.py       # 운영 포맷 변환
│   │   └── test_set_service.py
│   │
│   ├── domain/                     # 순수 비즈니스 로직 (외부 의존 없음)
│   │   ├── style/
│   │   │   ├── entity.py           # Style, Node, Edge dataclass
│   │   │   ├── schema.py           # JSON schema validation
│   │   │   ├── dag.py              # DAG 위상정렬, 사이클 감지
│   │   │   └── variables.py        # placeholder 검증
│   │   ├── run/
│   │   │   ├── entity.py           # Run, NodeExecution
│   │   │   └── state.py            # 상태 머신
│   │   ├── evaluation/
│   │   │   ├── entity.py           # EvalResult, Dimension
│   │   │   └── criteria.py         # 단계별 평가 차원 정의
│   │   └── prompt/
│   │       └── template.py         # placeholder 치환 (안전)
│   │
│   ├── engine/                     # DAG 실행 엔진
│   │   ├── executor.py             # 위상정렬 후 노드 단위 실행
│   │   ├── node_runners/           # 노드 타입별 러너
│   │   │   ├── base.py
│   │   │   ├── text_node.py
│   │   │   ├── image_node.py
│   │   │   ├── video_node.py
│   │   │   └── composition_node.py
│   │   └── retry.py                # 평가 실패 시 재시도 정책
│   │
│   ├── adapters/                   # 외부 모델 어댑터 (vendor 격리)
│   │   ├── base.py                 # ModelAdapter ABC
│   │   ├── claude.py               # Anthropic SDK — variant gen + eval
│   │   ├── openai.py               # OpenAI SDK — text 단계
│   │   ├── replicate.py            # Replicate SDK — 모든 image/video 모델
│   │   └── registry.py             # provider/model_id → adapter 매핑
│   │
│   ├── infra/                      # DB, 큐, 외부 I/O
│   │   ├── db/
│   │   │   ├── session.py          # async session factory
│   │   │   ├── base.py             # DeclarativeBase
│   │   │   └── models/             # ORM 모델
│   │   │       ├── style.py
│   │   │       ├── run.py
│   │   │       ├── evaluation.py
│   │   │       └── test_set.py
│   │   ├── repositories/           # 도메인 ↔ DB 매핑
│   │   │   ├── style_repo.py
│   │   │   ├── run_repo.py
│   │   │   └── evaluation_repo.py
│   │   └── queue/                  # Phase 2
│   │       └── arq_settings.py
│   │
│   ├── core/                       # 횡단 관심사
│   │   ├── config.py               # Pydantic Settings
│   │   ├── logging.py              # structlog 설정
│   │   ├── errors.py               # 도메인 예외 + HTTP 매핑
│   │   └── ids.py                  # ULID 생성기
│   │
│   ├── prompts/                    # AI prompt 템플릿 (system/user)
│   │   ├── variant_generator.py    # Variant Generator system prompt
│   │   ├── evaluator_text.py
│   │   ├── evaluator_image.py
│   │   ├── evaluator_video.py
│   │   └── evaluator_composition.py
│   │
│   └── main.py                     # FastAPI app factory
│
├── alembic/                        # 마이그레이션
│   └── versions/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden/                     # prompt 회귀 테스트셋
├── pyproject.toml
├── uv.lock
├── docker/
│   └── Dockerfile
└── docker-compose.yml
```

### 의존 방향 규칙

- `api` 는 `services` 만 임포트
- `services` 는 `domain`, `engine`, `adapters`, `infra/repositories` 임포트
- `domain` 은 어느 layer 도 임포트하지 않음 (순수)
- `engine` 은 `domain`, `adapters` 임포트
- `infra` 는 `domain` 임포트 가능 (외부 → 도메인 변환)

---

## 3. 핵심 모듈별 책임 & 계약

### 3.1 ModelAdapter (`adapters/base.py`)

모든 외부 모델 호출을 한 인터페이스로 통일. **어댑터는 3개로 충분**:

- `ClaudeAdapter` — Anthropic 직접 (variant 생성, 평가 전용)
- `OpenAIAdapter` — OpenAI 직접 (text 단계)
- `ReplicateAdapter` — Replicate 게이트웨이 (모든 image / video 모델)

```python
from abc import ABC, abstractmethod
from typing import Any, Literal
from pydantic import BaseModel

class ModelInput(BaseModel):
    prompt: str
    images: list[str] = []          # data URI 또는 provider URL
    parameters: dict[str, Any] = {} # duration, aspect_ratio 등

class ModelOutput(BaseModel):
    type: Literal["text", "image", "video"]
    content: str | None = None      # 텍스트일 때
    artifact_url: str | None = None # 이미지/비디오일 때 (provider URL, 화면 표시/다운로드용)
    raw_response: dict[str, Any] = {}
    cost_estimate: float = 0.0      # 원화

class ModelAdapter(ABC):
    provider: str                   # "anthropic" | "openai" | "replicate"
    supported_types: list[Literal["text", "image", "video"]]

    @abstractmethod
    async def call(self, model_id: str, input: ModelInput) -> ModelOutput: ...

    @abstractmethod
    def estimate_cost(self, model_id: str, input: ModelInput) -> float: ...
```

#### ReplicateAdapter — 단일 어댑터로 N개 모델 지원

```python
# adapters/replicate.py
import replicate

class ReplicateAdapter(ModelAdapter):
    provider = "replicate"
    supported_types = ["image", "video"]

    async def call(self, model_id: str, input: ModelInput) -> ModelOutput:
        # model_id 예: "google/nano-banana-pro", "kuaishou/kling-v2.5-turbo-pro",
        #              "bytedance/seedance-1.5-pro"
        prediction = await replicate.predictions.async_create(
            model=model_id,
            input=self._build_input(input),
        )
        completed = await self._poll(prediction)        # 비동기 폴링
        artifact_url = str(completed.output)            # provider URL 그대로 반환
        return ModelOutput(
            type=self._type_for(model_id),              # registry 또는 model_profile에서 lookup
            artifact_url=artifact_url,
            raw_response=completed.dict(),
            cost_estimate=self.estimate_cost(model_id, input),
        )
```

- 새 이미지/영상 모델 추가 = `model_profiles` 시드에 `replicate_model_id` 한 줄 추가. 어댑터 코드 변경 없음.
- 비용표는 `core/pricing.py` 의 model_id → 단가 매핑.
- polling 간격/최대 대기는 어댑터 내부 정책으로 캡슐화.

### 3.2 DAG Executor (`engine/executor.py`)

```python
class DagExecutor:
    """
    Style.nodes 의존 그래프를 위상정렬하고, 노드 단위로 NodeRunner를 호출.
    Phase 1: 직렬 실행 (단순). Phase 2: 독립 노드 병렬 실행.
    """
    async def execute(
        self,
        style: Style,
        user_input: dict[str, Any],     # {"photo": "s3://...", "name": "홍길동"}
        run_id: str,
    ) -> RunResult:
        topo_order = topological_sort(style.nodes, style.edges)
        outputs: dict[str, ModelOutput] = {}
        for node in topo_order:
            inputs = self._resolve_inputs(node, user_input, outputs)
            runner = NodeRunner.for_type(node.type)
            output = await runner.run(node, inputs)
            outputs[node.id] = output
            await self._persist_node_execution(run_id, node.id, output)
        return RunResult(run_id=run_id, outputs=outputs)
```

### 3.3 Variant Generator (`services/variant_service.py`)

```python
class VariantGenerator:
    """
    Brief를 받아 Claude로 N(=5)개의 Style 변주를 생성.
    각 변주는 동일 brief를 다른 angle/tone으로 해석.
    """
    async def generate(self, brief: Brief, n: int = 5) -> list[Style]:
        system_prompt = build_variant_system_prompt(brief)
        response = await self.claude.messages.create(
            model="claude-sonnet-4-6",
            system=system_prompt,
            messages=[{"role": "user", "content": brief.to_user_message()}],
            max_tokens=8000,
        )
        styles = parse_variants(response.content)  # 5개 Style JSON
        for s in styles:
            validate_dag(s)                        # 사이클/엣지 검증
            validate_variables(s)                  # placeholder 검증
        return styles
```

### 3.4 Step Evaluator (`services/evaluation_service.py`)

> Controller–Evaluator 분리 원칙: Evaluator는 **원본 prompt를 보지 않고** 결과물만 본다.

```python
class StepEvaluator:
    async def evaluate(
        self,
        node_type: NodeType,         # text/image/video/composition
        artifact: ModelOutput,
        brief_summary: str,          # 원본 prompt 대신 요약된 의도만 전달
    ) -> EvalResult:
        prompt = load_evaluator_prompt(node_type)
        response = await self.claude.messages.create(
            model="claude-opus-4-6",
            system=prompt,
            messages=[build_eval_message(artifact, brief_summary)],
        )
        return parse_eval_result(response)        # 차원별 점수 + retry_guidance
```

---

## 4. 데이터 모델 (PostgreSQL)

### 4.1 ER

```
styles ──< style_versions ──< runs ──< node_executions ──< evaluations
                                  │
                                  └─< run_inputs (어떤 사용자 사진을 썼는지)

test_sets ──< test_set_items
model_profiles (prompt_optimizer에서 임포트, read-only)
exports
```

### 4.2 주요 테이블

```sql
-- Style 정의 (DAG는 JSONB)
CREATE TABLE styles (
  id              TEXT PRIMARY KEY,           -- ULID
  name            TEXT NOT NULL,
  concept         TEXT,
  vertical        TEXT,
  tags            TEXT[],
  status          TEXT NOT NULL DEFAULT 'draft',  -- draft|reviewing|approved|deprecated
  current_version INT NOT NULL DEFAULT 1,
  created_by      TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 버전별 DAG 정의
CREATE TABLE style_versions (
  id          TEXT PRIMARY KEY,
  style_id    TEXT NOT NULL REFERENCES styles(id) ON DELETE CASCADE,
  version     INT  NOT NULL,
  dag         JSONB NOT NULL,                 -- {nodes, edges, variables}
  brief       JSONB,                          -- 원본 brief (variant origin)
  parent_variant_of TEXT,                     -- 다른 variant에서 파생된 경우
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(style_id, version)
);

CREATE INDEX idx_style_versions_dag ON style_versions USING GIN (dag);

-- 실행 (한 번의 DAG 실행 = 하나의 Run)
CREATE TABLE runs (
  id              TEXT PRIMARY KEY,
  style_version_id TEXT NOT NULL REFERENCES style_versions(id),
  test_set_id     TEXT,                       -- 회귀 batch인 경우
  user_input      JSONB,                      -- {photo: s3://, name: "..."}
  status          TEXT NOT NULL,              -- pending|running|succeeded|failed|cancelled
  total_cost      NUMERIC(10, 2),
  started_at      TIMESTAMPTZ,
  finished_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 노드 단위 실행 결과
CREATE TABLE node_executions (
  id              TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  node_id         TEXT NOT NULL,              -- DAG 안의 node id
  node_type       TEXT NOT NULL,              -- text|image|video|composition
  model_provider  TEXT,
  model_id        TEXT,
  prompt_resolved TEXT,                       -- placeholder 치환된 최종 prompt
  artifact_url    TEXT,                       -- provider URL
  raw_response    JSONB,
  cost            NUMERIC(10, 2),
  status          TEXT NOT NULL,
  started_at      TIMESTAMPTZ,
  finished_at     TIMESTAMPTZ
);

-- 평가
CREATE TABLE evaluations (
  id              TEXT PRIMARY KEY,
  node_execution_id TEXT NOT NULL REFERENCES node_executions(id) ON DELETE CASCADE,
  evaluator_model TEXT NOT NULL,              -- claude-opus-4-6
  overall_result  TEXT NOT NULL,              -- PASS|FAIL
  dimensions      JSONB NOT NULL,             -- [{name, score, result, reason}]
  retry_guidance  TEXT,
  human_verdict   TEXT,                       -- 디자이너가 채택/기각
  human_comment   TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 테스트 사진셋 (Phase 1.5+)
CREATE TABLE test_sets (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  category    TEXT NOT NULL,                  -- portrait|product|character|...
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE test_set_items (
  id          TEXT PRIMARY KEY,
  test_set_id TEXT NOT NULL REFERENCES test_sets(id) ON DELETE CASCADE,
  files       JSONB NOT NULL,                 -- [s3 url, ...] 단계별 입력 자료 가능
  metadata    JSONB                           -- 인물 정보, 환경 등 메타
);

-- 모델 프로파일 (prompt_optimizer에서 import, read-only)
CREATE TABLE model_profiles (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  type        TEXT NOT NULL,                  -- text|image|video|composition
  provider    TEXT NOT NULL,
  profile     JSONB NOT NULL,
  imported_from TEXT                          -- prompt_optimizer file path
);

-- Export 이력
CREATE TABLE exports (
  id          TEXT PRIMARY KEY,
  style_version_id TEXT NOT NULL REFERENCES style_versions(id),
  format      TEXT NOT NULL,                  -- gemgem_prod_v1
  payload     JSONB NOT NULL,
  exported_at TIMESTAMPTZ DEFAULT NOW(),
  exported_by TEXT
);
```

---

## 5. API 표면

REST + JSON. 모든 응답은 `snake_case` (frontend가 axios 인터셉터로 변환).

### 5.1 핵심 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/styles` | Style 신규 생성 (Draft) |
| `GET`  | `/api/styles` | 리스트 (필터: vertical/status/tags) |
| `GET`  | `/api/styles/{id}` | 단건 조회 (current_version 포함) |
| `PUT`  | `/api/styles/{id}` | 메타 수정 (name, concept, status) |
| `POST` | `/api/styles/{id}/versions` | 새 버전 (DAG 수정 = 새 버전) |
| `GET`  | `/api/styles/{id}/versions/{v}` | 특정 버전 조회 |
| `POST` | `/api/variants` | Brief → 5종 변주 생성 (Claude) |
| `POST` | `/api/runs` | 실행 시작 (style_version_id + user_input or test_set_id) |
| `GET`  | `/api/runs/{id}` | 실행 상태/결과 조회 |
| `POST` | `/api/runs/{id}/cancel` | 실행 취소 |
| `POST` | `/api/evaluations/{node_execution_id}` | 단계별 평가 트리거 |
| `POST` | `/api/evaluations/{id}/verdict` | 디자이너 채택/기각 기록 |
| `GET`  | `/api/test-sets` | 테스트셋 리스트 |
| `POST` | `/api/test-sets` | 테스트셋 생성 (파일 업로드 후) |
| `GET`  | `/api/models` | 모델 프로파일 리스트 |
| `POST` | `/api/exports` | Style → 운영 시스템 포맷 export |

### 5.2 핵심 응답 예시 — `POST /api/variants`

요청:
```json
{
  "concept": "공포 컨셉의 키링 광고",
  "vertical": "merchandise_ad",
  "tone_guide": ["dim", "tense", "cold_color"],
  "step_composition": ["text", "image", "video"],
  "input_kinds": [{"role": "person", "count": 1}, {"role": "prop", "count": 1}],
  "n": 5
}
```

응답:
```json
{
  "variants": [
    { "id": "var_01J...", "dag": { "nodes": [...], "edges": [...], "variables": [] }, "rationale": "..." },
    { "id": "var_02J...", "dag": {...}, "rationale": "..." },
    ... 총 5개
  ]
}
```

### 5.3 SSE — 실행 진행 스트리밍

```
GET /api/runs/{id}/events  (text/event-stream)

event: node_started      data: {"node_id": "txt1"}
event: node_finished     data: {"node_id": "txt1", "artifact_url": "..."}
event: evaluation_done   data: {"node_id": "txt1", "score": 0.84}
event: run_finished      data: {"status": "succeeded"}
```

---

## 6. DAG 실행 흐름 (시퀀스)

```
[FE Builder]
  │ POST /api/variants (brief)
  ▼
[VariantService]
  │  Claude(Sonnet 4.6) — variant prompt
  │  → 5개 Style JSON
  │  validate_dag, validate_variables
  ▼
[FE: 사용자가 1개 선택 + 샘플 입력 사진 업로드]
  │ POST /api/runs (style_version_id, user_input)
  ▼
[RunService] → DagExecutor
  │  topological_sort
  │  ─ for each node:
  │      NodeRunner.run → ModelAdapter.call
  │      persist node_execution
  │      EvaluationService.evaluate (옵션, async)
  │      평가 FAIL & retry_remaining > 0:
  │         apply retry_modifier → 같은 노드 재실행
  ▼
[FE: SSE 구독 → 각 노드 결과 실시간 그리드에 표시]
  │
  ▼
[FE: 디자이너가 verdict 기록]
  │ POST /api/evaluations/{id}/verdict
  ▼
[StyleService.approve → status='approved']
  │
  ▼
[ExportService → /api/exports]
   → 운영 시스템 포맷 JSON 산출
```

---

## 7. 평가 루프 (Phase 1: 단계별 동기, Phase 2: 비동기)

```
node_execution 완료
  → trigger_evaluation
    → load criteria for node_type
    → call Claude Vision (Opus 4.6)
    → parse {dimensions, retry_guidance}
    → if PASS: 다음 노드로
    → if FAIL & attempt < max:
        retry_modifier 적용 (도메인 사전 lookup)
        같은 노드 재실행
    → if FAIL & attempt == max:
        → run.status='failed', 디자이너 알림
```

**자기 확증 편향 차단 장치**:
- Variant Generator(생성)와 Step Evaluator(평가)는 **다른 모델 + 다른 system prompt**
- Evaluator는 brief의 **요약**만 받음 (원본 prompt 미노출)
- 임계 점수 판단은 Python 코드 (Claude는 점수만 산출)

---

## 8. 보안 / 권한

### Phase 1
- 인증: 환경변수 `WORKBENCH_API_KEY` 1개 (디자이너 소수 사용)
- 시크릿: `.env` (Anthropic/OpenAI/Google/Kuaishou 키)
- CORS: 화이트리스트 (개발/스테이징/운영 도메인)

### Phase 2+
- OAuth (Google Workspace SSO 추정)
- RBAC: viewer / editor / approver
- API key는 AWS Secrets Manager
- Audit log: `audit_log` 테이블

---

## 9. 관측성 (Phase 2부터 본격 도입)

| 신호 | 도구 | 보존 |
|---|---|---|
| 구조화 로그 | structlog → stdout → Loki | 30일 |
| Trace | OpenTelemetry → Tempo | 7일 |
| Metric | OpenTelemetry → Prometheus → Grafana | 90일 |
| 에러 | Sentry | 30일 |

핵심 지표:
- `run_duration_seconds` (히스토그램, by node_type)
- `model_call_cost_won_total` (카운터, by provider/model)
- `evaluation_score` (히스토그램, by node_type/dimension)
- `variant_generation_duration_seconds`

---

## 10. Frontend 구조

```
frontend/
├── src/
│   ├── routes/
│   │   ├── _layout.tsx
│   │   ├── styles/
│   │   │   ├── index.tsx            # /styles  - Style List
│   │   │   ├── new.tsx              # /styles/new - Brief 입력
│   │   │   └── $styleId.tsx         # /styles/:id - Style Detail/Builder
│   │   ├── runs/
│   │   │   └── $runId.tsx           # /runs/:id - Comparison Grid
│   │   └── test-sets/
│   │       └── index.tsx
│   │
│   ├── features/
│   │   ├── style-builder/
│   │   │   ├── StyleBuilder.tsx     # React Flow 캔버스
│   │   │   ├── nodes/
│   │   │   │   ├── TextNode.tsx
│   │   │   │   ├── ImageNode.tsx
│   │   │   │   ├── VideoNode.tsx
│   │   │   │   └── CompositionNode.tsx
│   │   │   ├── NodePalette.tsx
│   │   │   └── PromptEditor.tsx
│   │   ├── variants/
│   │   │   ├── BriefForm.tsx
│   │   │   └── VariantPicker.tsx
│   │   ├── comparison/
│   │   │   ├── ComparisonGrid.tsx
│   │   │   ├── StageCell.tsx
│   │   │   ├── EvaluationBadge.tsx
│   │   │   └── VerdictPanel.tsx
│   │   └── test-sets/
│   │       └── TestSetManager.tsx
│   │
│   ├── api/
│   │   ├── client.ts                # axios + 인터셉터
│   │   ├── styles.ts
│   │   ├── variants.ts
│   │   ├── runs.ts                  # SSE 구독 포함
│   │   └── evaluations.ts
│   │
│   ├── stores/                      # Zustand
│   │   ├── styleStore.ts
│   │   ├── runStore.ts
│   │   └── uiStore.ts
│   │
│   ├── components/ui/               # shadcn/ui copy
│   ├── lib/                         # 유틸
│   ├── styles/                      # Tailwind layer
│   └── main.tsx
├── public/
├── vite.config.ts
└── package.json
```

### 데이터 흐름 (FE)

- **서버 상태**: TanStack Query (Style/Run 등 API 조회·뮤테이션)
- **로컬 UI 상태**: Zustand (현재 편집 중인 DAG, 비교 그리드 선택 상태)
- **폼 상태**: React Hook Form + Zod
- **실시간**: SSE (`/api/runs/{id}/events`) → React Query setQueryData 패치

---

## 11. 운영 시스템 호환 — Export Adapter

`services/export_service.py` 가 단일 책임으로 격리. Style v1 → 운영 포맷 v1.

```python
class GemgemExportAdapter:
    format: str = "gemgem_prod_v1"

    def export(self, style: Style, version: int) -> dict:
        return {
            "style_id": style.id,
            "version": version,
            "pipeline": [
                self._node_to_step(n)
                for n in topological_sort(style.nodes, style.edges)
            ],
            "variables": style.variables,
        }
```

운영 시스템이 포맷 변경하면 새 어댑터 (예: `gemgem_prod_v2`) 추가, 기존은 보존.

---

## 12. 비기능 요구사항 / 한계 명시

| 항목 | Phase 1 | Phase 2 | 비고 |
|---|---|---|---|
| 동시 사용 디자이너 | ~3 | ~10 | 단일 노드로도 가능 |
| 동시 실행 Run 수 | 5~10 | 50+ | Phase 2에서 워커 풀 |
| Run 전체 latency | 비디오 모델에 의존 (~수 분) | 동일 | AI vendor 처리 시간 |
| Variant 생성 latency | <30s | <30s | Claude Sonnet |
| 평가 latency / 노드 | <15s | <15s | Claude Vision |
| 데이터 보존 | DB 무기한 | 동일 | artifact_url은 provider 정책에 따라 만료 가능 |
| 가용성 목표 | 95% | 99% | Phase 1은 일과시간만 |

---

## 13. 디렉토리 트리 — 최종 (저장소 루트)

```
style-workbench/
├── backend/                  # 위 §2
├── frontend/                 # 위 §10
├── docker-compose.yml        # postgres + redis(Phase2) + backend + frontend
├── docker/
├── docs/                     # 본 문서들 사본
├── .github/workflows/
│   ├── backend-ci.yml
│   ├── frontend-ci.yml
│   └── e2e.yml
├── README.md
└── CLAUDE.md                 # Claude Code 컨벤션
```

---

## 14. 마이그레이션 전략 (prompt_optimizer → Style Workbench)

| 단계 | 작업 |
|---|---|
| M1 | `prompt_optimizer/backend/data/model_profiles/*.json` → `model_profiles` 테이블로 시드 (8개). `replicate_model_id` 필드가 그대로 ReplicateAdapter의 model_id 가 됨 |
| M2 | `claude_client.py`(prompt_optimizer/core)를 별도 패키지(`packages/claude-runtime`)로 추출, 두 프로젝트가 의존. `replicate_client.py`도 동일하게 추출 검토 |
| M3 | `step별 md/02_evaluator_prompts.md` 를 `prompts/evaluator_*.py` 의 시드로 이식 |
| M4 | `automation/eval_criteria.md`, `retry_modifiers.md` 를 도메인 데이터로 변환 (`domain/evaluation/criteria.py`) |
| M5 | (Phase 2) modules 81개를 Variant Generator의 prompt building hint로 활용 |

prompt_optimizer는 in-place 변경하지 않음. 자산만 복사.

---

## 15. 결정·미결 사항 요약

**결정됨**
- 별도 신규 프로젝트 (PRD §5)
- DAG 데이터 모델 (§4 nodes/edges/variables)
- Phase 1은 단일 노드 + BackgroundTasks, Phase 2부터 arq+Redis
- ModelAdapter 인터페이스 3개(Claude/OpenAI/Replicate)로 vendor 격리
- 이미지·영상은 Replicate 단일 게이트웨이 (텍스트는 OpenAI 직접)
- Variant Generator(Sonnet 4.6) ≠ Step Evaluator(Opus 4.6)

**미결 → 추후 ADR 필요**
- 운영 시스템 export 포맷 v1 (운영팀 자료 받은 후 확정)
- Phase 2 큐: arq vs RQ vs Celery (성능 측정 후 결정)
- 멀티테넌시 여부 (다른 팀에서도 쓸 가능성)
