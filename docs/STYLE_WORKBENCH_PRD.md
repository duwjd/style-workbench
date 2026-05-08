# Style 자동 생성·평가 워크벤치 PRD

| 항목 | 값 |
|---|---|
| 작성일 | 2026-04-27 |
| 작성자 | 김정원 |
| 상태 | Draft v1 |
| Pilot user | 디자이너 |
| 코드네임 | Style Workbench |

---

## 1. Problem Statement

회사는 사용자가 업로드한 사진을 짧은 영상으로 변환해주는 솔루션(gemgem.biz)을 운영하고 있다. 한 편의 영상은 **텍스트 → 이미지 → 비디오로 이어지는 prompt 패키지와 AI 모델 매핑의 묶음(이하 "Style")** 으로 정의된다.

지금 디자이너가 새 Style을 하나 만드는 데 **평균 3일(≈24시간 작업량)** 이 든다. 시간이 많이 드는 이유는 세 가지다.

1. AI 모델이 같은 prompt에도 매번 다른 결과를 내는 비결정성
2. 텍스트·이미지·비디오 단계마다 prompt를 손으로 튜닝해야 하는 반복 작업
3. 결과 품질을 매 단계마다 사람이 직접 보고 판단해야 하는 검수 부담

결과적으로 디자이너 1인이 **월 5~6개 Style**만 생산할 수 있고, 다양한 컨셉(애니메이션, 공포, 기념일, 소품광고, 화장품 광고 등)과 단계 구성(text+image+video, image만, image 2장 합성+video 등)을 빠르게 실험할 수 없다. 새 컨셉을 시장에 내놓기 전에 디자이너 자원이 병목이 된다.

## 2. Goals / Non-Goals

### Goals

- 디자이너 1인의 Style 제작 시간을 **24h → 6h**로 단축 (≥4배 가속)
- 한 번의 brief로 **시안 5종을 동시 생성**하여 디자이너의 비교·선택 패턴을 표준화
- 단계별 평가를 부분 자동화하여 디자이너의 검수 부담 절감
- **단계 수와 입력 종류가 가변적인 Style**을 자유롭게 표현할 수 있는 데이터 모델 정착
- 기존 `prompt_optimizer` 프로토타입의 자산(모델 프로파일 8개, Claude 클라이언트, 모듈 81개)을 가능한 만큼 재활용

### Non-Goals

- 100% 무인 자동화 — 디자이너 검수 단계는 의도적으로 유지
- 운영 시스템(NestJS → SQS → Python Worker) 자체의 변경
- `prompt_optimizer` 프로토타입을 in-place 발전시키는 것 — **별도 프로젝트로 신규 구축**
- end-user(영상을 만드는 사용자)가 Style을 직접 편집하는 기능
- gemgem.biz 외 다른 제품으로의 확장 (Phase 3 이후 검토)

## 3. Pilot User & 사용 시나리오

### 1차 사용자: 디자이너

- 역할: Style 제작 및 컨텐츠 기획
- 기존 워크플로우: 컨셉 정의 → 단계별 prompt 손작성 → AI API 직접 호출 → 결과 보고 prompt 수정 반복 (3일)
- 페인포인트: 모델 결과의 비결정성, prompt 최적화의 시행착오, 단계 간 톤 정합성 유지의 까다로움

### 핵심 사용 시나리오 (Style 1개 신규 제작)

```
[Step 1] Brief 입력
  - 컨셉/버티컬: "공포 컨셉의 키링 광고"
  - 단계 구성: text + image + video
  - 입력 자료 종류: 인물 1장 + 소품 1장
  - 톤 가이드: "어둑한, 긴장감, 차가운 색온도"

[Step 2] 시안 5종 자동 생성
  → Claude가 위 brief에 맞춰 5개 변주(prompt 패키지 + 모델 매핑) 생성

[Step 3] 동시 실행
  → 디자이너가 미리 준비한 샘플 입력 1~2장으로 5개 변주를 병렬 실행
  → 단계별 결과(텍스트/이미지/비디오) 그리드로 펼침

[Step 4] 자동 평가 + 디자이너 검수
  → Claude Vision이 단계별 점수와 코멘트를 옆에 붙임
  → 디자이너는 점수 + 자기 미감으로 1개 채택, 또는 부분 수정 후 재실행

[Step 5] Export
  → 채택된 Style을 운영 시스템에 등록 가능한 포맷으로 export
```

