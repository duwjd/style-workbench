# CLAUDE.md — Backend (Python / FastAPI)

> 이 문서는 `backend/` 이하 작업 시 적용되는 컨벤션과 절차다. 루트 `CLAUDE.md`의 §5(절대 금지 사항)는 이곳에서도 그대로 유효하다. **프로젝트 전반 라우팅이 필요하면 루트 CLAUDE.md를 먼저 참조한다.**

---

## 1. 작업 시작 전 체크

1. 변경이 어느 layer에 속하는가? (api / services / domain / engine / infra)
2. 외부 모델 호출이 필요한가? → 직접 손대지 말고 `src/style_workbench/adapters/CLAUDE.md`로.
3. AI prompt가 관련된가? → `src/style_workbench/prompts/CLAUDE.md`로.
4. DB 스키마 변경인가? → §6 마이그레이션 절차.
5. 새 의존성 필요? → `docs/TECH_STACK.md` §2 안에 있는가? 없으면 ADR.

---

## 2. 절대 규칙 (위반 즉시 작업 중단)

1. **레이어 의존 방향**: `api → services → domain ← infra`. domain은 그 어떤 다른 레이어도 import 금지. infra는 services를 import 못 한다. **역방향 import는 즉시 거부.**
2. **외부 SDK 직접 호출 금지**: `anthropic`, `openai`, `replicate` 등은 `adapters/`에서만 import. services/api에서 발견되면 차단.
3. **JSON 파일 데이터 저장 금지**: PostgreSQL + SQLAlchemy 2.0 async + Alembic만.
4. **DAG 위상 검증 누락 금지**: Style 저장/업데이트 시 사이클·고립 노드·변수 참조 무결성 검사 필수.
5. **placeholder `{name}` 보호**: `domain/prompt/template.py`의 `safe_substitute(...)`로만 치환. 직접 `.format()`/`.replace()` 금지.

---

## 3. 코딩 컨벤션

### 3.1 언어/도구
- Python **3.12**. PEP 695 generics 사용.
- 의존성: **`uv`만** (`uv add`, `uv sync`, `uv lock`). `pip install` 금지.
- 포맷/린트: **Ruff** 단일 도구. 커밋 전 `uv run ruff format && uv run ruff check --fix`.
- 타입: **mypy strict**. `Any` 남발 금지. 외부 SDK 응답은 `cast(...)` 또는 `pydantic.TypeAdapter(...).validate_python(...)`로 변환.

### 3.2 async / 예외 / 로그
- **async 우선**: 라우터/서비스/저장소 모두 `async def`. blocking I/O는 `asyncio.to_thread(...)`로 격리.
- **예외**: 도메인 예외는 `core/errors.py`에서만 정의. API 핸들러에서 매핑 테이블로 HTTP 변환. **라우터에서 `HTTPException` 직접 raise 금지.**
- **로그**: `structlog.get_logger(__name__)`. `print` 금지. 외부 모델 응답 원문은 hash/요약만, 원문은 DB의 `artifact_url`(provider URL)로만 참조.

### 3.3 import / 응답
- 절대경로 임포트 (`from style_workbench.services.x import Y`). 상대경로 금지.
- 응답 직렬화는 **snake_case**. FE에서 camelCase로 변환.
- `from __future__ import annotations`를 모든 모듈 상단에.

---

## 4. 데이터 모델 (요약 — 자세한 건 루트 §4)

```
Style → versions[] → dag = {nodes[], edges[], variables[]}
```

- DAG 위상 검증은 항상 `domain/style/validation.py`의 `validate_dag(style)` 호출.
- 검증 실패는 `DomainError` raise → API 핸들러에서 422 매핑.
- 변수 참조 무결성: 모든 `{name}` placeholder는 `variables[]`에 선언되어 있어야 함.

---

## 5. 작업 순서

### 5.1 새 API 엔드포인트 추가
1. `api/schemas/<resource>.py` — Pydantic 입출력 모델 (request/response 분리)
2. `domain/<resource>/` — 엔티티/값객체/도메인 서비스
3. `infra/repositories/<resource>_repo.py` — Protocol 인터페이스 + SQLAlchemy 구현
4. Alembic 마이그레이션 (§6 절차)
5. `services/<resource>_service.py` — 유스케이스 (트랜잭션 경계, 어댑터 호출)
6. `api/<resource>.py` — 얇은 라우터 (검증 + DI + 응답 변환만)
7. `api/deps.py` — DI 함수 추가
8. 테스트: `tests/unit/services/...` + `tests/integration/api/...`

### 5.2 새 노드 타입 추가 (예: audio)
1. `domain/style/entity.py`의 `NodeType` enum 확장
2. `engine/node_runners/audio_node.py` 작성 — 어댑터 인터페이스만 의존
3. eval 차원 정의 (`domain/evaluation/criteria.py`)
4. 평가 prompt는 `prompts/CLAUDE.md` 영역에 위임
5. FE 노드 컴포넌트는 `frontend/CLAUDE.md` 영역에 위임

### 5.3 Repository 패턴
- 인터페이스(Protocol) `domain/<x>/repo.py`, 구현(SQLAlchemy) `infra/repositories/<x>_repo.py`
- 메서드는 도메인 엔티티 입출력. ORM 모델을 외부로 노출 금지.

