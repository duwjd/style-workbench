# Design System — Style Workbench

> 디자이너가 직접 사용하는 워크벤치이므로 디자인 자체가 first-class 요구사항. 유사 카테고리의 도구들을 분석하여 우리 컨텍스트에 맞는 디자인 시스템을 구축한다.

---

## 0. 디자인 원칙 (5)

1. **Image-first** — 이미지/영상을 정확하게 보기 위한 배경 환경(어두운 톤, 채도 낮은 중성색)을 기본으로 한다. 결과물이 UI보다 시각적으로 우위에 있어야 한다.
2. **Information density without clutter** — 디자이너는 한 화면에서 5개 시안 × 3~4단계 결과를 동시에 본다. 정보 밀도는 높되, 시각적 위계로 산만하지 않게 한다.
3. **Designer ergonomics** — Figma에 익숙한 사용자를 가정한다. 좌(Tools) - 중(Canvas) - 우(Inspector) 3분할, 키보드 단축키, contextual menu가 표준.
4. **Trust through transparency** — AI 평가 점수, 비용, 모델 이름이 항상 명시적으로 보인다. "왜 이 결정인가"가 한 클릭 안에 설명된다.
5. **Progressive disclosure** — 처음엔 brief 한 장. 깊게 들어가면 노드별 prompt 편집까지 접근 가능. 초보자가 길을 잃지 않게.

---

## 1. 유사 서비스 분석 (요약)

| 서비스 | 카테고리 | 우리가 가져갈 것 | 우리가 피할 것 |
|---|---|---|---|
| **ComfyUI** | 노드 기반 AI 워크플로우 | 노드 타입별 색상 코딩, 무한 캔버스, 핸들 색상 = 데이터 타입 | 입문자에게 압도적인 노드 수, 비전문가에게 진입장벽 |
| **Krea / Runway** | AI 미디어 생성 워크벤치 | 어두운 톤, 큰 미리보기, 결과물 비교 그리드 | 영상 편집기 톤(과한 효과 패널) |
| **Figma Weave** | 디자이너용 AI 워크플로우 | 디자이너 친화 좌-중-우 레이아웃, 인스펙터 패널 | (특별히 피할 것 없음, 가장 가까운 레퍼런스) |
| **Langfuse** | LLM 관측/평가 | 깔끔한 데이터 테이블, 평가 점수의 미니멀 시각화, 다크/라이트 모두 지원 | 개발자 중심 텍스트 위주 (디자이너에게 차가움) |
| **Helicone** | LLM gateway + 평가 | 비기술자 친화 UI, 비용 표시 | 너무 라이트 톤(이미지 결과 보기 어려움) |
| **Promptfoo** | prompt 회귀 테스트 (CLI) | 회귀 비교 표 구조 | CLI 기반(우리는 GUI 필요) |
| **NodeTool / Stack AI** | drag-and-drop AI 빌더 | drag 추가 + 자동 연결 추천 | 너무 다목적(우리는 Style 1종 도구) |
| **Reactflow templates "AI Workflow Editor"** | DAG 에디터 표준 | 미니맵, 줌 컨트롤, 키보드 네비게이션 | (기본 컨벤션 따름) |

**한 줄 결론**: ComfyUI의 노드 표현 + Krea의 결과물 그리드 + Figma의 사이드바 정보 구조 + Langfuse의 평가 미니멀리즘. 이 네 개의 교집합이 우리 디자인 시스템의 자리.

---

## 2. 컬러 시스템

### 2.1 토큰 — 모드별 (Tailwind v4 CSS variables)

라이트/다크 모드 둘 다 지원하되 **다크 모드를 기본**으로 한다. 이미지/영상 결과물의 색이 정확히 보여야 하기 때문.

