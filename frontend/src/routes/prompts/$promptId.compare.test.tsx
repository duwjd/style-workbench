/**
 * F05 단계 5 — PromptComparePage 단위 테스트
 *
 * URL query 파싱, diff 렌더, promote 버튼 분기 검증.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import PromptComparePage from "./$promptId.compare";

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/api/prompts", () => ({
  promptsApi: {
    getVersionById: vi.fn().mockImplementation((_promptId: string, versionId: string) => {
      if (versionId === "pmv-001") {
        return Promise.resolve({
          id: "pmv-001",
          version: 1,
          body: "Hello {name} from v1",
          declaredVariables: [{ name: "name", role: "person_name", required: true }],
          modelDefault: null,
          parentVersionId: null,
          changeNote: null,
          createdAt: "2026-05-01T00:00:00Z",
          createdBy: null,
        });
      }
      return Promise.resolve({
        id: "pmv-002",
        version: 2,
        body: "Hi there {name} from v2",
        declaredVariables: [{ name: "name", role: "person_name", required: true }],
        modelDefault: null,
        parentVersionId: "pmv-001",
        changeNote: "tone 변경",
        createdAt: "2026-05-02T00:00:00Z",
        createdBy: null,
      });
    }),
    promoteVersionById: vi.fn().mockResolvedValue({ id: "prm-001" }),
  },
}));

vi.mock("@/api/runs", () => ({
  runsApi: {
    getById: vi.fn().mockImplementation((runId: string) => {
      return Promise.resolve({
        id: runId,
        styleVersionId: "stv-001",
        styleId: "style-001",
        status: "succeeded",
        totalCost: 0.0042,
        createdAt: "2026-05-08T00:00:00Z",
        startedAt: "2026-05-08T00:00:01Z",
        finishedAt: "2026-05-08T00:00:30Z",
        nodeExecutions: [
          {
            id: `exec-${runId}`,
            nodeId: "node-text-1",
            nodeType: "text_generation",
            modelProvider: "anthropic",
            modelId: "claude-3-5-haiku-20241022",
            artifactUrl: "Generated text result",
            cost: 0.0042,
            status: "succeeded",
            startedAt: "2026-05-08T00:00:01Z",
            finishedAt: "2026-05-08T00:00:30Z",
          },
        ],
      });
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

interface RenderOptions {
  search?: string;
  state?: Record<string, unknown>;
}

function renderComparePage({ search = "?from=pmv-001&to=pmv-002", state = {} }: RenderOptions = {}) {
  const qc = makeQueryClient();

  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/prompts/prm-001/compare",
            search,
            state,
          },
        ]}
      >
        <Routes>
          <Route path="/prompts/:promptId/compare" element={<PromptComparePage />} />
          <Route path="/prompts/:promptId" element={<div>Prompt Detail</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PromptComparePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("URL query에서 from/to를 읽어 헤더에 표시한다", async () => {
    renderComparePage();
    await waitFor(() => {
      // A/B 비교: v1 → v2 (버전 조회 후 표시)
      expect(screen.getByText(/A\/B 비교/)).toBeInTheDocument();
    });
  });

  it("from/to query가 없으면 에러 안내 메시지를 표시한다", () => {
    renderComparePage({ search: "" });
    expect(
      screen.getByText("URL에 from, to 버전 파라미터가 없습니다.")
    ).toBeInTheDocument();
  });

  it("state에 run_id가 없으면 '실행 결과를 표시할 수 없습니다' 메시지를 표시한다", async () => {
    renderComparePage({ state: {} });
    expect(
      screen.getByText("실행 결과를 표시할 수 없습니다.")
    ).toBeInTheDocument();
  });

  it("'새로 비교 실행' CTA 버튼이 표시된다 (run_id 없음)", () => {
    renderComparePage({ state: {} });
    expect(screen.getByText("새로 비교 실행")).toBeInTheDocument();
  });

  it("state에 run_id가 있으면 '실행 결과 비교' 섹션이 렌더된다", async () => {
    renderComparePage({
      state: { fromRunId: "run-001", toRunId: "run-002" },
    });

    await waitFor(() => {
      expect(screen.getByText("실행 결과 비교")).toBeInTheDocument();
    });
  });

  it("promote 버튼과 유지 버튼이 있다", async () => {
    renderComparePage({
      state: { fromRunId: "run-001", toRunId: "run-002" },
    });

    await waitFor(() => {
      // AbResultPanel의 Promote 버튼 — aria-label로 찾기
      expect(
        screen.getByRole("button", { name: /current로 승격/ })
      ).toBeInTheDocument();
      // 유지 버튼 — aria-label에 "유지" 포함
      expect(
        screen.getByRole("button", { name: /유지/ })
      ).toBeInTheDocument();
    });
  });

  it("diff 뷰가 렌더된다 (버전 본문 로드 후)", async () => {
    renderComparePage();
    await waitFor(() => {
      // Diff 섹션의 header가 표시됨
      expect(screen.getByText(/Diff:/)).toBeInTheDocument();
    });
  });

  it("렌더링에 임의 hex 없음", async () => {
    const { container } = renderComparePage();
    // 초기 렌더 기준
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{6}\b/);
  });
});