### 5.4 Engine (DAG 실행)
- `engine/runner.py`가 위상정렬 → `node_runners/<type>_node.py` 호출.
- 실패 처리: 노드 단위 retry 횟수, 비용 누적은 항상 trace에.

---

## 6. DB 마이그레이션 절차

1. ORM 모델 변경 후: `uv run alembic revision --autogenerate -m "<설명>"`
2. **생성된 파일을 직접 검토** — autogenerate는 type 변경, default, index drop을 자주 놓친다.
3. 큰 테이블 인덱스는 `op.create_index(..., postgresql_concurrently=True)` 고려.
4. NOT NULL 컬럼 추가 시 기본값 또는 백필 SQL 동반.
5. `uv run alembic upgrade head`로 로컬 적용 후 `alembic downgrade -1`로 다운 검증.

---

## 7. 테스트

- **unit**: domain / engine / 어댑터(HTTP mock). 빠르게.
- **integration**: api + services + 실제 DB (testcontainers-postgres 또는 docker-compose).
- **golden**: prompt 회귀 — `tests/golden/`. Variant Generator / Evaluator 필수 (자세한 건 prompts/CLAUDE.md).
- **커버리지 목표**: domain 90%+, services 70%+, api 50%+(smoke).
- 외부 vendor 호출은 **반드시 mock**. integration에서 진짜 호출은 별도 마커.

---

## 8. 환경 변수 (필수 키)

```bash
# .env.example
DATABASE_URL=postgresql+asyncpg://workbench:workbench@localhost:5432/workbench

# AI vendors
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
REPLICATE_API_TOKEN=

# App
WORKBENCH_API_KEY=local-dev-key
LOG_LEVEL=INFO
ENVIRONMENT=development
```

운영은 AWS Secrets Manager. `.env` 절대 커밋 금지.

---

## 9. 비용 / 보안 가드레일

- **비디오 호출은 매우 비싸다** (Style 1개 회귀 ~₩80,000). `services/run_service.py`에 `cost_budget_won` 옵션을 두고 누적 비용 초과 시 abort.
- 한 Run 안에서 노드 N × 시도 ≤ 3 × 평가 1회. 초과 시 알림.
- 외부 모델 응답에 PII 가능 → 로그는 hash/요약만, 원문은 DB의 `artifact_url`(provider URL)로만 참조.

---

## 10. 코딩 패턴 (스니펫)

### 10.1 FastAPI 라우터 (얇은 layer)
```python
# api/styles.py
from fastapi import APIRouter, Depends
from .deps import get_style_service
from .schemas.styles import StyleCreate, StyleResponse

router = APIRouter(prefix="/api/styles", tags=["styles"])

@router.post("", response_model=StyleResponse, status_code=201)
async def create_style(
    payload: StyleCreate,
    service: StyleService = Depends(get_style_service),
) -> StyleResponse:
    style = await service.create(payload.to_domain())
    return StyleResponse.from_domain(style)
```

### 10.2 Service 오케스트레이션
```python
# services/variant_service.py
class VariantService:
    def __init__(self, claude: ClaudeAdapter, repo: StyleRepo) -> None:
        self.claude = claude
        self.repo = repo

    async def generate(self, brief: Brief, n: int = 5) -> list[Style]:
        prompt = build_variant_system_prompt(brief)
        resp = await self.claude.call(
            model_id="claude-sonnet-4-6",
            input=ModelInput(prompt=brief.to_user_message()),
        )
        styles = parse_variants(resp.content, n=n)
        for s in styles:
            validate_dag(s)
            validate_variables(s)
        return styles
```

---

## 11. 디버깅 — 자주 묻는 것

| 증상 | 가장 흔한 원인 |
|---|---|
| `ImportError: domain → infra` 류 순환 | 의존 방향 위반. domain은 어디도 import 금지 |
| Run이 영원히 pending | BackgroundTasks 예외 삼킴 → structlog로 trace 출력 |
| Variant 생성 결과가 schema 안 맞음 | system prompt에 schema 강제 안 됨 → JSON mode + Pydantic validate |
| 같은 입력에 평가 점수 흔들림 | Evaluator temperature 안 낮춘 것 (0.0~0.2 권장) |
| Alembic이 빈 마이그레이션 생성 | `target_metadata` 누락 또는 모델 import 누락 |
| asyncpg 연결이 메인 루프에 묶임 | sync 코드에서 async 함수 호출. `asyncio.to_thread` 또는 명시적 루프 사용 |

---

## 12. 작업 종료 체크리스트

- [ ] `uv run ruff format` / `uv run ruff check --fix` 통과
- [ ] `uv run mypy backend/src` 통과 (Any 추가 없음)
- [ ] `uv run pytest tests/unit` 통과
- [ ] (해당 시) Alembic 마이그레이션 직접 검토
- [ ] 응답 schema가 snake_case
- [ ] 도메인 예외만 raise (HTTPException 없음)
- [ ] 외부 SDK import가 services/api에 없음 (`rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/{api,services}` 0건)
- [ ] 출력 보고서: 변경 파일 / 마이그레이션 / 미완료 / 검증 결과
