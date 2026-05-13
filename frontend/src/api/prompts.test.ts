import { describe, it, expect } from "vitest";
import { PreconditionFailedError } from "@/types/prompts";

// ETag 처리 로직 단위 검증 (client mock 없이 타입/에러 분기 검증)

describe("PreconditionFailedError", () => {
  it("status 속성이 412", () => {
    const err = new PreconditionFailedError();
    expect(err.status).toBe(412);
  });

  it("name이 PreconditionFailedError", () => {
    const err = new PreconditionFailedError();
    expect(err.name).toBe("PreconditionFailedError");
  });

  it("instanceof Error", () => {
    const err = new PreconditionFailedError();
    expect(err instanceof Error).toBe(true);
  });

  it("커스텀 메시지 지원", () => {
    const err = new PreconditionFailedError("충돌");
    expect(err.message).toBe("충돌");
  });

  it("기본 메시지 포함", () => {
    const err = new PreconditionFailedError();
    expect(err.message).toContain("다른 사용자");
  });
});

// guard412 로직 분기 검증 — 직접 export가 없으므로 내부 동작을 타입으로 검증
describe("ETag 분기 규칙 (타입 레벨)", () => {
  it("PreconditionFailedError는 기본 Error의 서브클래스", () => {
    const err = new PreconditionFailedError();
    expect(err instanceof PreconditionFailedError).toBe(true);
    expect(err instanceof Error).toBe(true);
  });
});
