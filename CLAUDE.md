# CLAUDE.md — Style Workbench (루트)

> 이 문서는 프로젝트 **공통 규칙과 절대 금지 사항**, 그리고 **어디서 어떤 규칙을 찾는지의 라우팅 표**다. 레이어별 상세 컨벤션은 자식 CLAUDE.md를 참조한다. Claude Code는 작업 중인 파일과 가까운 CLAUDE.md를 우선 로드한다.

---

## 0. Project at a glance

- **이름**: Style Workbench (코드네임)
- **목적**: 디자이너가 gemgem.biz용 "Style"(텍스트→이미지→비디오 prompt 패키지)을 24h → 6h 안에 만들 수 있는 admin 도구.
- **1차 사용자**: 디자이너 (스타일 제작 / 콘텐츠 기획자)
- **부모 문서** (의도/근거):
  - `docs/STYLE_WORKBENCH_PRD.md` — 무엇을 / 왜
  - `docs/TECH_STACK.md` — 어떤 기술
  - `docs/SYSTEM_ARCHITECTURE.md` — 어떻게 (백엔드/도메인)
  - `docs/DESIGN_SYSTEM.md` — UI 토큰/컴포넌트
- **레퍼런스 자산**: `prompt_optimizer/` (별도 폴더, 자산만 import 대상)

---

## 1. CLAUDE.md 계층 — 어떤 작업이면 어디를 보나

| 작업 영역 | 추가로 읽을 CLAUDE.md |
|---|---|
| Python/FastAPI/services/domain/infra | `backend/CLAUDE.md` |
| AI prompt (Variant Generator, Evaluator) | `backend/src/style_workbench/prompts/CLAUDE.md` |
| 외부 모델 어댑터 / model_profiles / pricing | `backend/src/style_workbench/adapters/CLAUDE.md` |
| React / TS / Tailwind / shadcn / React Flow | `frontend/CLAUDE.md` |

서브에이전트(`.claude/agents/*.md`)도 영역별로 정의되어 있다 — 일상 작업은 서브에이전트가 자동 위임된다.

---

## 2. 작업 시작 전 반드시 확인 (공통)

1. 변경 범위가 어느 layer인가? (api / services / domain / engine / adapters / infra / FE features) → 해당 자식 CLAUDE.md를 먼저 읽는다.
2. 새 의존성이 필요한가? → `docs/TECH_STACK.md` §1, §2 매트릭스 안에 있는가? 없으면 ADR 필요.
3. UI 변경인가? → `docs/DESIGN_SYSTEM.md` §2 컬러 토큰, §5 컴포넌트 인벤토리 + `frontend/CLAUDE.md`.
4. 새 외부 모델 추가인가? → `backend/src/style_workbench/adapters/CLAUDE.md`.
5. AI prompt 변경인가? → `backend/src/style_workbench/prompts/CLAUDE.md`.
6. DB 변경인가? → `backend/CLAUDE.md`의 마이그레이션 절차.

---

## 3. 디렉토리 구조 (저장소 루트)

```
style-workbench/
├── backend/                    # ← backend/CLAUDE.md
│   └── src/style_workbench/
│       ├── api/                # FastAPI 라우터 (얇음)
│       ├── services/           # 유스케이스 오케스트레이션
│       ├── domain/             # 순수 비즈니스 로직 (외부 의존 X)
│       ├── engine/             # DAG 실행 엔진
│       ├── adapters/           # ← adapters/CLAUDE.md
│       ├── infra/              # DB / S3 / 큐
│       │   ├── db/, repositories/, storage/, queue/
│       ├── core/               # config, logging, errors, ids
│       ├── prompts/            # ← prompts/CLAUDE.md
│       └── main.py
├── frontend/                   # ← frontend/CLAUDE.md
│   └── src/
│       ├── routes/             # React Router 7 selectors
│       ├── features/           # 도메인 단위 컴포넌트
│       ├── api/                # axios 래퍼
│       ├── stores/             # Zustand
│       ├── components/ui/      # shadcn/ui 카피
│       ├── lib/, styles/
├── docs/                       # PRD, 아키텍처, 디자인 시스템
├── docker-compose.yml
├── .github/workflows/
├── .claude/agents/             # 서브에이전트 정의
└── CLAUDE.md                   # 이 파일
```

> **새 모듈을 만들 때**: 위 트리에 자리가 없으면, 추가하기 전 의도를 PR description에 적고 검토 받기.

