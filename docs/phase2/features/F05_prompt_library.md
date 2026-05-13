# F05 — Prompt Library

| 항목 | 값 |
|---|---|
| Feature ID | F05 |
| Phase | 2 |
| Priority | **P0** (Phase 2 진입 차단 항목 — 다른 모든 feature의 데이터 기반) |
| Owner | 김정원 |
| 작성일 | 2026-05-08 |
| 상태 | Draft v1 |
| Estimated effort | 2주 (백엔드 1주 + UI 1주) |
| 부모 문서 | `docs/phase2/PRD.md` §3 Axis A, §5 Feature Index |
| Dependencies | Phase 1 완료 (확인됨) |
| Closes (Phase 1 deferred) | W5 (CONCURRENTLY 인덱스 — 본 feature의 첫 마이그부터 강제) |

---

## 1. Problem

### 1.1 사용자 식별 이슈

> "프롬프트 관리 시스템이 미흡함" — Pilot user, 2026-05 (이슈 4)

### 1.2 현재 코드 증거

Phase 1 종료 시점에서 prompt는 Style DAG 노드의 `prompt_template` 필드에 인라인으로 저장된다.

- `backend/src/style_workbench/domain/style/entity.py` — `Node` dataclass에 `prompt_template: str` 필드만 존재. prompt가 도메인 엔티티가 아님.
- `backend/src/style_workbench/infra/db/models/style.py` — `style_versions.dag` JSONB 컬럼 안의 `nodes[].prompt_template` 문자열로 직렬화. 별도 `prompts` 테이블 없음.
- 결과: 같은 prompt가 N개 Style에 복제되어 흩어진다. 검색·필터·태그 불가.

### 1.3 결과적 한계

| 영향 | 측정 |
|---|---|
| Prompt 재사용율 | 0% (모든 Style이 인라인 저장) |
| 버전 추적 | 불가 — Style 버전 안에 포함되어 prompt 단독 변경 이력 없음 |
| A/B 비교 | 불가 — 같은 prompt의 두 버전을 동일 입력으로 동시 실행할 수 없음 |
| 회귀 발생 시 갱신 비용 | O(N) — N개 Style을 손으로 모두 수정 |
| Auto Loop(F01)·Optimizer(F02) 적용 가능성 | **불가** — retry_guidance를 적용한 prompt를 어디에 저장할지 정의 없음 |

### 1.4 Closed-Loop의 사전 조건

F01 Auto Evaluation Loop와 F02 Prompt Optimizer는 평가 결과로 prompt를 자동 수정·새 버전 생성·롤백한다. 이 동작은 prompt가 **Style과 분리된 버저닝 가능한 1급 엔티티** 일 때만 정의 가능하다. 따라서 F05는 Phase 2의 모든 자동화 feature에 선행한다.

---

## 2. Goals / Non-Goals

### 2.1 Goals (모두 측정 가능)

| 지표 | Phase 2 목표 | 측정 |
|---|---|---|
| 신규 Style의 prompt 중 Library 참조 비율 | **≥90%** | `nodes[].prompt_id IS NOT NULL` 비율 |
| 운영팀 자산 import 성공 | **외부 prompt 디렉토리 일괄 import (~80개)** | CLI 1회 실행 후 `prompts` 테이블 row count |
| 단일 진실 출처 보장 | **같은 prompt를 ≥5개 Style이 참조해도 본문이 1곳에 존재** | `prompt_versions.body` 중복 0건 |
| prompt 검색 응답시간 | **P95 ≤200ms** (1만 건 기준) | API 측정 |

### 2.2 Non-Goals

- prompt를 외부에 publish (운영 export는 Phase 1 ExportAdapter가 처리)
- 다국어 prompt 자동 번역 — Phase 3
- prompt 마켓플레이스 / 팀 공유 / 권한 분리 — Phase 3+
- prompt 의미 임베딩 검색 — 본 feature는 키워드 + tag 기반만
- prompt 자체 fork (같은 prompt에서 분기) — F02 Optimizer가 담당. F05는 데이터 모델만 제공
- Slack / Email 회귀 알림 — F06이 담당

---

## 3. User Stories

