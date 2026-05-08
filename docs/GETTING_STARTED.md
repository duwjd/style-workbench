# Getting Started — Style Workbench (Claude Code Edition)

> 이 문서를 그대로 따라하면, **Claude Code와 함께 0에서 Phase 1 첫 end-to-end 동작까지** 도달할 수 있다.
> 각 단계는 "Claude Code에 무엇을 시킬 것인가"를 구체적인 프롬프트와 함께 적었다. 위에서부터 차례대로 따라간다.

---

## 0. 사전 준비 (사람이 직접)

이건 Claude Code가 못 한다. 본인이 먼저 해야 함.

- [ ] **GitHub 저장소** 신규 생성: `style-workbench`
- [ ] 로컬에 clone 후 본 5개 문서(`STYLE_WORKBENCH_PRD.md`, `TECH_STACK.md`, `SYSTEM_ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, `CLAUDE.md`) 복사. 권장 위치: `<repo>/docs/`. `CLAUDE.md`는 **저장소 루트**에 두기 (Claude Code가 자동 인식).
- [ ] 다음 API 키 발급/확보 (3종): **Anthropic** (Claude), **OpenAI** (gpt-5.4 등), **Replicate** (이미지·영상 모델 통합 게이트웨이). 키만 모아두면 됨.
- [ ] Docker Desktop 또는 Colima + 충분한 디스크 (Postgres 컨테이너용 ~1GB).
- [ ] Node 22+, Python 3.12+, uv 0.4+ 설치. npm은 Node와 함께 자동 설치됨. 미설치면 Claude Code에 설치 절차 도움 요청.
- [ ] **운영팀에 자료 요청** (PRD §11) — 이건 코드와 별개로 병행. 도착하기 전에 Claude Code로 골격까지는 다 만들 수 있다.

---

## 1. Phase 1 마스터플랜 (4주)

| 주차 | 목표 | Claude Code 활용 |
|---|---|---|
| 1주차 | 저장소 골격 + 도커 인프라 + DB 스키마 + 첫 마이그레이션 | 디렉토리/패키지 골격 자동 생성, Alembic 초기화, docker-compose 작성 |
| 2주차 | 도메인 + 어댑터 + DAG 엔진 + Variant Generator | TDD 스타일 짝코딩 (테스트 → 구현) |
| 3주차 | API 라우터 + Service + 평가 루프 + FE 골격 | OpenAPI schema 자동 생성, FE API 클라이언트 자동 stub |
| 4주차 | DAG 에디터 + 비교 그리드 + end-to-end 검증 (비즈니스 포트레이트 1개) | UI 컴포넌트 작성, Playwright happy path |

---

## 2. Step 1 — 저장소 골격 (Day 1)

### 2.1 빈 저장소 → 모노레포 골격

저장소 root에서 Claude Code를 띄우고, 첫 프롬프트:

```
@CLAUDE.md @docs/SYSTEM_ARCHITECTURE.md 를 읽고 §13의 "최종 디렉토리 트리"를 그대로 만들어줘.
- backend/ 는 src layout 으로 pyproject.toml + uv.lock 초기화
- frontend/ 는 vite + react + ts 초기화 (pnpm 사용)
- 루트에 docker-compose.yml (postgres 16, backend, frontend) 초안
- .github/workflows/ 에 backend-ci.yml, frontend-ci.yml 스켈레톤
- .gitignore, .env.example
빈 폴더는 .gitkeep으로 남겨. 코드 내용은 아직 채우지 마.
```

### 2.2 Backend 의존성 + 첫 부팅

```
backend/ 에서 TECH_STACK.md §8의 pyproject.toml 을 그대로 적용하고
uv sync 로 락파일 생성. main.py 에 health 엔드포인트 (/health → {"status":"ok"})
하나만 두고, uvicorn 으로 띄워서 localhost:8000/health 가 200 나오는지 검증.
```

### 2.3 Frontend 의존성 + 첫 부팅

```
frontend/ 를 vite + react 19 + ts 로 초기화. TECH_STACK.md §8의 package.json
필수 패키지를 모두 설치. tailwindcss v4 + shadcn/ui 초기 설정 (다크 모드 기본).
DESIGN_SYSTEM.md §2 의 컬러 토큰을 src/styles/tokens.css 에 그대로 작성 후
tailwind.css 에서 @theme 블록으로 import. App.tsx 는 토큰 검증용 임시 화면
(배경색, 텍스트 색, 노드 dot 4개) 만 보여줘.
```

### 2.4 Docker Compose 부팅

```
docker-compose.yml 을 다음 서비스로 채워:
- postgres:16 (DATABASE_URL 환경변수 매칭)
- backend (Dockerfile.dev 로 hot reload)
- frontend (vite dev server)
.env.example 에 CLAUDE.md §8 키 모두 추가.
docker compose up 한 번에 다 뜨는지 검증해줘.
```

**1주차 끝 → 체크포인트**:
- [ ] `docker compose up` 으로 3개 서비스 정상 기동
- [ ] backend `/health` 200, frontend 빈 화면 + 디자인 토큰 확인
- [ ] 마이그레이션 디렉토리 (`backend/alembic/`) 초기화

---

## 3. Step 2 — DB 스키마 + 마이그레이션 (Day 2~3)

```
@docs/SYSTEM_ARCHITECTURE.md §4 의 SQL을 기준으로 SQLAlchemy 2.0 async 모델을
backend/src/style_workbench/infra/db/models/ 에 작성해줘.
- 각 테이블당 한 파일 (style.py, run.py, evaluation.py, test_set.py, model_profile.py, export.py)
- ULID PK 는 core/ids.py 의 helper 사용
- JSONB 필드는 pydantic dataclass 와 매핑되도록 type 힌트 명시
다 끝나면 alembic revision --autogenerate 로 첫 마이그레이션 생성.
docker compose 의 postgres 에 적용 후 \d 로 테이블 검증.
```

**검증 포인트**: `docker exec -it <postgres> psql -U workbench -c "\dt"` 로 7개 테이블이 떠야 함.

---

## 4. Step 3 — 도메인 + 어댑터 (Week 2)

이 주는 **TDD 권장**. Claude Code가 가장 잘하는 영역.

### 4.1 Domain (style/dag/variables)

```
domain/style/entity.py 에 Style, Node, Edge, NodeType, ModelRef dataclass 작성.
domain/style/dag.py 에 위상정렬, 사이클 감지 함수.
domain/style/variables.py 에 placeholder 추출/검증.

먼저 tests/unit/domain/test_dag.py 를 작성해줘:
- 사이클이 없는 DAG → 위상정렬 결과 검증
- 사이클이 있는 DAG → DagCycleError 발생
- 빈 DAG → 빈 list
- 단일 노드 → 그 노드 하나
그다음 dag.py 를 구현. pytest 로 모두 그린 되어야 함.
```

### 4.2 ModelAdapter 인터페이스 + Claude / OpenAI 어댑터

```
adapters/base.py 의 ModelAdapter ABC 와 ModelInput/ModelOutput Pydantic 모델 작성.
그다음 adapters/claude.py — anthropic SDK 사용해 messages.create wrap.
adapters/openai.py — openai SDK 사용해 chat completions wrap.
각 어댑터는 cost_estimate(model_id, input) 도 구현. (단가표는 core/pricing.py 분리)

테스트는 tests/unit/adapters/test_claude.py 에 httpx mock_transport 로
실제 호출 안 하고 응답 파싱만 검증.
```

### 4.3 Replicate 어댑터 (이미지·영상 통합)

```
adapters/replicate.py — replicate SDK 사용해 ModelAdapter 구현.
SYSTEM_ARCHITECTURE.md §3.1 의 ReplicateAdapter 시그니처를 따라:
  - replicate.predictions.async_create(model=model_id, input=...)
  - 비동기 polling (interval 2s, max 5분, 그 이후 timeout 에러)
  - 완료 후 output URL(provider URL)을 DB에 저장 → FE에 반환 → 화면 표시 및 다운로드
  - estimate_cost(model_id, input) 은 core/pricing.py 의 단가표 lookup
지원 model_id 예: "google/nano-banana-pro", "kuaishou/kling-v2.5-turbo-pro",
  "bytedance/seedance-1.5-pro", "runway/gen3" 등.
type 결정(image/video)은 model_profiles 테이블에서 lookup.

테스트 tests/unit/adapters/test_replicate.py 는 replicate SDK 를 mock 하고,
prediction lifecycle (created → processing → succeeded) 을 시뮬레이션.

REPLICATE_API_TOKEN 미설정 시 NotConfiguredError. 환경별로 토큰 분리.
```

---

## 5. Step 4 — DAG Engine + Variant Generator (Week 2 후반)

### 5.1 DAG Executor

```
engine/executor.py 의 DagExecutor 작성. SYSTEM_ARCHITECTURE §3.2 의 시그니처를 따름.
node_runners/ 에 type별 러너 (text/image/video/composition).
- 노드별로 ModelAdapter 호출
- 출력은 provider URL을 그대로 반환 (FE에서 표시 및 다운로드)
- node_executions 테이블에 진행 상황 persist

tests/integration/engine/test_executor.py 에 docker-compose 띄운 상태로
2-노드 DAG (text → image) 1개를 stub adapter 로 완주시키는 통합 테스트.
```

### 5.2 Variant Generator

```
prompts/variant_generator.py 에 system prompt 작성.
입력: brief (concept, vertical, tone, step_composition, input_kinds, n)
출력: 5개 Style JSON (각 DAG 포함)

services/variant_service.py 의 generate(brief) 메서드:
- system prompt 조립
- claude.call(model="claude-sonnet-4-6", ...)
- 응답 파싱 + DAG 검증

tests/golden/variants/biz_portrait/ 에 input.json + expected_schema.json
저장. 회귀: 각 변주가 schema 통과 + DAG 사이클 없음 + variables 일관.
```

---

## 6. Step 5 — API + Service 레이어 (Week 3 전반)

```
api/styles.py, api/variants.py, api/runs.py, api/evaluations.py 작성.
- 각 라우터는 얇게 (CLAUDE.md §12.1)
- Pydantic 입출력은 api/schemas/ 에 분리
- services/ 가 실제 유스케이스 처리
- 라우터 응답은 snake_case (FE 인터셉터가 변환)

검증: backend 띄우고 curl 로
- POST /api/styles  (Style 메타 생성)
- POST /api/variants  (5종 변주)
- POST /api/runs  (실행)
- GET  /api/runs/{id}  (상태)
모두 200/201 와 정합 응답이 와야 함.
```

---

## 7. Step 6 — Step Evaluator + 재시도 루프 (Week 3 후반)

```
prompts/evaluator_text.py / evaluator_image.py / evaluator_video.py 작성.
"프롬프트 옵티마이저"의 step별 md/02_evaluator_prompts.md 를 시드로 활용.
원본 prompt는 절대 노출하지 않고 brief 요약만 포함.

services/evaluation_service.py 의 evaluate(node_execution_id):
- 노드 type 별 prompt 로드
- claude(opus-4-6, vision) 호출
- 차원별 점수 + retry_guidance 파싱
- DB persist

engine/retry.py 의 RetryPolicy:
- 평가 FAIL 시 retry_modifier 적용 (도메인 사전)
- 같은 노드 ≤ 3회 재시도, 초과 시 run.status='failed'

tests/golden/eval/ 에 결과 fixture (이미지 sample + 기대 점수 ±0.05) 회귀.
```

---

## 8. Step 7 — Frontend 골격 + DAG 빌더 (Week 4)

### 8.1 라우팅 + Layout

```
React Router 7 declarative mode 로 라우팅 설정.
- /styles, /styles/new, /styles/:id, /runs/:runId
_layout.tsx 에 상단바 + 다크 토글 + 사용자 영역 (Phase 1은 단순).
shadcn/ui add 로 Button/Input/Dialog/Tabs/ScrollArea/Toast 추가.
```

### 8.2 Style List + Brief Form

```
features/styles/StyleList.tsx — TanStack Query 로 GET /api/styles, 카드 그리드.
features/variants/BriefForm.tsx — RHF + Zod schema, /styles/new 에서 브리프 입력.
제출 시 POST /api/variants → 응답을 stores/styleStore 에 저장 후
/styles/:id 빌더 화면으로 이동.
```

### 8.3 DAG Builder (React Flow)

```
features/style-builder/StyleBuilder.tsx 를 @xyflow/react 로 작성.
- 좌측 NodePalette (드래그 추가)
- 중앙 Canvas (custom node 4종: TextNode, ImageNode, VideoNode, CompositionNode)
- 우측 Inspector (선택 노드의 Prompt/Model/Variables 편집)
- 키보드 단축키: Cmd+S 저장, Cmd+Enter 실행, Backspace 삭제

DESIGN_SYSTEM.md §5.3 의 NodeCard 디자인을 정확히 따름.
노드 타입별 색상은 var(--color-node-*).
```

### 8.4 Comparison Grid + Verdict

```
features/comparison/ComparisonGrid.tsx — 5×N 그리드.
- 각 셀 MediaPreview + EvalScoreBadge
- 셀 호버: 액션 메뉴 (확대, 재실행, 부분 수정)
- 셀 선택: 우측 인스펙터 (차원별 점수, raw response, prompt)

features/comparison/VerdictPanel.tsx — 채택/기각/재실행.
SSE 구독 (api/runs.ts 에 EventSource 래퍼) 으로 실시간 업데이트.
```

### 8.5 End-to-end

```
Playwright 시나리오 1개:
1) /styles/new 로 가서 brief 입력 (concept="공포 키링 광고", steps=text+image+video)
2) 5종 변주가 30초 안에 그려지는지
3) 1개 선택 후 샘플 사진 업로드 → 실행 시작
4) Comparison Grid 에 결과가 점진적으로 채워지는지
5) "채택" 버튼 누르고 Style status='approved' 가 되는지

