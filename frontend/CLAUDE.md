# CLAUDE.md — Frontend (React 19 / TypeScript / Tailwind v4)

> 이 문서는 `frontend/` 이하 작업 시 적용되는 컨벤션과 절차다. 1차 사용자가 디자이너인 admin 도구이므로 **UI 자체가 first-class 요구사항**. 루트 `CLAUDE.md`의 §5 절대 금지 사항은 여기서도 유효하다. 디자인 토큰의 원본 정의는 `docs/DESIGN_SYSTEM.md`.

---

## 1. 작업 시작 전 체크

1. UI 변경인가? → `docs/DESIGN_SYSTEM.md` §2(컬러), §5(컴포넌트 인벤토리)부터.
2. 새 색/간격/폰트가 필요한가? → 토큰 추가 절차 (§7).
3. 새 컴포넌트인가, 기존 wrapper 확장인가? → shadcn 베이스 우선.
4. 폼 작업인가? → React Hook Form + Zod + shadcn `<Form>`.
5. 새 노드 타입인가? → backend 정의가 먼저. backend-engineer가 enum 확장 후 위임받음.

---

## 2. 절대 규칙 (위반 즉시 차단)

1. **임의 hex/px/rem 금지**. Tailwind 토큰 클래스 또는 `var(--color-*)`만. `bg-[#XXXXXX]`, `style={{color:"#..."}}`, `w-[123px]` 모두 금지.
2. **노드 색상 코딩**: text=teal / image=pink / video=amber / composition=lavender / input=slate / output=emerald — 일관성 유지. 새 노드 타입은 팔레트에서 다음 색을 골라 토큰으로 추가.
3. **DAG 캔버스는 `@xyflow/react`만**. 자체 캔버스/SVG 구현 금지.
4. **다크 모드 기본**. 결과물 미디어가 정확히 보여야 하므로 다크 first.
5. **shadcn/ui 베이스 강제**: 기본 컴포넌트는 `npx shadcn@latest add <name>`으로 카피 후 토큰 매핑 수정. 처음부터 자체 구현 금지.
6. **모바일 미지원**: 1280px 미만은 안내 메시지("데스크톱 권장"). 반응형 분기 노력 금지.
7. **접근성 필수**: focus-visible ring, aria-label, 색에만 의존하지 않는 정보 전달.

---

## 3. 코딩 컨벤션

### 3.1 언어/타입
- React **19**, TypeScript **5.6+ strict**.
- 함수형 컴포넌트만. **한 컴포넌트 = 한 파일.**
- default export는 페이지(`routes/*.tsx`)에서만. 그 외는 named export.
- 파일명: 컴포넌트 `PascalCase.tsx`, 훅 `useCamelCase.ts`, 유틸 `kebab-case.ts`.

### 3.2 상태
- **서버 상태** → TanStack Query (`useQuery`, `useMutation`). queryKey = `[resource, ...filters]`.
- **로컬 UI 상태** → Zustand 슬라이스.
- **폼 상태** → React Hook Form (위 두 가지에 섞지 않는다).

### 3.3 API 호출
- `src/api/<resource>.ts`의 axios 인스턴스. 직접 `fetch` 금지.
- 인터셉터가 응답을 snake→camel 변환 — 화면에서 camelCase로 사용.
- 요청은 camel→snake 변환되므로 작성 시 camelCase로 적는다.

### 3.4 스타일
- 우선순위: 토큰 클래스 → shadcn variant → Tailwind 유틸.
- `cn(...)` 헬퍼(`@/lib/utils`)로 클래스 결합. 문자열 `+` 연결 금지.
- 같은 색을 두 번 정의하지 않는다 — 하나의 토큰에서 파생.

---

## 4. 디자인 토큰 매핑 (자주 쓰는 것)

```
배경:        bg-bg-base / bg-bg-canvas / bg-bg-surface / bg-bg-elevated
             bg-bg-hover / bg-bg-active
보더:        border-border-subtle / border-border-default / border-border-strong
텍스트:      text-text-primary / text-text-secondary / text-text-tertiary
             text-text-disabled / text-text-on-accent
액센트:      bg-accent-500, hover:bg-accent-600
             ring-accent-500, text-accent-300
시맨틱:      text-success / text-warning / text-error / text-info  (bg-* 동일)
노드:        bg-node-text / bg-node-image / bg-node-video
             bg-node-comp / bg-node-input / bg-node-output
평가 점수:   bg-eval-0 .. bg-eval-9 (0 / 3 / 5 / 7 / 9 단계)
```

타이포: `text-h1 / text-h2 / text-h3 / text-body / text-caption`. 임의 `text-[20px]` 금지.

간격: `p-1/2/3/4/6/8`, `gap-*`, `space-y-*`만. 임의 `p-[7px]` 금지.

---

## 5. 작업 순서

### 5.1 새 화면(라우트) 추가
1. `routes/<route>.tsx` — 페이지 컴포넌트(default export)
2. `features/<domain>/` — 화면 구성 컴포넌트 분리
3. 데이터 fetching: 페이지에서 `useQuery`, 자식은 props로 받음
4. 로딩/에러/빈 상태 3가지 모두 제공
5. URL 동기화는 `useSearchParams` (React Router 7)