| ID | 페르소나 | 시나리오 |
|---|---|---|
| **US-1** | 디자이너 | 새 Style을 만들 때, 검증된 비즈니스 포트레이트용 prompt를 검색해 노드에 1-click 삽입. 더 이상 빈 칸에서 시작하지 않는다. |
| **US-2** | 디자이너 | 회귀 평가에서 점수가 떨어진 prompt(P-123)를 한 번만 수정하면, P-123을 참조하는 5개 Style이 자동 갱신된다 (`prompt_pinned=false`). |
| **US-3** | 디자이너 | prompt 변경 후 변경 전(v1) vs 변경 후(v2)를 같은 user_input으로 동시 실행해 평가 점수 diff를 본다. v2가 좋으면 promote, 나쁘면 v1 유지. |
| **US-4** | 시스템 (F01) | Auto Loop가 retry_guidance로 prompt 본문을 분기시켜 새 prompt_version을 생성. parent_version_id를 통해 계보를 추적한다. |
| **US-5** | 운영팀 | 기존 prompt_optimizer 자산(외부 디렉토리)을 CLI 1회로 Library에 일괄 import. 가져온 prompt는 status='approved'로 시작. |

---

## 4. Functional Requirements (FR)

### FR-1: Prompt CRUD

- 필드: `id`(ULID), `name`, `node_type`(text/image/video/composition), `owner`, `status`, `current_version_id`, `tags`(string array), `created_at`, `updated_at`
- 메타 변경(`name`, `tags`, `status`)은 in-place. 본문 변경은 FR-2 새 버전.
- 삭제는 soft delete만 — `status='deprecated'` (cascade delete 금지: prompt_usages가 참조)

### FR-2: Immutable Versioning

- `prompts` (메타) 1 — N `prompt_versions` (본문) 관계.
- 본문(`body`) 변경 = 새 row in `prompt_versions`. 이전 버전 row는 immutable.
- `prompts.current_version_id` 가 활성 버전을 가리킴. promote 작업으로 변경.
- `prompt_versions.parent_version_id` 로 계보 추적 (F02 Optimizer가 활용).

### FR-3: Placeholder Validation (CLAUDE.md §5.5 그대로 보존)

- prompt body는 **반드시** `domain/prompt/template.py`의 `safe_substitute(...)` 로만 치환 가능.
- prompt 저장 시 `extract_placeholders(body)` 결과를 `prompt_versions.declared_variables` JSONB에 저장.
- API 레벨에서 `body`에 등장하는 placeholder가 모두 `declared_variables`에 선언되어 있어야 422.
- `str.format()` / `.format_map()` / `str.replace()` 호출 0건 (정적 검증, B3 패턴 유지).

### FR-4: 검색 + 필터

- `GET /api/prompts?node_type=...&tags=...&status=...&q=...&limit=20&offset=0`
- 키워드 `q`는 `name` + `tags` array 매칭 (full-text는 Phase 3).
- 인덱스: `idx_prompts_node_type` (B-tree), `idx_prompts_tags` (GIN). 모두 `CONCURRENTLY` 적용 (W5 closing).

### FR-5: Style 노드와의 link

`style_versions.dag.nodes[]` schema에 다음 필드 추가:

```jsonc
{
  "id": "img1",
  "type": "image_generation",
  "model": { "provider": "replicate", "model_id": "google/nano-banana-pro" },

  // 신규 (F05)
  "prompt_id": "prm_01J...",          // nullable — 인라인 호환
  "prompt_version_id": "pmv_01J...",  // 활성 시점 버전 스냅샷
  "prompt_pinned": false,             // true면 prompt_version_id 고정. false면 prompts.current_version_id 자동 추종
  "prompt_template": null,            // F05 적용 시점에는 prompt_id 와 동시 채움 금지

  "inputs": [...]
}
```

- `prompt_id IS NOT NULL` 인 노드의 `prompt_template` 은 항상 NULL.
- `prompt_pinned=true` 면 promote가 발생해도 이 Style은 `prompt_version_id`로 고정.
- 마이그레이션은 §5.4 backfill 정책 참조.

### FR-6: 사용처 추적

- `prompt_usages` 테이블이 어느 Style·Node·Run이 prompt를 참조하는지 기록.
- Run 종료 시 `prompt_usages.last_run_score` 업데이트 (해당 노드 평가 점수).
- `GET /api/prompts/{id}` 응답에 사용처 ≤20건 포함 (전체는 별도 paginate 엔드포인트).

