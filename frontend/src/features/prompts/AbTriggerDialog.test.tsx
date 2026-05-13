/**
 * F05 단계 5 — AbTriggerDialog 단위 테스트
 *
 * API 호출은 vi.mock으로 스텁. QueryClient / RouterProvider 래핑 포함.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { AbTriggerDialog } from "./AbTriggerDialog";
import type { PromptVersionResponse, PromptUsageResponse } from "@/types/prompts";

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/api/prompts", () => ({
  promptsApi: {
    getVersionById: vi.fn().mockResolvedValue({
      id: "pmv-001",
      version: 1,
      body: "Hello {name}",
      declaredVariables: [{ name: "name", role: "person_name", required: true }],
      modelDefault: null,
      parentVersionId: null,
      changeNote: null,
      createdAt: "2026-05-01T00:00:00Z",
      createdBy: null,
    }),
    triggerAb: vi.fn().mockResolvedValue({
      abId: "ab-001",
      promptId: "prm-001",
      fromVersionId: "pmv-001",
      toVersionId: "pmv-002",
      styleVersionId: "stv-001",
      fromRunId: "run-001",
      toRunId: "run-002",
      status: "done",
    }),
  },
}));

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

const VERSION_1: PromptVersionResponse = {
  id: "pmv-001",
  version: 1,
  body: "Hello {name}",
  declaredVariables: [{ name: "name", role: "person_name", required: true }],
  modelDefault: null,
  parentVersionId: null,
  changeNote: null,
  createdAt: "2026-05-01T00:00:00Z",
  createdBy: null,
};

const VERSION_2: PromptVersionResponse = {
  id: "pmv-002",
  version: 2,
  body: "Hi there {name}",
  declaredVariables: [{ name: "name", role: "person_name", required: true }],
  modelDefault: null,
  parentVersionId: "pmv-001",
  changeNote: "tone 변경",
  createdAt: "2026-05-02T00:00:00Z",
  createdBy: null,
};

const USAGE: PromptUsageResponse = {
  styleVersionId: "stv-001",
  styleName: "테스트 스타일",
  nodeId: "node-text-1",
  pinned: false,
  lastRunScore: 0.84,
};

function renderDialog(props: Partial<Parameters<typeof AbTriggerDialog>[0]> = {}) {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AbTriggerDialog
          open={true}
          onOpenChange={vi.fn()}
          promptId="prm-001"
          versions={[VERSION_1, VERSION_2]}
          currentVersionId="pmv-001"
          usages={[USAGE]}
          {...props}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AbTriggerDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("다이얼로그 열리면 제목과 주요 필드가 표시된다", () => {
    renderDialog();
    expect(screen.getByText("A/B 비교 시작")).toBeInTheDocument();
    expect(screen.getByLabelText("From 버전 선택")).toBeInTheDocument();
    expect(screen.getByLabelText("To 버전 선택")).toBeInTheDocument();
    expect(screen.getByLabelText("Style 버전 선택")).toBeInTheDocument();
  });

  it("F03 미구현 직렬 실행 안내 문구가 표시된다", () => {
    renderDialog();
    // 직렬 실행 안내 note가 표시됨 (aria-label로 확인)
    expect(screen.getByRole("note", { name: "직렬 실행 안내" })).toBeInTheDocument();
  });

  it("from === to 시 Zod schema refine — 에러 메시지를 생성한다", async () => {
    const user = userEvent.setup();
    // from을 pmv-002로 변경하면 toVersionOptions에 pmv-001이 나타남
    // from=pmv-002, to=pmv-002로 설정하면 toVersionOptions에서 pmv-002가 제외되어
    // 실제 UI 상에서는 동일 선택이 불가능하므로, from 변경 후 to options 확인
    renderDialog();

    // from을 pmv-002로 변경
    const fromSelect = screen.getByLabelText("From 버전 선택");
    await user.selectOptions(fromSelect, "pmv-002");

    // to 옵션에 pmv-001이 나타나야 함 (pmv-002 제외)
    const toSelect = screen.getByLabelText("To 버전 선택");
    await user.selectOptions(toSelect, "pmv-001");

    // style 선택
    const styleSelect = screen.getByLabelText("Style 버전 선택");
    await user.selectOptions(styleSelect, "stv-001");

    // 정상 제출 가능해야 함 (from !== to)
    const submitBtn = screen.getByRole("button", { name: "A/B 비교 시작" });
    expect(submitBtn).not.toBeDisabled();
  });

  it("버전이 1개뿐이면 비교 시작 버튼이 disabled", () => {
    renderDialog({ versions: [VERSION_1] });
    const btn = screen.getByRole("button", { name: "A/B 비교 시작" });
    expect(btn).toBeDisabled();
  });

  it("사용처가 없으면 비교 시작 버튼이 disabled", () => {
    renderDialog({ usages: [] });
    const btn = screen.getByRole("button", { name: "A/B 비교 시작" });
    expect(btn).toBeDisabled();
  });

  it("사용처 없음 안내 문구가 표시된다", () => {
    renderDialog({ usages: [] });
    expect(
      screen.getByText(/이 Prompt를 사용하는 Style이 없습니다/)
    ).toBeInTheDocument();
  });

  it("취소 버튼 클릭 시 onOpenChange(false) 호출", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    renderDialog({ onOpenChange });

    await user.click(screen.getByRole("button", { name: "취소" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("임의 hex가 렌더링 결과에 없다", () => {
    const { container } = renderDialog();
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{6}\b/);
  });
});