backend mock 모드로 fast e2e 1번 + 실제 API 호출 e2e 1번 (skip 가능).
```

---

## 9. Phase 1 끝 — 출구 기준

- [ ] 비즈니스 포트레이트 Style 1개를 디자이너가 6시간 내로 만들 수 있다
- [ ] 5종 시안 중 1개 이상 채택되는 비율 ≥ 60%
- [ ] backend / frontend CI 그린, e2e happy path 1개 통과
- [ ] 모든 외부 모델 호출이 ModelAdapter 를 통과
- [ ] golden 회귀 (variant 생성, 평가) 안정

---

## 10. Claude Code 활용 베스트 프랙티스

### 10.1 좋은 프롬프트의 모양

- **항상 문서 레퍼런스 포함**: `@CLAUDE.md @docs/SYSTEM_ARCHITECTURE.md §3` 처럼 정확한 위치를 가리키기.
- **결과의 형태를 먼저 말하기**: "테스트 먼저 작성 → 구현" / "타입만 만들고 구현 보류" / "진단만, 코드 변경 X".
- **합격 기준 명시**: "pytest -k golden 통과 + mypy 0 errors + ruff 0 violations".
- **변경 범위 못박기**: "domain/style/ 안에서만, infra 건드리지 마".

### 10.2 위험한 패턴 (피하기)

- ✗ "전체 프로젝트를 한 번에 만들어줘" — 단계 잘게 쪼개기
- ✗ 새 라이브러리를 즉흥적으로 추가 — TECH_STACK.md 에 없으면 ADR 먼저
- ✗ 문서를 안 읽힌 채로 시키기 — 항상 `@` 첨부 또는 CLAUDE.md 의 자동 컨텍스트 활용
- ✗ 테스트 없이 큰 모듈 생성 — 도메인/엔진은 항상 TDD

### 10.3 Claude Code 슬래시 명령 활용 (이 프로젝트 컨텍스트)

- `/init` — 처음 한 번, 저장소를 스캔해 CLAUDE.md 보강 (이미 만든 CLAUDE.md를 이어서 쓰면 더 좋음)
- `/review` — PR 단위 리뷰
- `/security-review` — 외부 API 호출, 인증 부분에 한 번씩
- 커스텀 슬래시 명령을 `.claude/commands/` 에 정의해두면 좋음:
  - `/new-adapter <provider>` — 새 ModelAdapter 스캐폴드
  - `/new-node <type>` — 새 노드 타입 추가 절차 자동화

### 10.4 프롬프트 회귀 테스트 패턴 (Variant / Evaluator 튜닝 시)

```
@prompts/variant_generator.py 의 system prompt 를 다음 의도로 개선해줘:
- "톤 가이드"가 5개 변주 모두에 명확히 반영되게
- 각 변주가 서로 충분히 달라지도록 (cosine similarity ≤ 0.7 가이드)

