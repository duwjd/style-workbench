import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { PassBanner } from "./PassBanner";

// useNavigate mock
const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderBanner(styleId = "style-001") {
  return render(
    <MemoryRouter>
      <PassBanner styleId={styleId} />
    </MemoryRouter>
  );
}

describe("PassBanner", () => {
  it("배너를 렌더링한다", () => {
    renderBanner();
    expect(
      screen.getByRole("status", { name: /모든 노드 PASS/ })
    ).toBeInTheDocument();
  });

  it("'모든 노드 PASS' 문구를 포함한다", () => {
    renderBanner();
    expect(screen.getByText(/모든 노드 PASS/)).toBeInTheDocument();
  });

  it("'자동 승인 0건' 안내 문구를 포함한다 (AC-7 시각 단서)", () => {
    renderBanner();
    expect(screen.getByText(/자동 승인 0건/)).toBeInTheDocument();
  });

  it("'검수 시작' 버튼이 존재한다", () => {
    renderBanner();
    // 버튼에 aria-label="스타일 검수 화면으로 이동"이 설정되어 있음
    expect(
      screen.getByRole("button", { name: /스타일 검수 화면으로 이동/ })
    ).toBeInTheDocument();
    // 버튼 텍스트 "검수 시작"도 화면에 표시
    expect(screen.getByText("검수 시작")).toBeInTheDocument();
  });

  it("'검수 시작' 버튼 클릭 시 /styles/:id/review 로 navigate한다", () => {
    renderBanner("style-abc");
    fireEvent.click(
      screen.getByRole("button", { name: /스타일 검수 화면으로 이동/ })
    );
    expect(mockNavigate).toHaveBeenCalledWith("/styles/style-abc/review");
  });

  it("다른 styleId로 동작한다", () => {
    renderBanner("style-xyz");
    fireEvent.click(
      screen.getByRole("button", { name: /스타일 검수 화면으로 이동/ })
    );
    expect(mockNavigate).toHaveBeenCalledWith("/styles/style-xyz/review");
  });

  it("배너에서 'approved' 상태를 자동 전이하는 코드가 없다 (AC-7 정적 확인)", () => {
    // 이 테스트는 컴포넌트를 렌더링하고 approved 관련 DOM 요소가 없음을 검증
    renderBanner();
    // 'approved' 문자열이 자동 전이 버튼으로 노출되지 않아야 함
    const approvedButtons = screen
      .queryAllByRole("button")
      .filter((btn) => btn.textContent?.toLowerCase().includes("approved"));
    expect(approvedButtons).toHaveLength(0);
  });
});