```css
/* tailwind.css — :root layer */
@theme {
  /* Surfaces (다크 기본) */
  --color-bg-base: #0B0D10;        /* 가장 깊은 배경. 캔버스/플레이어 뒤 */
  --color-bg-canvas: #11141A;      /* DAG 캔버스 */
  --color-bg-surface: #161B22;     /* 사이드바, 카드 */
  --color-bg-elevated: #1D232C;    /* 모달, 팝오버 */
  --color-bg-hover: #232B36;
  --color-bg-active: #2A3340;

  /* Borders & Dividers */
  --color-border-subtle: #1F2630;
  --color-border-default: #2A3340;
  --color-border-strong: #3A4554;

  /* Text */
  --color-text-primary: #E5E9F0;
  --color-text-secondary: #A8B0BD;
  --color-text-tertiary: #6B7280;
  --color-text-disabled: #4B5563;
  --color-text-on-accent: #0B0D10;

  /* Brand / Accent (절제된 보라 — AI 도구다움 + 디자이너 톤) */
  --color-accent-50:  #F5F2FF;
  --color-accent-100: #E8E1FF;
  --color-accent-200: #CFC1FF;
  --color-accent-300: #B098FF;
  --color-accent-400: #8E70FF;
  --color-accent-500: #6E4CF6;     /* primary */
  --color-accent-600: #5934E0;
  --color-accent-700: #4824B8;
  --color-accent-800: #381B8C;
  --color-accent-900: #271264;

  /* Semantic */
  --color-success: #4ADE80;
  --color-warning: #FBBF24;
  --color-error: #F87171;
  --color-info: #60A5FA;

  /* Node-type accents (DAG 노드 색상 코딩 — 키 정체성) */
  --color-node-text:  #2DD4BF;     /* teal — text 단계 */
  --color-node-image: #F472B6;     /* pink — image 단계 */
  --color-node-video: #FBBF24;     /* amber — video 단계 */
  --color-node-comp:  #A78BFA;     /* lavender — composition */
  --color-node-input: #94A3B8;     /* slate — user input */
  --color-node-output:#34D399;     /* emerald — final output */

  /* Evaluation score scale (히트맵용) */
  --color-eval-0: #F87171;          /* 0.0 — red */
  --color-eval-3: #FB923C;          /* 0.3 */
  --color-eval-5: #FBBF24;          /* 0.5 */
  --color-eval-7: #A3E635;          /* 0.7 (PASS threshold) */
  --color-eval-9: #4ADE80;          /* 0.9+ */
}

/* Light mode (옵션, 토글) */
[data-theme="light"] {
  --color-bg-base: #FFFFFF;
  --color-bg-canvas: #FAFAFB;
  --color-bg-surface: #F4F5F7;
  --color-bg-elevated: #FFFFFF;
  --color-bg-hover: #ECEEF1;
  --color-bg-active: #E1E4E9;

  --color-border-subtle: #ECEEF1;
  --color-border-default: #D8DCE3;
  --color-border-strong: #B8BFC9;

  --color-text-primary: #0B0D10;
  --color-text-secondary: #4B5563;
  --color-text-tertiary: #6B7280;
  --color-text-disabled: #9CA3AF;
}
```

### 2.2 컬러 사용 가이드

| 용도 | 토큰 |
|---|---|
| 페이지 기본 배경 | `bg-base` |
| 사이드바, 카드 표면 | `bg-surface` |
| 모달, 팝오버, 드롭다운 | `bg-elevated` |
| 본문 텍스트 | `text-primary` |
| 보조 설명, 메타 | `text-secondary` |
| Placeholder, 비활성 | `text-tertiary` |
| Primary CTA, 활성 상태 | `accent-500` |
| 호버 (CTA) | `accent-400` |
| 노드 헤더 색 | 노드 타입에 따라 `node-*` |
| 평가 점수 히트맵 | `eval-*` (보간) |

---

## 3. 타이포그래피

### 3.1 폰트 스택

```css
--font-sans: "Pretendard Variable", "Pretendard", "Inter", system-ui, sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
--font-display: "Pretendard Variable", "Inter Display", sans-serif;
```

> 한국어 UI 텍스트가 많고 디자이너 사용자 환경을 고려해 **Pretendard Variable**을 1순위. 영문은 Inter로 자연스럽게 fallback.

### 3.2 스케일