수정 후 tests/golden/variants/biz_portrait/ 의 회귀를 돌려봐.
점수 변동이 ±0.05 초과하는 변주가 있으면 그 변주의 fixture 를 어떻게
업데이트해야 하는지 제안해줘 (자동 업데이트는 하지 말고 진단만).
```

---

## 11. "지금 당장" Claude Code에 시킬 첫 프롬프트 (복사해 쓰기)

저장소 root 에서 Claude Code 시작 후:

```
이 저장소는 빈 상태야. /Users/<...>/프롬프트 옵티마이저/ 폴더에 있는 다음 5개 문서를
docs/ 로 복사해줘:
  STYLE_WORKBENCH_PRD.md, TECH_STACK.md, SYSTEM_ARCHITECTURE.md,
  DESIGN_SYSTEM.md, CLAUDE.md
복사한 뒤 CLAUDE.md 는 저장소 루트에도 둬 (Claude Code 자동 인식용).
그리고 GETTING_STARTED.md 의 §2.1 부터 §2.4 까지 그대로 수행해.
모든 단계가 끝나면 README.md 를 쓰는데, 다음을 포함해:
  - 프로젝트 한 줄 소개
  - 사전 요구사항 (Docker, Node, Python, uv, pnpm 버전)
  - 개발 시작 커맨드 (docker compose up + npm run dev)
  - 폴더 구조 트리 (간략)
  - 자세한 가이드는 docs/ 안에 있다고 명시
