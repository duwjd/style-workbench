# Tech Stack 결정 — Style Workbench

> PRD §5(아키텍처)에서 정의한 "별도 admin 프로젝트"의 기술 스택 결정 문서. 모든 버전은 2026-04 기준 최신 안정판으로 정렬했고, 구성요소 간 호환성을 검증했다.

---

## 0. 결정 원칙

1. **prompt_optimizer 자산 재사용 원칙** — 가능한 부분은 같은 스택으로 통일하여 코드/지식 재사용 비용을 줄인다 (FastAPI, React, TS, Tailwind, Zustand 유지).
2. **DB 도입** — JSON 파일 기반에서 PostgreSQL로 이행. 동시 실행/비교/평가 이력 보존 부담이 prompt_optimizer 수준을 넘는다.
3. **DAG가 first-class** — 노드 그래프 편집 UI는 자체 구현하지 않고, 검증된 라이브러리(React Flow / XY Flow) 활용.
4. **Phase 1은 단일 노드, Phase 2부터 분산** — 큐/워커는 Phase 2에서 도입. Phase 1은 FastAPI 단일 프로세스 안에서 백그라운드 태스크로 충분.
5. **충돌 없는 최신 안정판 선택** — bleeding edge는 피하고, 메이저 버전이 안착된 라이브러리 사용.

---

## 1. Frontend

| 영역 | 기술 | 버전 | 채택 이유 |
|---|---|---|---|
| 프레임워크 | **React** | 19.x | prompt_optimizer와 동일. 19에서 안정화된 actions / use() / Suspense 흐름 활용 |
| 언어 | **TypeScript** | 5.6+ | 타입 시스템 안정. const type parameters, satisfies 연산자 활용 |
| 빌드 도구 | **Vite** | 6.x | prompt_optimizer 8 → Vite 6으로 통일 (Rolldown 안정화). HMR/ESM 우수 |
| 스타일링 | **Tailwind CSS** | 4.x | prompt_optimizer와 동일. v4 Oxide 엔진 + CSS 변수 기반 |
| 컴포넌트 | **shadcn/ui** | latest (Tailwind v4 호환) | 카피-앤-페이스트 방식. Radix UI 기반 접근성 보장. 디자이너 커스터마이즈 자유 |
| 아이콘 | **lucide-react** | 0.4xx | prompt_optimizer와 동일 |
| 라우팅 | **React Router** | 7.x | declarative mode 사용 (Remix 통합 모드 X). prompt_optimizer 호환 |
| 클라이언트 상태 | **Zustand** | 5.x | prompt_optimizer와 동일. 슬라이스 패턴 |
| 서버 상태 | **TanStack Query** | 5.x | API 캐싱/리페치/낙관적 업데이트. React 19 호환 |
| 폼 | **React Hook Form** + **Zod** | 7.x / 3.x | 컨트롤드 입력 비용 최소화 + 스키마 검증 |
| **DAG 에디터** | **@xyflow/react (React Flow v12)** | 12.x | de-facto 표준 노드 에디터. React 19 지원, 커스텀 노드/엣지 타입 |
| HTTP 클라이언트 | **axios** | 1.x | prompt_optimizer 인터셉터 패턴(snake↔camel) 재사용 |
| 비디오 플레이어 | **media-chrome** + 네이티브 `<video>` | latest | 가벼움. 시안 비교 그리드에서 N개 동시 재생 |
| 테스트 | **Vitest** + **@testing-library/react** + **Playwright** | latest | unit + E2E 분리 |
| 린트/포맷 | **ESLint 9** + **Prettier 3** | latest | flat config |

### 호환성 검증

- **React 19 + TanStack Query v5**: 공식 호환 (v5.59+).
- **React 19 + React Flow v12**: v12.4+에서 React 19 공식 지원.
- **Tailwind v4 + shadcn/ui**: 2025년 1분기부터 shadcn CLI가 Tailwind v4 변형 제공.
- **React Router 7 + React 19**: 공식 지원.
- **Vite 6 + React 19**: `@vitejs/plugin-react` 4.3+ 호환.

---

## 2. Backend