| 토큰 | 크기 / 행간 / 자간 | 용도 |
|---|---|---|
| `text-display` | 32px / 40px / -0.02em | Page title (Style List) |
| `text-h1` | 24px / 32px / -0.01em | 섹션 타이틀 |
| `text-h2` | 20px / 28px / -0.01em | 카드 타이틀 |
| `text-h3` | 16px / 24px / 0 | 패널 타이틀 |
| `text-body` | 14px / 22px / 0 | 본문 |
| `text-body-sm` | 13px / 20px / 0 | 보조 본문 |
| `text-caption` | 12px / 16px / 0.01em | 메타, 라벨 |
| `text-mono-sm` | 12px / 18px / 0 | prompt 코드, ID |
| `text-mono-md` | 14px / 22px / 0 | prompt 편집기 |

가중치: 400(regular), 500(medium), 600(semibold), 700(bold). 자주 쓰는 조합은 `text-h3 font-semibold`.

---

## 4. 간격 / 그리드 / 모서리

### 4.1 Spacing scale (Tailwind 기본 + 커스텀 2개)

`0 / 1 / 2 / 3 / 4 / 5 / 6 / 8 / 10 / 12 / 16 / 20 / 24` (4px 단위, Tailwind 기본). `1.5` (6px)와 `2.5` (10px)도 제한적으로 사용.

### 4.2 Layout grid

- 데스크톱 기본: 1440px+ 가정 (디자이너 작업 환경)
- 최소 지원: 1280px
- 컨텐츠 최대 폭: 1280px (List 페이지 등)
- 워크벤치 화면은 **viewport 100% 사용** (3분할 레이아웃)

### 4.3 모서리 / 그림자

```css
--radius-sm: 4px;    /* 인라인 배지, 작은 버튼 */
--radius-md: 6px;    /* 인풋, 일반 버튼 */
--radius-lg: 10px;   /* 카드 */
--radius-xl: 14px;   /* 모달, 큰 카드 */
--radius-2xl: 20px;  /* 미디어 미리보기 컨테이너 */

--shadow-sm:  0 1px 2px rgba(0,0,0,.30);
--shadow-md:  0 4px 12px rgba(0,0,0,.35);
--shadow-lg:  0 12px 28px rgba(0,0,0,.45);
--shadow-glow-accent: 0 0 0 1px var(--color-accent-500), 0 0 16px rgba(110,76,246,.35);
```

다크 모드 그림자는 살짝 강하게 (대비 보존).

---

## 5. 컴포넌트 인벤토리

shadcn/ui를 베이스로 카피 후 위 토큰으로 리브랜딩.

### 5.1 기본 컴포넌트 (shadcn/ui 채택)

`Button` / `Input` / `Textarea` / `Select` / `Checkbox` / `Radio` / `Switch` / `Slider` / `Tabs` / `Dialog` / `Sheet` / `Popover` / `Tooltip` / `DropdownMenu` / `ContextMenu` / `Toast` / `Card` / `Badge` / `Skeleton` / `Separator` / `Avatar` / `ScrollArea` / `Form`

### 5.2 워크벤치 전용 컴포넌트 (자체 제작)