끝나면 어디까지 했는지 보고만 해. 한 번에 너무 많이 쓰지 말고 단계별로 PR 단위로 끊어서.
```

---

## 12. 자주 막히는 곳 — 미리 알려드림

| 막힘 | 해결 |
|---|---|
| Tailwind v4 + shadcn/ui 통합이 익숙치 않음 | 공식 가이드: shadcn CLI 가 v4 variant 자동 처리. `npx shadcn@latest init` 시 v4 옵션 선택 |
| React Flow의 custom node 가 드래그 안 됨 | inner element 에 `nodrag` / `nopan` 클래스 명시 |
| Anthropic SDK 가 stream 모드에서 JSON 파싱 깨짐 | non-stream + JSON mode 강제 (`response_format`) |
| Replicate prediction이 영원히 starting 상태 | model_id 가 잘못됐거나(404), input schema 미스매치. 어댑터에서 첫 polling 응답의 status/error를 로깅 |
| Replicate 영상 생성 응답 URL이 짧은 시간 후 만료 | provider URL은 임시적임. FE에서 결과를 확인하면 바로 로컬 저장 권장. DB의 `artifact_url`은 참조용으로만 보관 |
| asyncpg + SQLAlchemy 트랜잭션 hang | 같은 세션에서 `await` 누락된 곳이 있는지 점검. mypy + ruff 가 잡아줌 |
| Variant 생성 결과가 5개 미만 | system prompt 마지막에 "exactly 5 variants" + JSON array length validation 코드에서 retry 1회 |

---

## 13. 한눈에 — Today / This Week / This Month

**Today**:
- 저장소 만들기 + 5개 문서 복사 + Claude Code 첫 부팅
- §2.1 Step 실행

**This week (1주차)**:
- §2 ~ §3 (인프라 + DB)
- 운영팀에 자료 요청 발송

**This month (Phase 1)**:
- §4 ~ §8 (도메인 → 엔진 → API → FE → e2e)
- 비즈니스 포트레이트 Style 1개 end-to-end 검증
- Time-to-Style 측정 (목표 6h)

이 순서대로 가면 4주에 Phase 1 출구를 통과할 수 있다.

---

## 14. 다음 단계 — 지금 바로 시작할 작업 (Week 2~4)

> 이 체크리스트는 §3~§8의 Claude Code 프롬프트 템플릿을 **실제 작업 순서와 검증 명령**으로 변환한 것이다. 각 항목마다 호출할 서브에이전트, 확인할 파일, 완료 확인 명령을 함께 적었다.

---

### 14.1 Step 3 — 도메인 + 어댑터 (§4 해당)

**서브에이전트**: `backend-engineer` (도메인) → `adapter-specialist` (어댑터)

**시작 전 확인 파일**:
- `docs/SYSTEM_ARCHITECTURE.md` §2, §3
- `backend/src/style_workbench/domain/` (현재 placeholder 상태)
- `backend/src/style_workbench/adapters/CLAUDE.md`

**작업 내용**: DAG 엔티티/위상정렬/변수 검증 + Claude/OpenAI/Replicate 어댑터 구현.

**완료 확인 명령**:
```bash
uv run pytest tests/unit/domain/ -v
# 결과: DAG 사이클 감지, 빈 DAG, 단일 노드, 변수 참조 테스트 모두 통과