## 4. Style 데이터 모델 (핵심)

Style은 **단계별 list가 아니라 노드와 엣지로 구성된 그래프(DAG)** 다. 단계 수도 가변, 입력 자료도 가변, 합성/직접 연결 같은 다양한 위상을 한 구조로 표현하기 위해서다.

```jsonc
{
  "id": "biz_portrait_v1",
  "name": "전문가 비즈니스 포트레이트",
  "concept": "professional business portrait",
  "vertical": "personal_branding",
  "tags": ["portrait", "professional", "calm"],
  "variables": ["{name}"],

  "nodes": [
    {
      "id": "txt1",
      "type": "text_generation",
      "model": { "provider": "openai", "model_id": "gpt-5.4" },
      "prompt_template": "You are a professional personal branding...",
      "inputs": [
        { "source": "user_input", "role": "photo" }
      ],
      "output_schema": { "title": "string", "caption": "string" }
    },
    {
      "id": "img1",
      "type": "image_generation",
      "model": { "provider": "replicate", "model_id": "google/nano-banana-pro" },
      "prompt_template": "Transform the person in the input photo into...",
      "inputs": [
        { "source": "user_input", "role": "photo" }
      ]
    },
    {
      "id": "vid1",
      "type": "video_generation",
      "model": { "provider": "replicate", "model_id": "kuaishou/kling-v2.5-turbo-pro" },
      "prompt_template": "A professional portrait video of a person...",
      "inputs": [
        { "source": "node_output:img1" }
      ]
    }
  ],

  "test_inputs": [
    { "id": "ti_001", "files": ["photo_001.jpg"] }
  ],

  "version": 1,
  "status": "draft" // draft | reviewing | approved | deprecated
}
```

### 왜 DAG인가

| 케이스 | 표현 방식 |
|---|---|
| text + image + video | 노드 3개, 직선 연결 |
| image + video만 (텍스트 없음) | 노드 2개 |
| 비디오만 | 노드 1개 |
| 이미지 2장 합성 → 비디오 | composition 노드 1개 + video 노드 1개 (composition.inputs에 user_input 2개) |
| 이미지 4장 시퀀스 → 비디오 | composition 노드 (inputs 4개) + video 노드 |

→ list 구조로는 표현 불가, **그래프 구조면 모든 케이스가 자연스럽게 들어감**

### Variables

`{name}` 같은 placeholder는 운영 중 사용자 데이터로 치환된다. Variable schema도 Style에 명시적으로 선언하여, 워크벤치에서 placeholder를 자동 검증할 수 있게 한다 (LLM이 placeholder를 임의로 치환하는 사고 방지).

## 5. 시스템 아키텍처

**별도 프로젝트로 신규 구축.** `prompt_optimizer`는 자산 제공자로만 활용한다.

```
┌────────────────────────────────────────────────────────┐
│              Style Workbench (신규 프로젝트)             │
│ ┌────────────────────────────────────────────────────┐ │
│ │  Frontend (React + TS + Vite)                       │ │
│ │  - Style List                                       │ │
│ │  - Style Builder (그래프 편집기, reactflow 기반)     │ │
│ │  - Sample Comparison Grid (5종 변주 비교)           │ │
│ │  - Evaluation Panel (자동 점수 + 디자이너 코멘트)    │ │
│ │  - Test Set Manager                                 │ │
│ └────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────┐ │
│ │  Backend (FastAPI 신규)                             │ │
│ │  - Style CRUD API                                   │ │
│ │  - DAG Execution Engine (단계 순차/병렬 실행)       │ │
│ │  - Variant Generator (Claude로 5종 prompt 변주)     │ │
│ │  - Step Evaluator (Claude Vision)                   │ │
│ │  - Test Set Storage                                 │ │
│ │  - Export Adapter (운영 시스템 포맷)                │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                       ↑ 자산 import
┌────────────────────────────────────────────────────────┐
│           prompt_optimizer (기존, 변경 없음)             │
│  - Model profiles (8개) — read-only import              │
│  - Claude client — 코드 추출하여 별도 패키지로 재사용    │
│  - Modules (81개) — Phase 2+에서 building block 참조    │
└────────────────────────────────────────────────────────┘
                       ↓ Style export
┌────────────────────────────────────────────────────────┐
│        gemgem 운영 시스템 (변경 없음)                    │
│        NestJS → SQS → Python Worker                     │
└────────────────────────────────────────────────────────┘
```