---

## 4. 데이터 모델 핵심 (모든 layer에서 알아야 함)

```
Style = {
  id, name, concept, vertical, tags, status, current_version,
  versions[].dag = { nodes[], edges[], variables[] }
}
```

- **Style은 DAG**, list가 아니다. 단계 수와 입력 종류가 가변. → React Flow의 NodeId/EdgeId와 1:1 매핑.
- **versioning**: DAG 변경 = 새 버전. 메타(name, status, tags) 변경은 in-place.
- **variables**: `{name}` 같은 placeholder. 운영 시 사용자 데이터로 치환. `domain/prompt/template.py`가 안전 치환 담당.

자세한 schema는 `docs/SYSTEM_ARCHITECTURE.md` §4. ORM 모델 변경 시 항상 Alembic 마이그레이션.

---

## 5. 절대 금지 사항 (모든 작업에 적용)

- ✗ Variant Generator와 Step Evaluator를 같은 system prompt / 같은 호출에 섞기
- ✗ 외부 SDK(`anthropic`, `openai`, `replicate`, `boto3`)를 services/api에서 직접 호출
- ✗ Tailwind 임의 hex/px (토큰만 — `frontend/CLAUDE.md` §디자인 토큰 매핑)
- ✗ JSON 파일 기반 데이터 저장 (prompt_optimizer 패턴 답습 — Phase 1부터 PostgreSQL)
- ✗ DAG 위상 검증/사이클 감지 누락 (Style 저장 시 항상 검증)
- ✗ placeholder `{name}` LLM 치환 가능성 무시 (Generator/Evaluator prompt에서 항상 명시적 보호)
- ✗ Backend가 운영 시스템에 직접 등록 (Export Adapter 통해서만)
- ✗ 디자이너 검수 없이 Style을 자동 approve (Phase 3 이전엔 항상 사람 verdict)

이 8개는 어떤 자식 CLAUDE.md를 보더라도 그대로 유효하다.

---

## 6. 공통 컨벤션

- 커밋 메시지: **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`)
- PR 단위: 작게. 한 layer + 그에 대응하는 테스트.
- 코드 코멘트: "왜"만. "무엇"은 코드로. TODO에는 이슈 번호.
- `.env`는 절대 커밋 금지. 운영은 AWS Secrets Manager.

---

## 7. 작업 순서가 헷갈릴 때 (라우팅)

| 작업 종류 | 진입점 |
|---|---|
| 새 API 엔드포인트 | `backend/CLAUDE.md` §작업 순서 → §9.4 |
| 새 노드 타입 (예: audio) | `backend/CLAUDE.md` (domain/engine) → `frontend/CLAUDE.md` (노드 컴포넌트) → `prompts/CLAUDE.md` (evaluator) |
| 외부 모델 추가 | `adapters/CLAUDE.md` 의사결정 트리 |
| 평가 prompt 튜닝 | `prompts/CLAUDE.md` Golden 테스트 절차 |
| 새 UI 컴포넌트 | `frontend/CLAUDE.md` shadcn 추가 절차 |
| 디자인 토큰 추가 | `docs/DESIGN_SYSTEM.md` §2 → `frontend/CLAUDE.md` 토큰 매핑 |

---

## 8. 다음에 확장될 것 (예고)

- Phase 2: arq 큐 + 워커 + 회귀 batch + Test Set Manager UI
- Phase 3: 운영 사용자 피드백 자동 수집, 평가셋 자가 보강
- Phase 3+: 멀티테넌시, OAuth/SSO, 권한 RBAC

---

## 9. 의문이 생기면 — 진짜 진입점 표

| 질문 | 어디 보세요 |
|---|---|
| "이 기능을 왜 하는가" | `docs/STYLE_WORKBENCH_PRD.md` |
| "어떤 라이브러리 써야 하는가" | `docs/TECH_STACK.md` |
| "백엔드 어디에 코드를 두는가" | `docs/SYSTEM_ARCHITECTURE.md` §2 + `backend/CLAUDE.md` |
| "이 색/간격이 맞는가" | `docs/DESIGN_SYSTEM.md` §2~§4 + `frontend/CLAUDE.md` |
| "노드 추가 절차" | 본 문서 §7 라우팅 표 |
| "외부 모델 추가 절차" | `adapters/CLAUDE.md` 의사결정 트리 |
| "지금 당장 할 일" | `docs/GETTING_STARTED.md` |