uv run pytest tests/unit/adapters/ -v
# 결과: Claude/OpenAI/Replicate 어댑터 mock 테스트 통과

uv run mypy backend/src --no-error-summary | grep "error:"
# 결과: 0건

# adapters/ 외부에서 SDK 직접 호출 없는지 확인
rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/services backend/src/style_workbench/api
# 결과: 0건
```

---

### 14.2 Step 4 — DAG 엔진 + Variant Generator (§5 해당)

**서브에이전트**: `backend-engineer` (엔진) → `prompt-engineer` (Variant Generator 프롬프트)

**시작 전 확인 파일**:
- `docs/SYSTEM_ARCHITECTURE.md` §3.2 (DagExecutor 시그니처)
- `backend/src/style_workbench/engine/` (현재 상태)
- `backend/src/style_workbench/prompts/CLAUDE.md`

**작업 내용**: DagExecutor + node_runners 4종 + Variant Generator system prompt + golden 회귀 fixture.

**완료 확인 명령**:
```bash
uv run pytest tests/integration/engine/ -v
# 결과: 2-노드 DAG stub adapter 완주 테스트 통과

uv run pytest tests/golden/variants/ -v
# 결과: biz_portrait 변주가 schema 통과 + DAG 사이클 없음 + variables 일관

# Variant Generator가 adapters/ 외부에서 직접 SDK 호출하지 않는지 확인
rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/services backend/src/style_workbench/engine
# 결과: 0건
```

---

### 14.3 Step 5 — API + Service 레이어 (§6 해당)

**서브에이전트**: `backend-engineer`

**시작 전 확인 파일**:
- `backend/CLAUDE.md` §5.1 (새 API 엔드포인트 추가 순서)
- `backend/src/style_workbench/api/` (현재 라우터 placeholder 현황)
- `backend/src/style_workbench/services/` (현재 서비스 placeholder 현황)

**작업 내용**: styles/variants/runs/evaluations 라우터 + 서비스 레이어 구현.

**완료 확인 명령**:
```bash
# backend 기동 상태에서
curl -s http://localhost:8000/health | python3 -m json.tool
# 결과: {"status": "ok"}