### 데이터 저장

- Style 정의: PostgreSQL (DAG는 JSONB 컬럼)
- 실행 결과 (텍스트/이미지/비디오 산출물): 화면에 직접 표시, 브라우저 로컬 다운로드 (provider URL을 DB에 보관)
- 테스트 사진셋: DB 메타 (파일은 브라우저에서 직접 업로드)
- 평가 점수/코멘트: PostgreSQL

(현재 `prompt_optimizer`가 JSON 파일 기반인 것과 달리, 신규는 DB 도입 권장. 동시 실행/비교/평가 이력 보존 부담 때문)

## 6. 워크벤치 UX 흐름

핵심 화면 4개.

### 6-1. Style List
카드형 리스트. 컨셉, 버티컬, 단계 구성 다이어그램(미니), 최근 수정일, 상태(Draft/Reviewing/Approved). 우상단 "+ 새 Style" 버튼.

### 6-2. Style Builder
- **좌측 패널**: 노드 팔레트 — text generation / image generation / video generation / image composition
- **중앙 캔버스**: 그래프 편집기 — 노드 드래그 추가, 핸들 연결로 엣지 생성
- **우측 패널**: 선택한 노드의 prompt 편집기, 모델 매핑(prompt_optimizer 모델 프로파일에서 선택), variable 정의
- **상단 바**: brief 입력(컨셉/버티컬/톤 가이드) + "5종 변주 생성" 버튼

### 6-3. Sample Comparison Grid
5×N 그리드 (5개 변주 × 단계별 결과 N단계). 각 셀:
- 단계 결과 미리보기 (텍스트는 텍스트, 이미지는 썸네일, 비디오는 썸네일+재생)
- 자동 평가 점수 배지 (0.0~1.0)
- 디자이너 코멘트 영역
하단 액션: **"채택"** / **"이 변주만 재실행"** / **"이 셀만 부분 수정"**

### 6-4. Test Set Manager (Phase 1.5+)
카테고리별로 큐레이션된 사진셋 등록·관리. Style 검증 시 자동 batch 실행 트리거.

## 7. 평가 시스템

### 단계별 평가 차원

| 단계 | 평가 차원 | 도구 |
|---|---|---|
| text | 형식 준수, 길이, 톤 적합성, placeholder 보존 | Claude (text-only) |
| image | 구도, 조명, 피사체 보존, 요청 부합, 텍스트/워터마크 부재 | Claude Vision |
| video | 모션 일관성, 피사체 안정성, 지시 모션 부합, 프레임 간 워핑 부재 | Claude Vision (frame extract) |
| composition | 합성 경계 자연스러움, 조명 매칭, 그림자 일관 | Claude Vision |

(자세한 차원은 `step별 md/02_evaluator_prompts.md`의 기존 정의를 채택)

### Phase별 평가 매트릭스

| Phase | 평가 방식 | 테스트셋 | Style 검증 비용/회 | 합격 판단 |
|---|---|---|---|---|
| **1 (POC)** | 디자이너 사진 1~2장 + 시안 5개 + 사람이 고름 | 사실상 없음 | ~8천원 | 디자이너 1명 OK |
| **1.5** | Phase 1 + 카테고리별 5장 큐레이션 | 카테고리당 5장 | ~2만원 | 디자이너 OK + 평가 prompt 회귀 |
| **2** | K=10장 batch 회귀, 분포 차트 | 카테고리당 10~20장 | ~8만원 | 평균 점수 ≥0.75 + 분산 ≤0.15 |
| **3** | 운영 사용자 피드백 자동 수집 → 평가셋 보강 | 자동 누적 | (b)와 동일 | 채택률 + 사용자 만족도 |

### Controller–Evaluator 분리 원칙

기존 하네스 SOP에서 "동일 Claude 대화창에서 생성·평가 동시 수행 금지"를 명시했다. 이 원칙은 워크벤치에서도 유지한다:

- Variant Generator와 Step Evaluator는 **다른 system prompt + 다른 호출 컨텍스트**로 분리
- Evaluator에게는 **원본 prompt를 노출하지 않고** 결과물만 보여주어 자기 확증 편향을 차단
- 통과/탈락 판단은 가능하면 **결정론적 코드**가 수행, Claude는 **점수와 근거**만 산출

## 8. Phase 마일스톤 & 성공 지표

### Phase 1 (POC, 4주)

산출물:
- Style 데이터 모델 + DB schema
- DAG Execution Engine (단계 순차 실행, MVP)
- Variant Generator (Claude로 5종 prompt 변주 생성)
- 기본 Style Builder + Sample Comparison Grid (단순 버전)
- 비즈니스 포트레이트 1개 컨셉으로 end-to-end 검증

성공 지표:
- 디자이너가 비즈니스 포트레이트 Style 1개를 **6시간 내**로 제작 (vs 기존 24h)
- 시안 5개 중 디자이너 채택률 ≥60%

### Phase 1.5 (4주)

산출물:
- 카테고리별 큐레이션 테스트셋 등록 (5장씩)
- 카테고리별 평가 prompt 튜닝
- Style Builder 그래프 편집기 (전체 기능)
- 5~6개 컨셉 검증: 애니메이션 / 공포 / 기념일 / 소품광고 / 화장품 광고

성공 지표:
- 5개 카테고리에서 평균 6시간 내 Style 제작
- 디자이너 월 생산량 5~6개 → **15개 이상**

### Phase 2 (8주)

산출물:
- (b) 평가: 카테고리별 K=10장 batch 회귀
- 회귀 결과 분포 차트
- Test Set Manager UI
- 운영 시스템 export 포맷 정착, 자동 등록 파이프라인

성공 지표:
- 새 Style 채택률 ≥80%
- Style 회귀 batch 자동 실행 (사람 손 없이)
- 디자이너 월 생산량 **30개 이상**

### Phase 3 (장기)

- 운영 사용자 피드백(채택률, 조회수, 완수율) 자동 수집
- 평가셋 자동 보강 + 자가 강화 루프
- 팀/커뮤니티 Style 공유

### 북극성 지표 종합

| 지표 | 현재 | Phase 1 목표 | Phase 2 목표 |
|---|---|---|---|
| Time-to-Style | 24h | 6h | 4h |
| 디자이너 월 생산량 | 5~6개 | 20개 | 30개+ |
| Style 1개 검증 비용 | (수작업, 측정 안 됨) | ~8천원 | ~8만원 (회귀 포함) |
| 시안 채택률 | n/a | ≥60% | ≥80% |
| 단계별 평가 자동화율 | 0% | 50% | 80% |

## 9. prompt_optimizer 자산 매핑

| 기존 자산 | 새 프로젝트 활용 | 비고 |
|---|---|---|
| Model profiles (8개) | DAG 노드의 model 메타데이터로 read-only import | nano-banana-pro, gpt-5.4 등 누락 모델 추가 필요 |
| Claude client (재시도+지수백오프) | 코드 그대로 재사용 | **별도 패키지로 추출** 권장 (두 프로젝트가 동일 코드 의존) |
| Modules (81개, 6 카테고리) | Phase 2+에서 prompt building block 라이브러리로 참조 | Variant Generator의 hint로 활용 가능 |
| 버전 히스토리 (history/) | Style 단위 버전 관리에 구조 참고 | 신규는 DB 기반 권장 |
| Analyzer / Generator | 미사용 | 1차 사용자가 다름 (분석 도구 vs 생성 워크벤치) |
| Module composer | 미사용 | Variant Generator가 대체 |
| `step별 md/` 자료 (Master Controller, Evaluator prompts, retry modifiers) | **Step Evaluator system prompt의 시드로 그대로 활용** | 이미 정제된 자산 |

## 10. Claude Code 활용 시나리오

> Claude Code는 **개발 가속 도구**다. 운영 중 Claude API 호출은 백엔드의 `claude_client`가 수행하며, Claude Code는 개발 환경 내에서만 동작한다. 둘을 섞지 말 것.