### FR-7: prompt_optimizer 자산 import

- CLI: `uv run python -m style_workbench.tools.import_prompts --source <path>`
- 입력: 외부 디렉토리 (예: 운영팀이 별도 보관 중인 `prompt_optimizer/modules/`).
- 동작: 디렉토리 walk → 각 파일을 prompt 1건으로 변환 → `status='approved'`, `tags`는 카테고리 디렉토리명, `node_type`은 파일 이름 규칙(`*_text.md`, `*_image.md` 등).
- 멱등성: `imported_from` 필드 일치 시 skip (재실행 가능).
- 실패한 파일은 stderr에 누적 후 마지막에 요약 (`X imported, Y skipped, Z errored`).
- Admin only: API key 헤더 필요.

### FR-8: A/B 비교

- `POST /api/prompts/{id}/ab` 입력: `from_version`, `to_version`, `style_version_id`(nodes[] 위치 lookup), `user_input`
- 동작: 같은 user_input으로 두 버전 각각의 Run을 동시에 큐 (F03 도입 후) / 직렬 (F03 전).
- 응답: `ab_id` + Phase 1 SSE 동일 포맷의 진행 이벤트.
- 결과 화면: `/prompts/:id/compare?from=v1&to=v2&ab=...` (UI §7.3).

### FR-9: Lifecycle

| status | 의미 | 전이 가능 |
|---|---|---|
| `draft` | 작성 중. 신규 prompt 기본값 | → reviewing |
| `reviewing` | 디자이너가 검수 중 | → approved / draft |
| `approved` | 운영 가능. `current_version` 변경 가능 | → deprecated |
| `deprecated` | 신규 사용 차단. 기존 사용처는 유지 | (terminal) |

- Style 도메인의 `status` 모델과 동일 (CLAUDE.md §4.1 모델 일관성).
- `deprecated` prompt를 신규 Style 노드가 link 시도 → 422.

### FR-10: 외부 모델 호출 격리 (CLAUDE.md §5.2 그대로 보존)

- F05 자체는 외부 모델 호출 없음 (UI/CRUD/검증 영역).
- A/B 비교(FR-8)의 실제 실행은 기존 RunService 경로 → DagExecutor → adapters/. F05는 Run을 트리거하기만.
- `services/prompt_service.py`, `infra/repositories/prompt_repo.py` 어느 것도 `anthropic`/`openai`/`replicate` import 금지 (정적 검증으로 강제).

---

## 5. Data Model

### 5.1 신규 테이블 — `prompts`

```sql
CREATE TABLE prompts (
  id              TEXT PRIMARY KEY,                     -- ULID, core/ids.py
  name            TEXT NOT NULL,
  node_type       TEXT NOT NULL,                        -- text|image|video|composition
  owner           TEXT,                                 -- 작성자 (Phase 2는 단순 문자열)
  status          TEXT NOT NULL DEFAULT 'draft',        -- draft|reviewing|approved|deprecated
  current_version_id TEXT,                              -- FK to prompt_versions
  tags            TEXT[] NOT NULL DEFAULT '{}',
  imported_from   TEXT,                                 -- prompt_optimizer 경로 (FR-7 멱등성)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT prompts_node_type_chk CHECK (node_type IN ('text','image','video','composition')),
  CONSTRAINT prompts_status_chk CHECK (status IN ('draft','reviewing','approved','deprecated'))
);

CREATE INDEX CONCURRENTLY idx_prompts_node_type ON prompts (node_type);
CREATE INDEX CONCURRENTLY idx_prompts_status ON prompts (status);
CREATE INDEX CONCURRENTLY idx_prompts_tags ON prompts USING GIN (tags);
CREATE UNIQUE INDEX CONCURRENTLY uq_prompts_imported_from
  ON prompts (imported_from) WHERE imported_from IS NOT NULL;
```

### 5.2 신규 테이블 — `prompt_versions`

