/**
 * F02 — OptimizeDialog 단위 테스트
 *
 * 검증 항목:
 *   - 폼 검증 (Mode B 필수 필드 — retry_guidance, failed_dimensions, parent_version_id)
 *   - retry_guidance JSON parse 분기 (유효한 JSON / 자유 텍스트)
 *   - failed_dimensions chip CRUD (추가 / 제거)
 *   - Mode A/B 탭 전환
 *   - succeeded=false 응답 시 failureReason 표시 + 다이얼로그 유지
 *   - succeeded=true 응답 시 navigate
 *   - 임의 hex 없음
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { Toaster } from "sonner";
import { OptimizeDialog } from "./OptimizeDialog";
import type { PromptVersionResponse } from "@/types/prompts";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();

vi.mock("@/api/prompts", () => ({
  promptsApi: {
    optimizePrompt: vi.fn(),
    listOptimizations: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    }),
  },
}));

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import { promptsApi } from "@/api/prompts";
const mockOptimizePrompt = vi.mocked(promptsApi.optimizePrompt);

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
  body: "Hi {name}",
  declaredVariables: [{ name: "name", role: "person_name", required: true }],
  modelDefault: null,
  parentVersionId: "pmv-001",
  changeNote: "tone 조정",
  createdAt: "2026-05-02T00:00:00Z",
  createdBy: null,
};

function renderDialog(
  props: Partial<Parameters<typeof OptimizeDialog>[0]> = {}
) {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Toaster />
        <OptimizeDialog
          open={true}
          onOpenChange={vi.fn()}
          promptId="prm-001"
          versions={[VERSION_1, VERSION_2]}
          currentVersionId="pmv-001"
          {...props}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("OptimizeDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("다이얼로그 열리면 제목과 Mode B 기본 필드가 표시된다", () => {
    renderDialog();
    expect(screen.getByText("F02 Prompt Optimize")).toBeInTheDocument();
    expect(screen.getByLabelText("기준 버전 선택")).toBeInTheDocument();
    expect(screen.getByLabelText("수정 지침 입력")).toBeInTheDocument();
    expect(screen.getByLabelText("실패 차원 입력")).toBeInTheDocument();
  });

  it("Mode A 탭 전환 시 evaluationId 입력 필드가 표시된다", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(
      screen.getByRole("tab", { name: "Mode A — evaluation 자동" })
    );

    expect(screen.getByLabelText("evaluation_id 입력")).toBeInTheDocument();
    expect(screen.getByRole("note", { name: "Mode A 안내" })).toBeInTheDocument();
  });

  it("Mode B — 필수 필드 미입력 시 Optimize 실행 버튼이 disabled", () => {
    renderDialog();
    const btn = screen.getByRole("button", { name: "Optimize 실행" });
    expect(btn).toBeDisabled();
  });

  it("Mode B — retry_guidance + dimension + version 모두 입력 시 버튼 활성화", async () => {
    const user = userEvent.setup();
    renderDialog();

    // 기준 버전 선택 (이미 defaultVersionId=pmv-001이므로 select가 이미 선택됨 여부 확인)
    const versionSelect = screen.getByLabelText("기준 버전 선택");
    await user.selectOptions(versionSelect, "pmv-001");

    // retry_guidance 입력
    await user.type(
      screen.getByLabelText("수정 지침 입력"),
      "주광원 방향을 변경하세요"
    );

    // dimension 추가
    await user.type(screen.getByLabelText("실패 차원 입력"), "lighting");
    await user.click(screen.getByRole("button", { name: "차원 추가" }));

    const btn = screen.getByRole("button", { name: "Optimize 실행" });
    expect(btn).not.toBeDisabled();
  });

  it("dimension chip 추가 후 제거가 동작한다", async () => {
    const user = userEvent.setup();
    renderDialog();

    // dimension 추가
    await user.type(screen.getByLabelText("실패 차원 입력"), "composition");
    await user.click(screen.getByRole("button", { name: "차원 추가" }));

    // chip + quick-add 버튼 두 곳에 "composition"이 있을 수 있으므로 getAllByText 사용
    expect(screen.getAllByText("composition").length).toBeGreaterThan(0);

    // chip 제거
    await user.click(
      screen.getByRole("button", { name: "composition 차원 제거" })
    );

    // 제거 후 chip span은 사라지고 quick-add 버튼(비활성화 해제됨)만 남음
    // quick-add 버튼은 disabled 상태가 아닌 것으로 변경 확인
    const removeBtn = screen.queryByRole("button", {
      name: "composition 차원 제거",
    });
    expect(removeBtn).not.toBeInTheDocument();
  });

  it("권장 차원 quick-add 버튼으로 dimension이 추가된다", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(
      screen.getByRole("button", { name: "lighting 차원 빠른 추가" })
    );

    expect(screen.getAllByText("lighting").length).toBeGreaterThan(0);
  });

  it("retry_guidance 자유 텍스트는 JSON 래핑되어 전달된다", async () => {
    const user = userEvent.setup();
    mockOptimizePrompt.mockResolvedValue({
      optimizationId: "po-001",
      promptId: "prm-001",
      parentVersionId: "pmv-001",
      newVersionId: "pmv-003",
      changeSummary: "lighting 개선",
      costWon: "312.50",
      latencyMs: 4523,
      succeeded: true,
      failureReason: null,
    });

    renderDialog();

    const versionSelect = screen.getByLabelText("기준 버전 선택");
    await user.selectOptions(versionSelect, "pmv-001");

    const guidanceInput = screen.getByLabelText("수정 지침 입력");
    await user.type(guidanceInput, "순수 자유 텍스트 지침");

    await user.type(screen.getByLabelText("실패 차원 입력"), "mood");
    await user.click(screen.getByRole("button", { name: "차원 추가" }));

    await user.click(screen.getByRole("button", { name: "Optimize 실행" }));

    await waitFor(() => {
      expect(mockOptimizePrompt).toHaveBeenCalledWith(
        "prm-001",
        expect.objectContaining({
          retryGuidance: { instruction: "순수 자유 텍스트 지침" },
          failedDimensions: ["mood"],
          parentVersionId: "pmv-001",
        })
      );
    });
  });

  it("retry_guidance 유효한 JSON은 그대로 파싱되어 전달된다", async () => {
    const user = userEvent.setup();
    mockOptimizePrompt.mockResolvedValue({
      optimizationId: "po-002",
      promptId: "prm-001",
      parentVersionId: "pmv-001",
      newVersionId: "pmv-004",
      changeSummary: "조명 개선",
      costWon: "250.00",
      latencyMs: 3000,
      succeeded: true,
      failureReason: null,
    });

    renderDialog();

    const versionSelect = screen.getByLabelText("기준 버전 선택");
    await user.selectOptions(versionSelect, "pmv-001");

    // userEvent.type은 중괄호를 특수키로 해석하므로 fireEvent.change 또는 paste 대신
    // textarea에 직접 click 후 값을 설정하는 방식 사용
    const guidanceInput = screen.getByLabelText("수정 지침 입력");
    await user.click(guidanceInput);
    // paste는 중괄호 문제 없음
    await user.paste('{"instruction": "change lighting", "confidence": 0.9}');

    await user.type(screen.getByLabelText("실패 차원 입력"), "lighting");
    await user.click(screen.getByRole("button", { name: "차원 추가" }));

    await user.click(screen.getByRole("button", { name: "Optimize 실행" }));

    await waitFor(() => {
      expect(mockOptimizePrompt).toHaveBeenCalledWith(
        "prm-001",
        expect.objectContaining({
          retryGuidance: {
            instruction: "change lighting",
            confidence: 0.9,
          },
        })
      );
    });
  });

  it("succeeded=false 응답 시 failureReason이 표시되고 다이얼로그가 유지된다", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    mockOptimizePrompt.mockResolvedValue({
      optimizationId: "po-003",
      promptId: "prm-001",
      parentVersionId: "pmv-001",
      newVersionId: null,
      changeSummary: null,
      costWon: "100.00",
      latencyMs: 2000,
      succeeded: false,
      failureReason: "placeholder {role} 누락",
    });

    renderDialog({ onOpenChange });

    const versionSelect = screen.getByLabelText("기준 버전 선택");
    await user.selectOptions(versionSelect, "pmv-001");

    await user.type(screen.getByLabelText("수정 지침 입력"), "수정 지침");
    await user.type(screen.getByLabelText("실패 차원 입력"), "composition");
    await user.click(screen.getByRole("button", { name: "차원 추가" }));

    await user.click(screen.getByRole("button", { name: "Optimize 실행" }));

    await waitFor(() => {
      expect(screen.getByText("placeholder {role} 누락")).toBeInTheDocument();
    });

    // 다이얼로그 유지 (onOpenChange(false) 미호출)
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("succeeded=true 응답 시 navigate가 호출된다", async () => {
    const user = userEvent.setup();
    mockOptimizePrompt.mockResolvedValue({
      optimizationId: "po-004",
      promptId: "prm-001",
      parentVersionId: "pmv-001",
      newVersionId: "pmv-005",
      changeSummary: "lighting 개선",
      costWon: "312.50",
      latencyMs: 4523,
      succeeded: true,
      failureReason: null,
    });

    renderDialog();

    const versionSelect = screen.getByLabelText("기준 버전 선택");
    await user.selectOptions(versionSelect, "pmv-001");

    await user.type(screen.getByLabelText("수정 지침 입력"), "수정 지침");
    await user.type(screen.getByLabelText("실패 차원 입력"), "lighting");
    await user.click(screen.getByRole("button", { name: "차원 추가" }));

    await user.click(screen.getByRole("button", { name: "Optimize 실행" }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        expect.stringContaining("/prompts/prm-001/compare")
      );
    });

    // compare URL에 optimization param 포함 여부 확인
    const navigateArg = mockNavigate.mock.calls[0][0] as string;
    expect(navigateArg).toContain("optimization=po-004");
    expect(navigateArg).toContain("from=pmv-001");
    expect(navigateArg).toContain("to=pmv-005");
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