| 작업 | Claude Code 활용 방식 |
|---|---|
| Style 데이터 모델 → Pydantic/SQLAlchemy 모델 작성 | schema 명세 → 모델 코드 변환 짝코딩 |
| DAG Execution Engine 구현 | TDD: 테스트 먼저 작성 후 구현 |
| Variant Generator system prompt 튜닝 | golden set 만들고 prompt 변경마다 회귀 |
| Step Evaluator prompt 튜닝 | 평가 결과 일관성 회귀 (같은 입력 → 같은 점수 ±0.05) |
| Style Builder UI (reactflow 통합) | 컴포넌트 골격 + 이벤트 핸들러 |
| Export Adapter (운영 시스템 포맷 변환) | 기존 운영 포맷 분석 → 변환 코드 |
| prompt_optimizer 자산 추출 (claude_client → 별도 패키지) | 리팩토링 + 의존성 정리 |

## 11. 운영팀에 즉시 요청할 자료 (Phase 1 시작 전)

- [ ] **gemgem.biz에서 운영 중인 Style 1개의 실제 데이터** (DB 레코드 / 어드민 export / 내부 도구 설정값 무엇이든)
- [ ] **운영 시스템이 받는 Style 포맷 명세** — Export Adapter 설계의 입력
- [ ] **사용 중인 모델 API 사양 통합본** — 텍스트 단계는 OpenAI(gpt-5.4) 직접 호출, 이미지/영상 단계는 Replicate(nano-banana-pro, kling-v2.5-turbo-pro 등) 경유. 각 모델의 파라미터/제약/단가표
- [ ] **카테고리별 테스트 사진셋 큐레이션** (Phase 1.5 시작 전까지) — 비즈니스/애니메이션/공포/기념일/소품광고/화장품 각 5장
- [ ] **디자이너 1인의 Style 제작 과정 비디오 녹화 1회** — 실제 3일이 어디에 쓰이는지 분해 (UX 설계의 입력)
- [ ] **실패 사례 2~3개** — prompt는 괜찮았는데 결과가 나빴던 케이스 (Step Evaluator의 음성 시그널)

## 12. 리스크 & 미해결 질문

### Risk 1. 평가 prompt의 합격 기준 드리프트
Claude Vision의 점수가 시간이 지나며 흔들릴 수 있다 (모델 업데이트, prompt 미세 변경).
- **완화**: golden test set + 매 배포 전 회귀, 점수 ±0.05 초과 변동 시 알림

### Risk 2. 비디오 모델 비용
Phase 2의 batch 회귀 비용(Style당 ~8만원)이 누적되면 월 비용 부담이 커진다.
- **완화**: Phase 2 진입 전 비용 시뮬레이션, batch 빈도 정책(Style 등록 시 + 분기별 회귀) 합의

### Risk 3. DAG 편집기의 학습 곡선
디자이너가 그래프 UI에 익숙해지는 비용이 클 수 있다.
- **완화**: Phase 1은 폼 기반 단순 UI로 시작, Phase 1.5에서 그래프 편집기 도입, 자주 쓰는 위상은 템플릿으로 제공

### Risk 4. 운영 시스템 포맷 변경
gemgem 운영 시스템의 Style 포맷이 향후 변경되면 Export Adapter가 깨진다.
- **완화**: Adapter 단일 모듈로 격리, 운영팀과 포맷 변경 사전 통보 합의

### 미해결 질문 (spec v2에서 다룰 항목)

- 운영 사용자 피드백을 어떤 신호(채택률 / 완수율 / 좋아요 / 신고)로 정의할 것인가
- Style 간 의존성/상속 (예: "비즈니스 포트레이트 v1.1은 v1의 변주") 표현 방식
- 권한 관리 (Style 작성자 vs 검토자 vs 운영 등록 권한)
- 다국어 prompt 관리 (텍스트 단계가 한/영 모두 필요한 Style)

## 13. 다음 액션

1. 운영팀에 §11 자료 요청 (이번 주 안)
2. `prompt_optimizer`의 `claude_client.py`를 별도 패키지로 추출 (1주 이내)
3. Phase 1 킥오프 일정 확정 + Style 1개(비즈니스 포트레이트) end-to-end 시연 마일스톤 잡기
4. Variant Generator의 system prompt 초안 작성 + golden test set 만들기 (디자이너 1인 + 작성자 협업)