```sql
CREATE TABLE prompt_versions (
  id                  TEXT PRIMARY KEY,
  prompt_id           TEXT NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  version             INT NOT NULL,                       -- 1, 2, 3, ... per prompt
  body                TEXT NOT NULL,
  declared_variables  JSONB NOT NULL DEFAULT '[]',        -- [{name, role, required}]
  model_default       JSONB,                              -- {provider, model_id} optional 권장
  parent_version_id   TEXT REFERENCES prompt_versions(id),-- F02 분기 계보
  change_note         TEXT,                               -- 사람 또는 F02 산출
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by          TEXT,                               -- "user:..." 또는 "auto:F02"
  UNIQUE (prompt_id, version)
);

CREATE INDEX CONCURRENTLY idx_prompt_versions_prompt_id ON prompt_versions (prompt_id);
CREATE INDEX CONCURRENTLY idx_prompt_versions_parent ON prompt_versions (parent_version_id);
```

`prompts.current_version_id` 의 FK는 `prompt_versions.id` (테이블 생성 후 ALTER로 추가, 순서 의존 회피).

### 5.3 신규 테이블 — `prompt_usages`

```sql
CREATE TABLE prompt_usages (
  id                  TEXT PRIMARY KEY,
  prompt_id           TEXT NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  prompt_version_id   TEXT NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
  style_version_id    TEXT NOT NULL REFERENCES style_versions(id) ON DELETE CASCADE,
  node_id             TEXT NOT NULL,                      -- DAG 안의 node id
  pinned              BOOLEAN NOT NULL DEFAULT FALSE,
  last_run_score      NUMERIC(4,3),                       -- 0.000 ~ 1.000
  last_run_at         TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (style_version_id, node_id)                      -- 한 Style의 한 노드는 하나의 prompt만
);

CREATE INDEX CONCURRENTLY idx_prompt_usages_prompt_id ON prompt_usages (prompt_id);
CREATE INDEX CONCURRENTLY idx_prompt_usages_style_version_id ON prompt_usages (style_version_id);
```

### 5.4 기존 테이블 변경 — `style_versions.dag.nodes[]`

JSONB 안의 schema 변경. 마이그레이션은 다음 3단계:

1. **신규 컬럼 도입 마이그**: `style_versions` JSONB schema에 `prompt_id`, `prompt_version_id`, `prompt_pinned` 필드 허용 (nullable). 기존 데이터에 영향 없음.
2. **online backfill 마이그** (분리, idempotent):
   - 모든 `style_versions` row 순회.
   - 각 노드의 `prompt_template` 으로 prompt 1건 생성 (`status='draft'`, `imported_from='inline:<style_id>:<node_id>'`).
   - `prompt_usages` 1건 생성, `pinned=true` (자동 추종 방지 — 기존 동작 보존).
   - 노드의 `prompt_id`, `prompt_version_id` 채움. `prompt_template` 은 그대로 둠 (롤백 안전성).
3. **deprecation 마이그** (Phase 2 종료 후 6개월):
   - 모든 노드에서 `prompt_template` 필드 제거.
   - 별도 ADR + 사용자 공지.

### 5.5 ER 다이어그램

```
prompts ──< prompt_versions
   │            │
   │            └──< prompt_usages >── style_versions ── runs ── node_executions ── evaluations
   │                                                                                    │
   └──── (prompt-level 분석은 F06 영역)                                                  │
                                                              prompt_usages.last_run_score ←┘
```

---

## 6. API Surface

모든 응답은 snake_case (CLAUDE.md §3.3).

### 6.1 엔드포인트 목록

| Method | Path | 설명 | Auth |
|---|---|---|---|
| `GET` | `/api/prompts` | 검색 (filter: node_type, tags, status, q, limit, offset) | API key |
| `GET` | `/api/prompts/{id}` | 단건 + current_version + 사용처 ≤20건 | API key |
| `POST` | `/api/prompts` | 신규 (status=draft, version=1) | API key |
| `PUT` | `/api/prompts/{id}` | 메타 (name, tags, status). 본문 변경은 §6.4 | API key |
| `POST` | `/api/prompts/{id}/versions` | 본문 변경 = 새 버전 생성 | API key |
| `GET` | `/api/prompts/{id}/versions/{v}` | 특정 버전 (body + declared_variables) | API key |
| `POST` | `/api/prompts/{id}/versions/{v}/promote` | 이 버전을 `current_version_id`로 | API key |
| `GET` | `/api/prompts/{id}/usages?limit=...` | paginated 사용처 (UI §7.2 사이드패널) | API key |
| `POST` | `/api/prompts/{id}/ab` | A/B 비교 실행 트리거 (FR-8) | API key |
| `POST` | `/api/prompts/import-modules` | CLI 가 호출하는 admin 엔드포인트 | API key + admin scope |

