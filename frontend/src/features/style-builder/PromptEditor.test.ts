import { describe, it, expect } from "vitest";
import { extractVariables } from "./PromptEditor";

describe("extractVariables — {placeholder} 정규식 추출", () => {
  it("빈 문자열이면 빈 배열 반환", () => {
    expect(extractVariables("")).toEqual([]);
  });

  it("변수 없는 일반 텍스트", () => {
    expect(extractVariables("Hello world, no variables here.")).toEqual([]);
  });

  it("단일 변수 추출", () => {
    expect(extractVariables("Hello {name}")).toEqual(["name"]);
  });

  it("복수 변수 추출", () => {
    expect(extractVariables("{subject} in {style} style, {mood} mood")).toEqual([
      "subject",
      "style",
      "mood",
    ]);
  });

  it("중복 변수는 한 번만 반환", () => {
    expect(extractVariables("{name} and {name} again")).toEqual(["name"]);
  });

  it("숫자 포함 변수명 지원 (\\w+)", () => {
    expect(extractVariables("{var1} {var2}")).toEqual(["var1", "var2"]);
  });

  it("언더스코어 포함 변수명 지원", () => {
    expect(extractVariables("{user_name} {photo_url}")).toEqual([
      "user_name",
      "photo_url",
    ]);
  });

  it("{{escaped}} 형태도 내부 변수명을 추출함 ({word} 패턴이 매칭되므로)", () => {
    // {{escaped}} 는 \{(\w+)\} 패턴으로 {escaped} 가 매칭됨
    // Jinja2 스타일 이스케이프는 현재 구현 범위 밖임
    const result = extractVariables("{{escaped}} and {valid}");
    expect(result).toContain("escaped");
    expect(result).toContain("valid");
  });

  it("공백이 포함된 placeholder는 추출하지 않음 (\\w+은 공백 불포함)", () => {
    expect(extractVariables("{has space}")).toEqual([]);
  });

  it("여러 줄 템플릿", () => {
    const template = `
      안녕하세요, {name}님.
      당신의 {style} 스타일 사진을 {tone} 톤으로 생성합니다.
      참고 이미지: {photo}
    `;
    expect(extractVariables(template)).toEqual(["name", "style", "tone", "photo"]);
  });
});