curl -s -X POST http://localhost:8000/api/styles \
  -H "Content-Type: application/json" \
  -d '{"name":"테스트","concept":"초상화"}' | python3 -m json.tool
# 결과: 201 Created + id 필드 포함 응답

uv run ruff check backend/src --select E,F,I
# 결과: 0 violations

# 라우터에서 HTTPException 직접 raise 없는지 확인
rg "raise HTTPException" backend/src/style_workbench/api
# 결과: 0건
```

---

### 14.4 Step 6 — Step Evaluator + 재시도 루프 (§7 해당)

**서브에이전트**: `prompt-engineer` (evaluator 프롬프트) → `backend-engineer` (evaluation_service, retry 로직)

**시작 전 확인 파일**:
- `backend/src/style_workbench/prompts/CLAUDE.md` §2 (자기확증편향 차단 규칙)
- `backend/src/style_workbench/prompts/` (현재 파일 현황)

**작업 내용**: evaluator_text/image/video.py + evaluation_service + RetryPolicy.

**완료 확인 명령**:
```bash
uv run pytest tests/golden/eval/ -v
# 결과: 이미지 fixture 점수 ±0.05 이내 통과

# evaluator 프롬프트 모듈에 원본 prompt 참조 없는지 확인
rg "prompt_resolved|raw_response" backend/src/style_workbench/prompts/
# 결과: 0건