### 6.2 응답 예시 — `GET /api/prompts/{id}`

```json
{
  "id": "prm_01J7YK...",
  "name": "Business portrait — formal greeting",
  "node_type": "text",
  "status": "approved",
  "owner": "designer:jiwon",
  "tags": ["portrait", "professional", "korean"],
  "current_version": {
    "id": "pmv_01J7YK...",
    "version": 3,
    "body": "Generate a formal Korean greeting for {name}, the {role}...",
    "declared_variables": [
      {"name": "name",  "role": "person_name", "required": true},
      {"name": "role",  "role": "job_title",   "required": true}
    ],
    "model_default": {"provider": "openai", "model_id": "gpt-5.4"},
    "parent_version_id": "pmv_01J7XX...",
    "change_note": "auto:F02 — 형식적 톤 강화 (retry_guidance: '인사말이 너무 캐주얼함')",
    "created_at": "2026-05-01T03:14:22Z",
    "created_by": "auto:F02"
  },
  "usages": [
    {
      "style_version_id": "stv_01J...",
      "style_name": "비즈니스 포트레이트 v3",
      "node_id": "txt1",
      "pinned": false,
      "last_run_score": 0.84
    }
    // ... ≤20건
  ],
  "usage_count_total": 7,
  "created_at": "2026-04-15T10:00:00Z",
  "updated_at": "2026-05-01T03:14:22Z"
}
```

### 6.3 요청 예시 — `POST /api/prompts/{id}/versions`

```json
{
  "body": "Generate a formal Korean greeting for {name}, the {role}, with concise warmth.",
  "declared_variables": [
    {"name": "name", "role": "person_name", "required": true},
    {"name": "role", "role": "job_title",   "required": true}
  ],
  "change_note": "tone 약화 — 회귀 -0.07 보정",
  "model_default": {"provider": "openai", "model_id": "gpt-5.4"}
}
```

서버 검증:

- `extract_placeholders(body)` 의 결과가 모두 `declared_variables[].name`에 존재 → 아니면 422 `MissingDeclaredVariableError`.
- 본문에 `\\{0\\}` / `\\{x:>10\\}` / `\\{a.b\\}` 같은 패턴 → safe_substitute 검증으로 어차피 무시되지만, 서버가 경고만 (CLAUDE.md §5.5 보호 그대로).

응답: 201 + 신규 `prompt_versions` row.

### 6.4 ETag (낙관적 락)

- `GET /api/prompts/{id}` 응답에 `ETag: W/"<updated_at hash>"` 헤더.
- `PUT /api/prompts/{id}` / `POST /api/prompts/{id}/versions` 시 `If-Match` 헤더 필수.
- 불일치 시 412 `PreconditionFailedError` — UI 가 충돌 알림.

---

## 7. UI / UX

세 화면 + Style Builder 통합 변경.

### 7.1 `/prompts` — Library 메인

- 좌측 필터 패널: `node_type`(checkbox 4개), `status`(approved/draft/reviewing/deprecated), `tags`(autocomplete chip).
- 중앙: 카드 그리드. 카드당 prompt name + node_type 컬러 배지 + tag chips + 사용처 수 + 최근 평균 점수.
- 우상단 버튼: "+ 새 Prompt" → 모달 입력.
- 카드 클릭 → `/prompts/:id`.
- DESIGN_SYSTEM.md §5.3 NodeCard 색상 코드 일관 (`var(--color-node-text)` 등).

### 7.2 `/prompts/:id` — 본문 편집 + 사용처