| 영역 | 기술 | 버전 | 채택 이유 |
|---|---|---|---|
| 언어 | **Python** | 3.12.x | typing 안정성, PEP 695 generics, asyncio 성능 개선 |
| 웹 프레임워크 | **FastAPI** | 0.115+ | prompt_optimizer와 동일. Pydantic v2 기반, async-native |
| ASGI 서버 | **Uvicorn** | 0.30+ | 개발용. 운영은 Gunicorn + UvicornWorker |
| 데이터 검증 | **Pydantic** | 2.9+ | FastAPI 기본. Pydantic v2 의 모델 dump/serialize 활용 |
| ORM | **SQLAlchemy** | 2.0 async | 비동기 세션, async/await 흐름 통일 |
| DB 드라이버 | **asyncpg** | 0.29+ | PostgreSQL 비동기 최고 성능 |
| 마이그레이션 | **Alembic** | 1.13+ | SQLAlchemy 표준 |
| 데이터베이스 | **PostgreSQL** | 16.x | JSONB(DAG 저장), pg_trgm(검색), 안정성 |
| AI SDK (Claude) | **anthropic** | 0.40+ | prompt_optimizer와 동일. async 클라이언트. Variant Generator + Step Evaluator 전용 |
| AI SDK (OpenAI) | **openai** | 1.50+ | gpt-5.4 등 텍스트 모델 호출 (텍스트 단계 전용) |
| AI SDK (Replicate) | **replicate** | 0.34+ | **이미지/영상 모델 통합 호출** — nano-banana-pro, kling, seedance, runway, sora 등을 단일 SDK로 |
| HTTP 클라이언트 | **httpx** | 0.27+ | 기타 외부 호출, async 지원 |
| 큐 (Phase 2) | **arq** | 0.26+ | async-native Redis 큐. Celery보다 가볍고 FastAPI와 궁합 좋음 |
| 캐시 (Phase 2) | **Redis** | 7.x | arq + 결과 캐시 |
| 로깅 | **structlog** | 24.x | 구조화된 로그, JSON 출력 |
| 텔레메트리 | **OpenTelemetry** SDK | 1.27+ | trace/span. Phase 2부터 |
| 테스트 | **pytest** + **pytest-asyncio** + **httpx** | latest | async 테스트 표준 |
| 의존성 관리 | **uv** | 0.4+ | pip보다 10~100배 빠른 패키저. lockfile 안정성 |
| 린트/포맷 | **Ruff** | 0.6+ | flake8/black/isort 통합. 압도적으로 빠름 |
| 타입 체커 | **mypy** | 1.11+ | strict 모드 |

### 호환성 검증

- **FastAPI 0.115 + Pydantic 2.9 + SQLAlchemy 2.0 async**: 공식 지원 매트릭스 안.
- **Python 3.12 + asyncpg 0.29**: 정식 지원.
- **arq + Redis 7**: 공식 호환.
- **Anthropic SDK 0.40+**: Claude Sonnet 4.6, Opus 4.6, Haiku 4.5 모두 지원.

---

## 3. AI 모델 / 외부 API

호출 경로는 **세 종류**로 좁힌다. 이미지·영상은 모두 Replicate를 단일 게이트웨이로 사용해 SDK 의존성을 줄이고, prompt_optimizer가 이미 갖고 있는 `replicate_model_id` 시드 자산을 그대로 재사용한다.

| 호출 경로 | SDK | 사용 모델 (예시) | 비고 |
|---|---|---|---|
| **Anthropic 직접** | `anthropic` | `claude-sonnet-4-6`, `claude-opus-4-6` | Variant Generator + Step Evaluator. 두 역할에만 한정 |
| **OpenAI 직접** | `openai` | `gpt-5.4` 등 텍스트 모델 | Style의 text_generation 노드 |
| **Replicate 경유** | `replicate` | `google/nano-banana-pro`, `kuaishou/kling-v2.5-turbo-pro`, `bytedance/seedance-1.5-pro`, `runway/gen3`, 기타 | **모든 이미지·영상 모델** |

| 단계 | 호출 경로 | 모델 |
|---|---|---|
| Variant Generator | Anthropic 직접 | `claude-sonnet-4-6` |
| Step Evaluator (Vision) | Anthropic 직접 | `claude-opus-4-6` |
| 텍스트 단계 실행 | OpenAI 직접 | `gpt-5.4` (Style이 텍스트 단계를 갖는 경우) |
| 이미지 단계 실행 | Replicate | `google/nano-banana-pro` 등 |
| 비디오 단계 실행 | Replicate | `kuaishou/kling-v2.5-turbo-pro` 등 |
| (확장) 다른 이미지/영상 모델 | Replicate | prompt_optimizer 모델 프로파일 8종 그대로 |

### Replicate를 단일 게이트웨이로 쓰는 이유

1. **단일 SDK + 단일 인증** — Google / Kuaishou / ByteDance / Runway 각자 다른 SDK·키를 직접 다루지 않음.
2. **공통 polling 패턴** — Replicate Predictions API가 모두 `create → poll → completed` 동일 흐름. 어댑터 하나로 통일.
3. **prompt_optimizer 자산 즉시 재사용** — 8개 모델 프로파일이 이미 `replicate_model_id` 필드를 갖고 있다.
4. **모델 추가 비용 최소화** — 새 이미지/영상 모델은 model_id 한 줄만 등록.

### Vendor SDK 추상화

