import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { PromptBodyEditor } from "./PromptBodyEditor";
import type { DeclaredVariable } from "@/types/prompts";

describe("PromptBodyEditor — placeholder 검증", () => {
  const noop = vi.fn();

  it("선언된 변수가 모두 body에 있으면 성공 메시지", () => {
    const vars: DeclaredVariable[] = [
      { name: "name", role: "person_name", required: true },
    ];
    render(
      <PromptBodyEditor
        body="Hello {name}"
        onChange={noop}
        declaredVariables={vars}
      />
    );
    expect(screen.getByText(/모든 변수가 선언되었습니다/)).toBeInTheDocument();
  });

  it("body에 있지만 선언 안 된 변수는 빨간 배지", () => {
    render(
      <PromptBodyEditor
        body="Hello {name}"
        onChange={noop}
        declaredVariables={[]}
      />
    );
    // 미선언 경고가 나타나야 함
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/미선언 변수/)).toBeInTheDocument();
  });

  it("선언됐지만 body에 없는 변수는 경고", () => {
    const vars: DeclaredVariable[] = [
      { name: "role", role: "job_title", required: true },
    ];
    render(
      <PromptBodyEditor
        body="Hello world"
        onChange={noop}
        declaredVariables={vars}
      />
    );
    expect(screen.getByText(/선언되었지만 본문에 없는 변수/)).toBeInTheDocument();
  });

  it("서버 경고 chips 표시", () => {
    render(
      <PromptBodyEditor
        body="Hello"
        onChange={noop}
        declaredVariables={[]}
        warnings={["의심스러운 패턴 {0} 발견"]}
      />
    );
    expect(screen.getByText("의심스러운 패턴 {0} 발견")).toBeInTheDocument();
  });

  it("readOnly 시 textarea가 읽기 전용", () => {
    render(
      <PromptBodyEditor
        body="Hello {name}"
        onChange={noop}
        declaredVariables={[{ name: "name", role: "", required: true }]}
        readOnly
      />
    );
    const textarea = screen.getByRole("textbox", { name: "프롬프트 본문" });
    // readOnly prop은 HTML attribute "readonly"로 반영됨
    expect(textarea).toHaveAttribute("readonly");
  });
});