- 메인: prompt body 편집기 (CodeMirror — 이미 의존성에 있음). placeholder 하이라이트.
- 변수 검증 패널: `declared_variables` 입력 + body 자동 매칭. 누락/미선언 placeholder 즉시 빨간 배지.
- 모델 default 선택: 노드 타입에 맞는 model_profiles에서 선택.
- 사이드패널 (오른쪽): 사용처 ≤20 + 더보기 → paginate.
- 사이드패널 헤더: lifecycle 상태 + "Promote v3 → current" 버튼 (status='approved' 한정).
- 하단 actions: 저장 (Cmd+S) → 새 버전 (Cmd+Shift+S) → A/B 시작 (Cmd+B).

### 7.3 `/prompts/:id/compare?from=v1&to=v2[&ab=...]`

- 좌측: v1 본문 + 우측: v2 본문 (diff 하이라이트).
- 하단: A/B 실행 결과 (이미 trigger한 ab가 있으면).
  - 같은 user_input으로 두 버전 각각의 노드 결과 (이미지/비디오 thumbnail) + 평가 점수 diff.
  - "v2 promote" / "v1 유지" 버튼.

### 7.4 Style Builder 통합 변경

`features/style-builder/PromptEditor.tsx` (Phase 1 §1.8b 결과물)에 변경 추가:

- "Library에서 선택" 버튼 → 모달로 `/prompts` 와 동일한 검색 UI → 선택 시 노드의 `prompt_id` + `prompt_version_id` 채움.
- `prompt_id` 가 채워진 노드는 본문 편집기를 read-only로 표시 + "이 prompt를 Library에서 편집" 링크.
- 처음 prompt를 인라인으로 입력 후 저장 시 다이얼로그: "Library로 추출하시겠습니까? (다른 Style에서도 재사용 가능합니다)" — 예 → POST /api/prompts → 노드 link 갱신.
- `prompt_pinned` 토글 (체크박스): "이 Style은 v3에 고정 (Library에서 promote해도 자동 갱신 안 됨)".

### 7.5 디자인 토큰

- 모든 화면 디자인 토큰만 사용. 임의 hex/px 0건 (CLAUDE.md §5.3 그대로).
- node_type 컬러 배지: `var(--color-node-text)` / `var(--color-node-image)` / `var(--color-node-video)` / `var(--color-node-composition)`.
- 회귀 점수 ≤0.5 → `var(--color-danger)`, 0.5~0.75 → `var(--color-warning)`, ≥0.75 → `var(--color-success)`.

---

## 8. Non-Functional Requirements

### 8.1 성능

| 지표 | 목표 |
|---|---|
| `GET /api/prompts` (1만 건 기준, 10건 페이지) | P95 ≤200ms |
| `GET /api/prompts/{id}` (사용처 20건 포함) | P95 ≤300ms |
| `POST /api/prompts/{id}/versions` | P95 ≤500ms (검증 포함) |
| 검색 인덱스 | `idx_prompts_node_type` (B-tree), `idx_prompts_tags` (GIN) — 모두 CONCURRENTLY |

### 8.2 보안

- API key 인증 (Phase 1과 동일 헤더 `X-Workbench-Key`)
- `import-modules` 엔드포인트는 admin scope (Phase 2 추가 — `WORKBENCH_API_KEY_ADMIN` 별도 변수, `core/config.py`)
- prompt body는 PII 가능성 있음 → 로그에 본문 출력 금지, hash만 (CLAUDE.md §9, B3 패턴 유지)

### 8.3 동시성

- ETag + If-Match 낙관적 락으로 동시 편집 충돌 방지 (§6.4)
- prompt promote는 트랜잭션 단일 — `current_version_id` 갱신은 SELECT FOR UPDATE 후

### 8.4 외부 모델 호출 격리

- `services/prompt_service.py`, `infra/repositories/prompt_repo.py`, `api/prompts.py` 어느 곳에서도 `anthropic`/`openai`/`replicate` import 금지.
- A/B 비교(FR-8)는 RunService 경유 → 기존 adapters 사용.
- 정적 검증: `rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/services/prompt_service.py` → 0건.

### 8.5 마이그레이션 안전성

- Backfill (§5.4 단계 2)은 Style 1만 건 기준 ≤30분 안에 완료. 중단 시 idempotent 재실행 가능 (`imported_from='inline:<style>:<node>'` 중복 검사).
- Backfill 실패 시 새 컬럼 NULL 그대로 → 인라인 호환 모드 작동 (FR-5의 `prompt_id IS NULL` 분기).

---

## 9. Acceptance Criteria