세 가지 호출 경로를 **`ModelAdapter` 인터페이스**로 감싼다 (architecture 문서 §3 참고). 어댑터는 단 3개로 끝.

```
ModelAdapter (ABC)
├── ClaudeAdapter      # Anthropic SDK — Variant gen, Evaluation 전용
├── OpenAIAdapter      # OpenAI SDK    — Text generation 단계
└── ReplicateAdapter   # Replicate SDK — 모든 이미지·영상 단계 (모델은 model_id 로 전환)
```

---

## 4. 인프라 & 운영

| 영역 | 기술 | 채택 이유 |
|---|---|---|
| 컨테이너 | **Docker** + **Docker Compose** | 개발/Phase 1 배포. backend / frontend / postgres / redis 한 번에 |
| CI | **GitHub Actions** | 린트/타입체크/테스트/이미지 빌드 |
| 배포 (Phase 1) | 단일 EC2 또는 사내 서버 + docker compose | 디자이너 소수만 사용, 트래픽 낮음 |
| 배포 (Phase 2+) | **Kubernetes** 또는 **ECS** | 워커 확장 필요 시 검토 |
| 시크릿 관리 | `.env` (개발) → **AWS Secrets Manager** (운영) | API 키 다수 |
| 모니터링 (Phase 2) | **Grafana** + **Loki** + **Tempo** | OTel 기반 |

---

## 5. 충돌 가능성 점검 — 종합

| 잠재 충돌 | 검증 결과 |
|---|---|
| Tailwind v4 + 기존 prompt_optimizer Tailwind v4 | ✓ 동일 버전 |
| React 19 + React Flow v12 | ✓ v12.4+ 공식 지원 |
| FastAPI + SQLAlchemy 2.0 async | ✓ 공식 권장 패턴 |
| asyncpg + 트랜잭션 | ✓ SQLAlchemy 2.0 async 세션이 처리 |
| arq + FastAPI BackgroundTasks | Phase 1은 BackgroundTasks, Phase 2에서 arq로 마이그레이션 (둘 동시 사용 X) |
| Anthropic / OpenAI / Replicate SDK 동시 사용 | ✓ ModelAdapter로 격리. 각 SDK는 어댑터 안에서만 import |
| Replicate SDK + httpx async | ✓ replicate 0.34+는 async 지원, polling은 어댑터 내부에서 처리 |
| React Hook Form + Zod + shadcn/ui Form | ✓ shadcn/ui Form 컴포넌트가 RHF + Zod 표준 통합 |

---

## 6. 버전 잠금 정책

- **major**: lockfile에 명시 (frontend: package.json + package-lock.json, backend: pyproject.toml + uv.lock)
- **minor/patch**: lockfile만 잠그고 `^` 허용
- **API SDK (anthropic, openai)**: minor lock — 모델 변경/응답 schema 변경 영향 큼

---

## 7. 결정 요약 (한 문장씩)

- **Frontend**: React 19 + TS 5.6 + Vite 6 + Tailwind v4 + shadcn/ui + Zustand + TanStack Query + **React Flow v12 (DAG)**
- **Backend**: Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 async + PostgreSQL 16 + Anthropic/OpenAI/**Replicate** SDK + **arq + Redis (Phase 2)**
- **인프라**: Docker Compose → (Phase 2) K8s, GitHub Actions
- **모델 호출**: ModelAdapter 인터페이스 3개(Claude/OpenAI/Replicate)로 격리. **이미지·영상은 Replicate 단일 경로**, 텍스트는 OpenAI, 평가/변주는 Anthropic. Variant Generator(Sonnet 4.6) ≠ Evaluator(Opus 4.6).

---

## 8. 의존성 매니페스트 (참고용 초안)

### `pyproject.toml` (backend)

```toml
[project]
name = "style-workbench-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "anthropic>=0.40",
  "openai>=1.50",
  "replicate>=0.34",
  "httpx>=0.27",
  "structlog>=24.4",
  "python-multipart>=0.0.9",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "ruff>=0.6",
  "mypy>=1.11",
]

phase2 = [
  "arq>=0.26",
  "redis>=5.0",
  "opentelemetry-api>=1.27",
  "opentelemetry-instrumentation-fastapi>=0.48b0",
]
```

### `package.json` (frontend, 핵심)

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@xyflow/react": "^12.4.0",
    "@tanstack/react-query": "^5.59.0",
    "react-router": "^7.0.0",
    "zustand": "^5.0.0",
    "react-hook-form": "^7.53.0",
    "zod": "^3.23.0",
    "axios": "^1.7.0",
    "lucide-react": "^0.450.0",
    "tailwindcss": "^4.0.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.5.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "vitest": "^2.1.0",
    "@playwright/test": "^1.48.0",
    "eslint": "^9.12.0",
    "prettier": "^3.3.0"
  }
}
```