# evaluator temperature가 낮은지 확인
rg "temperature" backend/src/style_workbench/prompts/
# 결과: 0.0~0.2 범위 값만 존재해야 함
```

---

### 14.5 Step 7 — Frontend 골격 + DAG 빌더 (§8 해당)

**서브에이전트**: `frontend-engineer`

**시작 전 확인 파일**:
- `frontend/CLAUDE.md` (절대 규칙, 토큰, 작업 순서)
- `docs/DESIGN_SYSTEM.md` §5.3 (NodeCard 디자인)
- `frontend/src/` (현재 구조)

**작업 내용**: React Router 7 라우팅 + StyleList + BriefForm + StyleBuilder (React Flow) + ComparisonGrid.

**완료 확인 명령**:
```bash
npm run --prefix frontend tsc -- --noEmit
# 결과: 0 errors

npm run --prefix frontend lint
# 결과: 0 violations

# 임의 색상값 직접 사용 확인
rg "bg-\[#|style=\{.*color.*#" frontend/src/
# 결과: 0건 (디자인 토큰만 사용)

# 노드 색상 코딩 일관성 확인
rg "var(--color-node-)" frontend/src/
# 결과: text/image/video/composition/input/output 토큰만 참조
```

---

### 14.6 End-to-End 검증 + 출구 기준 확인 (§8.5 + §9 해당)

**서브에이전트**: `code-reviewer` (최종 검토)

**시작 전 확인 파일**:
- `docs/GETTING_STARTED.md` §9 (Phase 1 출구 기준)
- `backend/CLAUDE.md` §12 (작업 종료 체크리스트)

**작업 내용**: Playwright e2e 시나리오 1개 + Phase 1 출구 기준 전체 검증.

**완료 확인 명령**:
```bash
# 전체 유닛 테스트
uv run pytest tests/unit/ -v --tb=short
# 결과: 전체 통과

# 통합 테스트 (docker compose up 상태 필요)
uv run pytest tests/integration/ -v --tb=short
# 결과: 전체 통과

# Playwright e2e (frontend + backend 모두 기동 필요)
npm run --prefix frontend exec -- playwright test --reporter=line
# 결과: happy path 시나리오 통과

# 최종 레이어 위반 스캔
rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/api backend/src/style_workbench/services
# 결과: 0건
```

---

### 작업 순서 요약

```
Day 4~5   → 14.1 도메인 + 어댑터 (backend-engineer → adapter-specialist)
Day 6~7   → 14.2 DAG 엔진 + Variant Generator (backend-engineer → prompt-engineer)
Day 8~9   → 14.3 API + Service 레이어 (backend-engineer)
Day 10~11 → 14.4 Step Evaluator + 재시도 루프 (prompt-engineer → backend-engineer)
Day 12~14 → 14.5 Frontend 골격 + DAG 빌더 (frontend-engineer)
Day 15    → 14.6 End-to-End 검증 (code-reviewer)
```