세션 종료 시 아래 모두 통과해야 F05 status='Done'.

- [ ] **AC-1**: 디자이너가 새 Style 만들 때 노드 inspector "Library에서 선택" 버튼으로 prompt 검색·삽입 가능. 인라인 입력 0건도 가능 (회귀 안전).
- [ ] **AC-2**: 한 prompt를 5개 Style이 참조한 상태에서 v3을 promote → `prompt_pinned=false` 4개 Style 의 다음 Run에서 v3 사용. `prompt_pinned=true` 1개 Style 은 이전 버전 유지.
- [ ] **AC-3**: CLI `import_prompts` 1회 실행으로 외부 디렉토리(테스트는 fixture 디렉토리 ≥10개 파일)를 `prompts` 테이블에 import. 재실행 시 중복 0건.
- [ ] **AC-4**: `/prompts/:id` 페이지에서 해당 prompt를 참조하는 Style 사용처 ≥1건 표시 + 사용처 클릭 → Style Builder 이동.
- [ ] **AC-5**: A/B 비교(`POST /api/prompts/{id}/ab`) 1회 실행 → `/prompts/:id/compare` 화면에서 두 버전의 평가 점수 diff 표시.
- [ ] **AC-6**: `mypy backend/src` strict 0건. `ruff check` 0건. 외부 SDK import 정적 검증 0건.
- [ ] **AC-7**: 모든 신규 인덱스가 `postgresql_concurrently=True` (W5 closing). 마이그 review에서 강제.
- [ ] **AC-8**: e2e Playwright 시나리오 1건: `/prompts` 검색 → Style Builder 노드에 삽입 → Run 시작 → 결과 표시 → 평가 점수가 `prompt_usages.last_run_score`에 반영.
- [ ] **AC-9**: golden 회귀 — 본문에 `{name}` placeholder 가진 prompt가 `safe_substitute` 로 치환된 결과가 Phase 1 fixture와 동치.
- [ ] **AC-10**: CLAUDE.md §5 절대 금지 사항 8건 위배 0건 (정적 검증 스크립트 통과).

---

## 10. Test Plan

### 10.1 Unit (`backend/tests/unit/`)

- `services/test_prompt_service.py` — CRUD, 버전 생성, promote, lifecycle 전이
- `domain/test_prompt_validation.py` — declared_variables vs body placeholder 검증
- `domain/test_template.py` — Phase 1 기존 테스트 회귀 (safe_substitute 무영향)
- `infra/repositories/test_prompt_repo.py` — SQLAlchemy 매핑, 사용처 join

### 10.2 Integration (`backend/tests/integration/`)

- `test_prompt_api.py` — POST → PUT → POST versions → promote → GET
- `test_prompt_ab.py` — A/B 트리거 → Run 2개 생성 → SSE 이벤트 → 점수 diff
- `test_prompt_backfill.py` — testcontainers-postgres 위에 Phase 1 fixture Style 5개 → backfill 마이그 적용 → `prompt_usages` 5건 + `prompt_id` 채워짐 검증

### 10.3 Golden (`backend/tests/golden/`)

- `prompts/test_safe_substitute_equivalence.py` — 본문에 `{name}`/`{role}` 있는 prompt 10개 × user_input 5종 → 치환 결과 fixture 동치
- Phase 1 variant_generator / evaluator golden 회귀 그대로 통과 (prompt 본문이 Library 경유로 옮겨가도 출력 동일)

### 10.4 E2E (`frontend/tests/e2e/`)

- `prompt_library.spec.ts`:
  1. `/prompts` 진입 → "+ 새 Prompt" → name/body/declared_variables 입력 → 저장
  2. `/styles/new` brief → 5종 변주 → 1개 선택 → Builder 진입 → 노드 inspector "Library에서 선택" → 방금 만든 prompt 선택
  3. Run 시작 → SSE 이벤트로 결과 표시
  4. `/prompts/:id` 다시 진입 → 사용처 1건 표시 + last_run_score 반영

### 10.5 정적 검증

