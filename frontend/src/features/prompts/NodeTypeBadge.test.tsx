import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NodeTypeBadge } from "./NodeTypeBadge";

describe("NodeTypeBadge", () => {
  it("text 타입 — label과 aria-label 표시", () => {
    render(<NodeTypeBadge nodeType="text" />);
    expect(screen.getByLabelText("노드 타입: Text")).toBeInTheDocument();
  });

  it("image 타입 — label 표시", () => {
    render(<NodeTypeBadge nodeType="image" />);
    expect(screen.getByText("Image")).toBeInTheDocument();
  });

  it("video 타입 — label 표시", () => {
    render(<NodeTypeBadge nodeType="video" />);
    expect(screen.getByText("Video")).toBeInTheDocument();
  });

  it("composition 타입 — label 표시", () => {
    render(<NodeTypeBadge nodeType="composition" />);
    expect(screen.getByText("Composition")).toBeInTheDocument();
  });

  it("임의 hex 없음 — 컬러 배지 클래스 토큰만 사용", () => {
    const { container } = render(<NodeTypeBadge nodeType="text" />);
    const html = container.innerHTML;
    // 임의 hex 검증
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,6}\b/);
  });
});