### 5.2 새 노드 타입 추가 (DAG)
1. backend enum 확장은 backend-engineer가 처리한 뒤 위임받음
2. `features/style-builder/nodes/<X>Node.tsx`에 `NodeProps<XNodeData>` 컴포넌트
3. `--color-node-<x>` 토큰 추가 (없으면 §7로)
4. `features/style-builder/nodeTypes.ts`에 등록
5. 좌측 Tools 패널에 drag 가능한 항목 추가
6. Inspector(우측)에 해당 노드 편집 UI

### 5.3 shadcn 컴포넌트 추가
1. `npx shadcn@latest add <name>` → `components/ui/<name>.tsx`
2. 색/간격을 우리 토큰으로 매핑 (예: `bg-primary` → `bg-accent-500`)
3. `tailwind.config` 또는 `@theme` 토큰 누락 없는지 확인
4. 디자인과 안 맞으면 wrapper에서 흡수 (fork 금지)

### 5.4 폼 작성
1. Zod schema 정의 → `z.infer<typeof schema>`로 타입 추출
2. `useForm({resolver: zodResolver(schema)})`
3. shadcn `<Form>` + `<FormField>` 사용
4. submit은 `useMutation` — 성공 시 `queryClient.invalidateQueries`
5. 에러는 toast(shadcn `<Sonner>`) + 필드 단위 인라인

---

## 6. 키보드 단축키 (Figma 컨벤션)

- Space + drag → pan
- Cmd/Ctrl + S → 저장
- Cmd/Ctrl + Enter → 실행(Run)
- Cmd/Ctrl + D → 복제
- Delete/Backspace → 노드 삭제 (연결된 엣지 함께)
- ? → 단축키 치트시트

새 단축키는 항상 `features/help/Shortcuts.tsx`에도 등록.

---

## 7. 디자인 토큰 추가 절차

1. `docs/DESIGN_SYSTEM.md` §2 팔레트에서 색을 고른다 (직접 hex 발명 금지).
2. `frontend/src/styles/tailwind.css` `@theme` 블록에 `--color-<name>` 추가.
3. `tailwind.config`의 `theme.extend`에 매핑(`bg-<name>` 등 클래스 생성을 위해).
4. 다크/라이트 모두에서 색이 의도대로 보이는지 시각 확인.
5. PR 설명에 "왜 이 토큰이 필요했는가" 명시.

---

## 8. 코딩 패턴 (스니펫)

### 8.1 React 컴포넌트 (Zustand + TanStack Query)
```tsx
// features/comparison/ComparisonGrid.tsx
import { useQuery } from "@tanstack/react-query";
import { useUiStore } from "@/stores/uiStore";
import { runsApi } from "@/api/runs";

export function ComparisonGrid({ runIds }: { runIds: string[] }) {
  const selectedCell = useUiStore((s) => s.selectedCell);
  const { data, isLoading } = useQuery({
    queryKey: ["runs", runIds],
    queryFn: () => runsApi.batchGet(runIds),
  });
  if (isLoading) return <GridSkeleton rows={5} />;
  return <Grid runs={data!} selected={selectedCell} />;
}
```

### 8.2 React Flow 커스텀 노드
```tsx
// features/style-builder/nodes/TextNode.tsx
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";

export function TextNode({ data, selected }: NodeProps<TextNodeData>) {
  return (
    <div
      className={cn(
        "w-60 rounded-lg border bg-bg-surface shadow-md",
        "border-border-default",
        selected && "ring-1 ring-accent-500 shadow-glow-accent"
      )}
    >
      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
        <span className="h-2 w-2 rounded-full bg-node-text" />
        <span className="text-h3 font-semibold text-text-primary">Text Generation</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-node-text" />
    </div>
  );
}
```

---

## 9. 테스트

- **unit**: hooks, lib utils — Vitest.
- **component**: features 컴포넌트 — Testing Library + MSW (API mock).
- **e2e**: Playwright. Phase 1은 happy path 1~2개만 (브리프 → 변주 → 실행 → 채택).

---

## 10. 디버깅 — 자주 묻는 것

| 증상 | 가장 흔한 원인 |
|---|---|
| Tailwind 색이 undefined | `tailwind.config`의 `theme.extend` 또는 v4 `@theme` 블록에 토큰 누락 |
| React Flow 노드 선택 안 잡힘 | 인터랙티브 영역에 `nodrag nopan` 클래스 누락 |
| `useQuery` 데이터가 stale | `queryKey`에 필터 변수 누락 |
| 폼 submit 시 타입 오류 | Zod schema와 RHF 제너릭 타입 불일치 — `z.infer<typeof schema>` 사용 |
| 다크 → 라이트 전환에서 색이 이상 | `[data-theme="light"]`에서 토큰 재정의 누락 |
| shadcn 컴포넌트 색이 우리 톤과 다름 | `bg-primary` 같은 shadcn 변수 → `bg-accent-500` 매핑 누락 |

---

## 11. 작업 종료 체크리스트

- [ ] `npm run lint` 통과 (eslint 9 flat config)
- [ ] `npm run build`의 `tsc --noEmit` 통과
- [ ] `npm run test` (vitest) 통과
- [ ] 임의 hex/px 0건 — `rg "bg-\[#|w-\[\d|h-\[\d|p-\[\d" frontend/src` 빈 결과
- [ ] 다크/라이트 모드 모두 시각 확인
- [ ] 키보드 네비게이션 / focus-visible 작동
- [ ] 응답 데이터를 camelCase로 사용 (snake_case 잔재 0건)
- [ ] 출력 보고서: 변경 파일 / 토큰 영향 / 시각 확인 / 후속 필요(backend)