| 컴포넌트 | 용도 | 핵심 props |
|---|---|---|
| **DagCanvas** | React Flow 래퍼, 미니맵/줌/배경 그리드 | `nodes`, `edges`, `onNodesChange`, `onConnect` |
| **NodeCard** | DAG 안의 노드 (text/image/video/composition) | `type`, `model`, `status`, `evaluation` |
| **NodeHandle** | 입출력 핸들 — 데이터 타입별 색상 | `kind`, `position`, `dataType` |
| **NodePalette** | 좌측 팔레트 (드래그 추가) | `onDragStart` |
| **PromptEditor** | 노드 우측 패널의 prompt 편집기 | `value`, `variables`, `onChange` |
| **VariableChip** | `{name}` placeholder 시각화 | `name`, `validated` |
| **BriefForm** | 컨셉/단계구성/입력종류 입력 | `onSubmit` |
| **VariantPicker** | 5종 변주 카드 그리드 | `variants`, `onSelect` |
| **ComparisonGrid** | 5×N 시안 결과 그리드 | `runs`, `nodes` |
| **StageCell** | 한 칸 (한 변주 × 한 단계) | `artifact`, `evaluation` |
| **MediaPreview** | 텍스트/이미지/영상 통합 미리보기 | `output`, `size` |
| **EvalScoreBadge** | 평가 점수 배지 (색 보간) | `score`, `result` |
| **EvalDimensions** | 차원별 점수 펼침 | `dimensions` |
| **VerdictPanel** | 채택/기각/재실행 액션 | `onAdopt`, `onReject`, `onRerun` |
| **CostMeter** | Run 비용 누적 게이지 | `cost`, `budget?` |
| **ModelPicker** | 노드의 모델 선택 셀렉터 | `nodeType`, `value` |
| **TestSetSelector** | 테스트셋 선택/업로드 | `category` |
| **RunStatusPill** | 실행 상태 배지 | `status` |
| **DiffViewer** | prompt 변경 diff (variant 간 비교) | `from`, `to` |

### 5.3 NodeCard 디자인 (핵심 컴포넌트)

```
┌──────────────────────────────────────┐
│ ●  Text Generation        ✕          │  ← 헤더: 노드타입 dot(node-text 색) + 타이틀 + 닫기
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ Model: gpt-5.4 ▼                     │  ← 모델 선택
│                                      │
│  Prompt preview (3 lines, truncate)  │  ← prompt 미리보기
│  "You are a professional..."         │
│                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ ⏱ 2.4s   ₩ 35   [score 0.82] PASS    │  ← 실행 후: 시간/비용/점수
└──────────────────────────────────────┘
   ⬅ left handles    right handles ➡
```

- 너비: 240px 고정
- 헤더 좌측 dot 색상: `--color-node-{type}` (정체성 강조)
- 실행 전: 점수/비용 영역 빈 자리. 실행 중: skeleton + spinner. 완료: 채워짐.
- 호버 시 가벼운 elevation, 선택 시 `shadow-glow-accent`.

### 5.4 ComparisonGrid 레이아웃

```
            Stage 1: text     Stage 2: image      Stage 3: video
          ┌───────────────┬───────────────────┬────────────────┐
Variant 1 │  txt preview  │   image thumb     │  video player  │
          │  score 0.82   │   score 0.79      │  score 0.84    │
          ├───────────────┼───────────────────┼────────────────┤
Variant 2 │      ...      │       ...         │      ...       │
          ├───────────────┼───────────────────┼────────────────┤
   ...    │      ...      │       ...         │      ...       │
          └───────────────┴───────────────────┴────────────────┘
                                                    [채택] [재실행]
```

- 5×N 그리드. 한 행 = 한 variant.
- 각 셀: `MediaPreview` + `EvalScoreBadge` + 호버 시 액션 메뉴 (확대, 다시 실행, 부분 수정)
- 셀 선택 시 우측 인스펙터에 detail (차원별 점수, raw response, prompt)

---

## 6. 인터랙션 & 모션

### 6.1 모션 토큰

```css
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
--duration-fast: 120ms;
--duration-normal: 220ms;
--duration-slow: 360ms;
```

- 호버: 120ms `ease-out`
- 패널 토글: 220ms `ease-in-out`
- 모달: 220ms `ease-out` + scale 0.96 → 1
- DAG 노드 추가: 360ms spring (React Flow 내부)
- 결과물 등장 (스트리밍): 220ms fade + slide-up 8px

### 6.2 키보드 단축키 (Figma 컨벤션 차용)

| 단축키 | 동작 |
|---|---|
| `Space + drag` | 캔버스 panning |
| `Cmd/Ctrl + scroll` | 줌 |
| `Cmd/Ctrl + 0` | 줌 fit |
| `Cmd/Ctrl + S` | 저장 (현재 변주를 Style version으로 저장) |
| `Cmd/Ctrl + Enter` | 변주 생성 / Run 실행 |
| `Cmd/Ctrl + D` | 노드 복제 |
| `Backspace` | 선택 노드/엣지 삭제 |
| `R` | 선택한 셀 재실행 |
| `A` | 채택 (Adopt) |
| `1`–`5` | 비교 그리드에서 variant 행 선택 |
| `?` | 단축키 도움말 |

