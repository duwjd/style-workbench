import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreChip } from "./ScoreChip";

describe("ScoreChip — F05 §7.5 점수 색상 분기", () => {
  it("null이면 em-dash 표시", () => {
    render(<ScoreChip score={null} />);
    expect(screen.getByLabelText("점수 없음")).toBeInTheDocument();
  });

  it("0.0 점 — error 색상 (≤0.5)", () => {
    const { container } = render(<ScoreChip score={0.0} />);
    expect(container.querySelector(".text-error")).not.toBeNull();
  });

  it("0.5 점 — error 색상 (경계: <0.5는 error, >=0.5는 warning)", () => {
    const { container } = render(<ScoreChip score={0.5} />);
    // 0.5는 warning
    expect(container.querySelector(".text-warning")).not.toBeNull();
  });

  it("0.49 점 — error 색상", () => {
    const { container } = render(<ScoreChip score={0.49} />);
    expect(container.querySelector(".text-error")).not.toBeNull();
  });

  it("0.7 점 — warning 색상", () => {
    const { container } = render(<ScoreChip score={0.7} />);
    expect(container.querySelector(".text-warning")).not.toBeNull();
  });

  it("0.75 점 — success 색상 (경계: ≥0.75)", () => {
    const { container } = render(<ScoreChip score={0.75} />);
    expect(container.querySelector(".text-success")).not.toBeNull();
  });

  it("1.0 점 — success 색상", () => {
    const { container } = render(<ScoreChip score={1.0} />);
    expect(container.querySelector(".text-success")).not.toBeNull();
  });

  it("점수가 퍼센트로 표시 (0.84 → 84)", () => {
    render(<ScoreChip score={0.84} />);
    expect(screen.getByText("84")).toBeInTheDocument();
  });
});