```bash
# 외부 SDK import 격리
rg "from (anthropic|openai|replicate) import" \
   backend/src/style_workbench/services/prompt_service.py \
   backend/src/style_workbench/infra/repositories/prompt_repo.py \
   backend/src/style_workbench/api/prompts.py
# 결과: 0건

# format_map 회귀 방지 (B3 그대로)
rg "\.format_map\(" backend/src/style_workbench
# 결과: 0건

# CONCURRENTLY 컨벤션 (W5)
rg "create_index" backend/alembic/versions/*prompt* | grep -v "postgresql_concurrently=True"
# 결과: 0건
```

---

## 11. Out of Scope

- prompt_optimizer 자체 자산의 Phase 2 후 운영 정책 (별도 마이그 작업)
- prompt 권한 RBAC (Phase 3)
- prompt 마켓플레이스 / 팀 공유 (Phase 3+)
- 외국어 자동 번역 (Phase 3)
- prompt 의미 임베딩 검색 (Phase 3)
- prompt fork 분기 UI — F02 Optimizer가 자동 생성한 분기를 보여주는 정도까지만. UI에서 사용자가 직접 fork 버튼을 누르는 것은 Phase 3
- prompt GC / 자동 deprecation 정책 (Phase 2 종료 후 데이터 누적 보고 결정 — PRD §10 Risk 2)

---

## 12. Dependencies

### 12.1 사전 조건 (확인됨)

- Phase 1 12건 + B1~B3 적용 (직전 세션 결과)
- DB Alembic 작동 (`backend/alembic/`)
- `domain/prompt/template.py:safe_substitute` 안정 (Phase 1 B3에서 도입)
- `adapters/*` 인터페이스 안정

### 12.2 후속 의존자 (이 feature가 차단)

- **F01 Auto Evaluation Loop** — `prompt_version_id` 발행 인터페이스 필요. F05 W2 종료 후 진입.
- **F02 Prompt Optimizer** — `prompt_versions.parent_version_id` 와 `change_note` 사용. F05 backfill 완료 후 진입.
- **F04 Regression Batch** — 회귀 단위가 prompt_version. F05 인덱스 (idx_prompt_versions_prompt_id) 필요.
- **F06 Analytics** — prompt_usages 데이터 사용.

### 12.3 Phase 1 Deferred

- **W5** (CONCURRENTLY 인덱스) — 본 feature의 첫 마이그레이션부터 강제 (AC-7).
- W1·W2·W3·W4는 본 feature와 무관 (다른 feature 진입 전 closing).

---

## 13. Implementation Phases

| 단계 | 기간 | 산출물 | 출구 검증 |
|---|---|---|---|
| **단계 1** | 3일 | `domain/prompt/entity.py`, `domain/prompt/repo.py` (Protocol), `infra/repositories/prompt_repo.py`, `services/prompt_service.py`, alembic 마이그 (테이블 3종) | unit + integration 통과, mypy strict 0건 |
| **단계 2** | 2일 | `api/schemas/prompts.py`, `api/prompts.py`, `api/deps.py` 추가 | curl 시나리오 5종 통과 (생성→수정→version→promote→link) |
| **단계 3** | 3일 | `/prompts`, `/prompts/:id` UI + Style Builder 통합 변경 | e2e `prompt_library.spec.ts` 통과 |
| **단계 4** | 2일 | `tools/import_prompts.py` CLI + backfill 마이그 | AC-3 통과 (CLI fixture import + 재실행 멱등) |
| **단계 5** | 2일 | A/B 비교 UI + golden + 회귀 검증 | AC-5, AC-8, AC-9, AC-10 통과 |

총 **2주**. 각 단계 종료 시 PR 1건. PR description에 `Closes (Phase 1 deferred): W5` 명시.

---

## 14. 참고

- 부모 PRD: [`../PRD.md`](../PRD.md) §3 Axis A, §5 Feature Index
- 절대 금지 사항: [`/CLAUDE.md`](/CLAUDE.md) §5
- Backend 컨벤션: [`/backend/CLAUDE.md`](/backend/CLAUDE.md) §5.1 (새 API 엔드포인트 추가 절차)
- Phase 1 prompt 인프라: [`/backend/src/style_workbench/domain/prompt/template.py`](/backend/src/style_workbench/domain/prompt/template.py)
- 디자인 토큰: [`/docs/DESIGN_SYSTEM.md`](/docs/DESIGN_SYSTEM.md) §2, §5.3