### 6.3 상태 (State) 시각 언어

| 상태 | 시각 |
|---|---|
| Idle | 평소 상태 |
| Hover | bg-hover, 투명한 elevation |
| Selected | 1px outline `accent-500` + `shadow-glow-accent` |
| Loading | skeleton(시머) 또는 spinner (8px stroke 1.5px) |
| Disabled | opacity 0.4, cursor not-allowed |
| Success (PASS) | dot `success`, badge 배경 `success/15` |
| Warning | dot `warning` |
| Error (FAIL) | dot `error`, badge 배경 `error/15`, 좌측 4px 바 `error` |
| Streaming | 우측 상단 작은 펄스 dot + "live" 캡션 |

---

## 7. 핵심 화면 와이어프레임 (텍스트)

### 7.1 Style List (`/styles`)

```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo] Style Workbench       Search...        [+ 새 Style]  ◐   │  ← 상단바
├─────────────────────────────────────────────────────────────────┤
│ Filters: All / Approved / Draft / Reviewing                     │
│ Vertical: [전체 ▼]   Tags: [+]                                  │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│ │ [thumb]     │ │ [thumb]     │ │ [thumb]     │ │ [thumb]     ││
│ │ Biz Portrait│ │ Horror Key  │ │ Anniversary │ │ ...         ││
│ │ ●●● 3 steps │ │ ●● 2 steps  │ │ ●●●● 4 steps│ │             ││
│ │ Approved    │ │ Reviewing   │ │ Draft       │ │             ││
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Style Builder (`/styles/:id`)

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Biz Portrait  v3 (Draft)        [변주 5종 생성] [실행 ▶] [저장]│
├──────────┬──────────────────────────────────────────┬───────────┤
│ Palette  │           DAG Canvas                      │ Inspector │
│          │                                           │           │
│ ▣ Text   │     ┌─txt1─┐                              │ Selected: │
│ ▣ Image  │     │ ●    │──┐                           │ img1      │
│ ▣ Video  │     └──────┘  │                           │           │
│ ▣ Compose│              ┌─img1─┐                     │ Model:    │
│          │              │ ●    │──>┌─vid1─┐          │ nano-     │
│          │              └──────┘   │ ●    │          │ banana-pro│
│          │                          └──────┘         │           │
│          │  [minimap]                                │ Prompt:   │
│          │                                           │ ┌────────┐│
│          │                                           │ │textarea││
│          │                                           │ └────────┘│
└──────────┴──────────────────────────────────────────┴───────────┘
```

### 7.3 Comparison Grid (`/runs/:runId`)

```
┌─────────────────────────────────────────────────────────────────┐
│ Run abc123 · biz portrait v3 · ₩ 8,400 · ⏱ 2m 14s              │
├─────────────────────────────────────────────────────────────────┤
│              text          image            video               │
│ Variant 1 [text 0.82] [image preview 0.79] [video preview 0.84] │ ← [채택]
│ Variant 2 [text 0.71] [image preview 0.65] [video preview 0.88] │
│ Variant 3 [text 0.85] [image preview 0.81] [video preview 0.62] │
│ Variant 4 [text 0.78] [image preview 0.74] [video preview 0.79] │
│ Variant 5 [text 0.69] [image preview 0.58] [video preview 0.55] │
├─────────────────────────────────────────────────────────────────┤
│ [선택된 셀의 상세 인스펙터: 차원별 점수, prompt, raw response]    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 접근성 (WCAG 2.1 AA 기준)

- **컬러 콘트라스트**: 본문 text-primary on bg-base ≥ 13.5:1, secondary ≥ 7:1.
- **포커스 가시성**: 모든 인터랙티브 요소에 `outline-2 outline-accent-500 outline-offset-2`.
- **키보드 네비게이션**: 모든 액션 키보드만으로 도달 가능 (위 §6.2).
- **상태 색에만 의존 X**: PASS/FAIL은 색 + 아이콘 + 텍스트 동시.
- **모션 감소**: `prefers-reduced-motion: reduce`에서 transform 애니메이션 → 0ms, opacity는 유지.
- **i18n**: 1차는 한국어. 영문 토글 가능 구조 (i18next).

---

## 9. 컴포넌트 코드 컨벤션 (FE)

```tsx
// shadcn/ui 베이스에 토큰 적용 예시
import { cn } from "@/lib/utils";

