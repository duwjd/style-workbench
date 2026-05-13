/**
 * F02 — OptimizationHistoryPanel 단위 테스트
 *
 * 검증 항목:
 *   - 빈 상태 메시지
 *   - succeeded=true 배지 (CheckCircle 아이콘 + "성공" 텍스트)
 *   - succeeded=false 배지 (XCircle 아이콘 + "실패" 텍스트)
 *   - succeeded=true row 클릭 시 navigate
 *   - succeeded=false row는 클릭 불가
 *   - change_summary truncate 표시
 *   - cost_won 포맷
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { OptimizationHistoryPanel } from "./OptimizationHistoryPanel";
import type { PromptOptimizationSummary } from "@/types/prompts";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/api/prompts", () => ({
  promptsApi: {
    listOptimizations: vi.fn(),
    optimizePrompt: vi.fn(),
  },
}));

import { promptsApi } from "@/api/prompts";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const SUCCESS_ITEM: PromptOptimizationSummary = {
  optimizationId: "po-001",
  parentVersionId: "pmv-001",
  newVersionId: "pmv-002",
  changeSummary: "lighting 관련 추가 지시",
  costWon: "312.50",
  succeeded: true,
  failureReason: null,
  createdAt: new Date(Date.now() - 60_000).toISOString(), // 1분 전
};

const FAILURE_ITEM: PromptOptimizationSummary = {
  optimizationId: "po-002",
  parentVersionId: "pmv-001",
  newVersionId: null,
  changeSummary: null,
  costWon: "100.00",
  succeeded: false,
  failureReason: "placeholder {role} 누락",
  createdAt: new Date(Date.now() - 3600_000).toISOString(), // 1시간 전
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPanel(promptId = "prm-001") {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OptimizationHistoryPanel promptId={promptId} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("OptimizationHistoryPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("빈 상태 — 이력이 없을 때 안내 문구 표시", async () => {
    vi.mocked(promptsApi.listOptimizations).mockResolvedValue({
      items: [],
      total: 0,
      limit: 5,
      offset: 0,
    });

    renderPanel();

    await screen.findByText("아직 F02 호출 이력이 없습니다.");
    expect(
      screen.getByText("아직 F02 호출 이력이 없습니다.")
    ).toBeInTheDocument();
  });

  it("succeeded=true row — 성공 배지와 change_summary가 표시된다", async () => {
    vi.mocked(promptsApi.listOptimizations).mockResolvedValue({
      items: [SUCCESS_ITEM],
      total: 1,
      limit: 5,
      offset: 0,
    });

    renderPanel();

    // 성공 배지: 아이콘 + 텍스트 (색에만 의존 금지 검증)
    await screen.findByText("성공");
    expect(screen.getByText("성공")).toBeInTheDocument();

    // change_summary
    expect(
      screen.getByText("lighting 관련 추가 지시")
    ).toBeInTheDocument();

    // 비용 포맷 — 텍스트가 여러 노드로 분리되므로 body 전체에서 확인
    expect(document.body.textContent).toMatch(/비용.*원/);
  });

  it("succeeded=false row — 실패 배지와 failure_reason이 표시된다", async () => {
    vi.mocked(promptsApi.listOptimizations).mockResolvedValue({
      items: [FAILURE_ITEM],
      total: 1,
      limit: 5,
      offset: 0,
    });

    renderPanel();

    await screen.findByText("실패");
    expect(screen.getByText("실패")).toBeInTheDocument();
    expect(
      screen.getByText("placeholder {role} 누락")
    ).toBeInTheDocument();
  });

  it("succeeded=true row 클릭 시 compare 페이지로 navigate", async () => {
    const user = userEvent.setup();
    vi.mocked(promptsApi.listOptimizations).mockResolvedValue({
      items: [SUCCESS_ITEM],
      total: 1,
      limit: 5,
      offset: 0,
    });

    renderPanel("prm-001");

    await screen.findByText("성공");

    const row = screen.getByRole("button", {
      name: /Optimization po-001/,
    });
    await user.click(row);

    expect(mockNavigate).toHaveBeenCalledWith(
      "/prompts/prm-001/compare?from=pmv-001&to=pmv-002&optimization=po-001"
    );
  });

  it("succeeded=false row는 클릭 가능한 button role이 없다", async () => {
    vi.mocked(promptsApi.listOptimizations).mockResolvedValue({
      items: [FAILURE_ITEM],
      total: 1,
      limit: 5,
      offset: 0,
    });

    renderPanel();

    await screen.findByText("실패");

    const buttons = screen.queryAllByRole("button", {
      name: /Optimization po-002/,
    });
    expect(buttons).toHaveLength(0);
  });

  it("임의 hex가 렌더링 결과에 없다", async () => {
    vi.mocked(promptsApi.listOptimizations).mockResolvedValue({
      items: [SUCCESS_ITEM, FAILURE_ITEM],
      total: 2,
      limit: 5,
      offset: 0,
    });

    const { container } = renderPanel();
    await screen.findByText("성공");

    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{6}\b/);
  });
});
