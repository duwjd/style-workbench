import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { RetryTimeline } from "./RetryTimeline";
import type { RetryAttemptList } from "@/types";

// ─── Fixture helpers ──────────────────────────────────────────────────────────

function makeAttempt(
  overrides: Partial<RetryAttemptList["attempts"][number]> = {}
): RetryAttemptList["attempts"][number] {
  return {
    id: "rta-1",
    nodeId: "img1",
    attemptNumber: 0,
    promptVersionIdUsed: null,
    retryGuidance: null,
    evaluationId: "eval-1",
    costWon: "12500.00",
    passed: true,
    failedDimensions: [],
    startedAt: "2026-05-08T03:14:22Z",
    finishedAt: "2026-05-08T03:15:01Z",
    ...overrides,
  };
}

function makeList(
  attempts: RetryAttemptList["attempts"],
  extra: Partial<RetryAttemptList> = {}
): RetryAttemptList {
  return {
    runId: "run-1",
    attempts,
    totalAttempts: attempts.length,
    succeeded: null,
    ...extra,
  };
}

function renderTimeline(
  props: Partial<Parameters<typeof RetryTimeline>[0]> = {}
) {
  return render(
    <MemoryRouter>
      <RetryTimeline
        data={undefined}
        isLoading={false}
        isError={false}
        {...props}
      />
    </MemoryRouter>
  );
}

// ─── 테스트 ───────────────────────────────────────────────────────────────────

describe("RetryTimeline", () => {
  it("attempt가 0건이면 섹션을 렌더링하지 않는다", () => {
    const { container } = renderTimeline({
      data: makeList([]),
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("data가 undefined이고 isLoading=false이면 렌더링하지 않는다", () => {
    const { container } = renderTimeline({ data: undefined, isLoading: false });
    expect(container).toBeEmptyDOMElement();
  });

  it("isLoading=true이면 스켈레톤을 표시한다", () => {
    renderTimeline({ isLoading: true });
    expect(screen.getByLabelText("로딩 중")).toBeInTheDocument();
  });

  it("isError=true이면 에러 메시지를 표시한다", () => {
    renderTimeline({ isError: true });
    expect(
      screen.getByText(/재시도 이력을 불러오지 못했습니다/)
    ).toBeInTheDocument();
  });

  it("PASS attempt 카드를 렌더링한다", () => {
    renderTimeline({
      data: makeList([makeAttempt({ passed: true })]),
    });
    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.getByText("Attempt #1")).toBeInTheDocument();
  });

  it("FAIL attempt 카드를 렌더링한다", () => {
    renderTimeline({
      data: makeList([
        makeAttempt({
          passed: false,
          failedDimensions: ["composition", "lighting"],
        }),
      ]),
    });
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText("composition")).toBeInTheDocument();
    expect(screen.getByText("lighting")).toBeInTheDocument();
  });

  it("passed=null(예산 초과)이면 '예산 초과' 배지를 표시한다", () => {
    renderTimeline({
      data: makeList([makeAttempt({ passed: null })]),
    });
    expect(screen.getByText("예산 초과")).toBeInTheDocument();
  });

  it("promptVersionIdUsed가 null이면 '(inline prompt)'를 표시한다", () => {
    renderTimeline({
      data: makeList([makeAttempt({ promptVersionIdUsed: null })]),
    });
    expect(screen.getByText("(inline prompt)")).toBeInTheDocument();
  });

  it("promptVersionIdUsed가 있으면 링크를 렌더링한다", () => {
    renderTimeline({
      data: makeList([
        makeAttempt({ promptVersionIdUsed: "pmv_01JX00000001" }),
      ]),
    });
    const link = screen.getByRole("link", { name: /프롬프트 버전/ });
    expect(link).toHaveAttribute("href", "/prompts/pmv_01JX00000001");
  });

  it("retryGuidance 토글 클릭 시 가이던스를 펼친다", () => {
    renderTimeline({
      data: makeList([
        makeAttempt({
          retryGuidance: {
            instruction: "주광원을 좌측으로 변경",
            confidence: 0.82,
          },
        }),
      ]),
    });

    const toggleBtn = screen.getByRole("button", { name: /재시도 가이던스/ });
    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("주광원을 좌측으로 변경")).toBeInTheDocument();
  });

  it("비용을 '원' 단위 포맷으로 표시한다", () => {
    renderTimeline({
      data: makeList([makeAttempt({ costWon: "12500.00" })]),
    });
    expect(screen.getByText("12,500원")).toBeInTheDocument();
  });

  it("소요 시간을 '초' 단위로 표시한다", () => {
    renderTimeline({
      data: makeList([
        makeAttempt({
          startedAt: "2026-05-08T03:14:22Z",
          finishedAt: "2026-05-08T03:15:00Z",
        }),
      ]),
    });
    expect(screen.getByText("38초")).toBeInTheDocument();
  });

  it("finishedAt이 null이면 '진행 중' 표시", () => {
    renderTimeline({
      data: makeList([makeAttempt({ finishedAt: null })]),
    });
    expect(screen.getByText("진행 중")).toBeInTheDocument();
  });

  it("같은 nodeId의 attempt들을 하나의 그룹으로 묶는다", () => {
    renderTimeline({
      data: makeList([
        makeAttempt({ id: "rta-1", attemptNumber: 0, nodeId: "img1" }),
        makeAttempt({ id: "rta-2", attemptNumber: 1, nodeId: "img1" }),
      ]),
    });
    // "img1" 헤더가 1개만 있어야 함
    const headers = screen.getAllByText("img1");
    expect(headers).toHaveLength(1);
    // Attempt #1, #2 모두 표시
    expect(screen.getByText("Attempt #1")).toBeInTheDocument();
    expect(screen.getByText("Attempt #2")).toBeInTheDocument();
  });

  it("다른 nodeId는 별도 그룹으로 분리된다", () => {
    renderTimeline({
      data: makeList([
        makeAttempt({ id: "rta-1", nodeId: "img1", passed: true }),
        makeAttempt({ id: "rta-2", nodeId: "text1", passed: false }),
      ]),
    });
    expect(screen.getByText("img1")).toBeInTheDocument();
    expect(screen.getByText("text1")).toBeInTheDocument();
  });

  it("총 시도 횟수를 헤더에 표시한다", () => {
    renderTimeline({
      data: makeList(
        [makeAttempt({ id: "rta-1" }), makeAttempt({ id: "rta-2" })],
        { totalAttempts: 2 }
      ),
    });
    expect(screen.getByText("총 2회 시도")).toBeInTheDocument();
  });

  // ─── 시나리오 회귀 (50개 케이스 압축) ────────────────────────────────────

  it.each(
    Array.from({ length: 50 }, (_, i) => {
      const passed: boolean | null =
        i % 3 === 0 ? true : i % 3 === 1 ? false : null;
      return {
        label: `scenario-${i}`,
        attempt: makeAttempt({
          id: `rta-${i}`,
          attemptNumber: i % 4,
          passed,
          failedDimensions:
            passed === false ? [`dim-${i % 5}`] : [],
          costWon: `${(i + 1) * 1000}.00`,
          promptVersionIdUsed:
            i % 2 === 0 ? `pmv_0000000${String(i).padStart(3, "0")}` : null,
        }),
      };
    })
  )("렌더링 회귀: $label", ({ attempt }) => {
    const { container } = renderTimeline({
      data: makeList([attempt]),
    });
    // 렌더 중 오류 없이 DOM이 비어있지 않음
    expect(container).not.toBeEmptyDOMElement();
  });
});