export function Button({ variant = "primary", className, ...props }) {
  return (
    <button
      className={cn(
        "inline-flex items-center gap-2 rounded-md font-medium transition-colors duration-fast",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500",
        variant === "primary" &&
          "bg-accent-500 text-text-on-accent hover:bg-accent-400",
        variant === "secondary" &&
          "bg-bg-surface text-text-primary hover:bg-bg-hover border border-border-default",
        variant === "ghost" &&
          "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
        className
      )}
      {...props}
    />
  );
}
```

### 토큰 매핑 원칙

- 색은 항상 토큰 클래스 (`bg-bg-surface`)로 — hex 직접 X
- 간격은 Tailwind 스케일 — 임의 값 X
- 라운드는 `rounded-{sm|md|lg|xl|2xl}` 토큰만
- 그림자도 토큰만

---

## 10. 디자인 디버깅 가이드

| 증상 | 점검 |
|---|---|
| 화면이 평평해 보임 | elevation 단계가 부족. surface/elevated 구분 점검 |
| 노드 식별이 어려움 | 노드 헤더 dot 색상이 토큰과 매칭되는지 |
| 이미지 결과가 너무 어두워 보임 | 미디어 컨테이너 배경을 `bg-base`로 (UI 더 깊게 가서 결과물 부각) |
| 텍스트 가독성 떨어짐 | text-secondary를 본문에 쓰지 않았는지 — 본문은 text-primary |
| Variant 비교 시 점수 차이가 안 보임 | EvalScoreBadge의 색이 0.7 임계 기준으로 색상 점프하는지 |

---

## 11. 자산 / 참조 라이브러리

- **shadcn/ui**: 컴포넌트 베이스
- **Radix UI Primitives**: shadcn 의존성, 접근성 보장
- **lucide-react**: 아이콘 (라인, 1.5px stroke 통일)
- **@xyflow/react**: DAG 에디터
- **vaul**: 시트/드로어 (모바일 고려 시)
- **cmdk**: 커맨드 팔레트(`Cmd+K`)
- **sonner**: 토스트
- **media-chrome**: 영상 플레이어 (선택)

## 12. 참고 자료 (External)

- [React Flow - AI Workflow Editor template](https://reactflow.dev/ui/templates/ai-workflow-editor) — DAG 에디터 표준
- [ComfyUI](https://comfy.org/) — 노드 색상 코딩, 무한 캔버스 패턴
- [Figma Weave](https://weave.figma.com/) — 디자이너용 AI 워크플로우 레이아웃 레퍼런스
- [NodeTool](https://nodetool.ai/) — 로컬 노드 빌더 UI
- [Langfuse — clean UI for prompt management](https://www.confident-ai.com/knowledge-base/compare/top-langfuse-alternatives-and-competitors-compared) — 평가 미니멀리즘

Sources:
- [React Flow - AI Workflow Editor](https://reactflow.dev/ui/templates/ai-workflow-editor)
- [ComfyUI](https://comfy.org/)
- [Figma Weave](https://weave.figma.com/)
- [NodeTool](https://nodetool.ai/)
- [Comparison of Promptfoo, Langfuse, Optik, and Other Self-Hosted LLM Platforms](https://www.davidpp.com/ai/llm-observability-tools)
- [Top 5 Langfuse Alternatives and Competitors, Compared (2026) — Confident AI](https://www.confident-ai.com/knowledge-base/compare/top-langfuse-alternatives-and-competitors-compared)
