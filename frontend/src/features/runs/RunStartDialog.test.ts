import { describe, it, expect } from "vitest";
import { collectUserInputFields } from "./RunStartDialog";
import type { Node } from "@xyflow/react";

function makeNode(id: string, variableMapping: Record<string, unknown>): Node {
  return {
    id,
    type: "text_generation",
    position: { x: 0, y: 0 },
    data: { variableMapping },
  };
}

describe("collectUserInputFields", () => {
  it("빈 노드 배열이면 빈 배열", () => {
    expect(collectUserInputFields([])).toEqual([]);
  });

  it("variableMapping 없는 노드는 스킵", () => {
    const nodes: Node[] = [
      { id: "n1", type: "text_generation", position: { x: 0, y: 0 }, data: {} },
    ];
    expect(collectUserInputFields(nodes)).toEqual([]);
  });

  it("user_input 소스 변수만 수집", () => {
    const nodes = [
      makeNode("n1", {
        name: { source: "user_input", role: "text" },
        style: { source: "constant", value: "warm" },
      }),
    ];
    const result = collectUserInputFields(nodes);
    expect(result).toEqual([{ variable: "name", role: "text" }]);
  });

  it("node_output 소스는 수집하지 않음", () => {
    const nodes = [
      makeNode("n1", {
        photo: { source: "node_output", nodeId: "n2" },
      }),
    ];
    expect(collectUserInputFields(nodes)).toEqual([]);
  });

  it("여러 노드에서 user_input 변수 수집", () => {
    const nodes = [
      makeNode("n1", {
        name: { source: "user_input", role: "text" },
      }),
      makeNode("n2", {
        photo: { source: "user_input", role: "photo" },
      }),
    ];
    const result = collectUserInputFields(nodes);
    expect(result).toHaveLength(2);
    expect(result).toContainEqual({ variable: "name", role: "text" });
    expect(result).toContainEqual({ variable: "photo", role: "photo" });
  });

  it("여러 노드에서 같은 변수명이 중복되면 한 번만 수집", () => {
    const nodes = [
      makeNode("n1", { name: { source: "user_input", role: "text" } }),
      makeNode("n2", { name: { source: "user_input", role: "name" } }),
    ];
    const result = collectUserInputFields(nodes);
    expect(result).toHaveLength(1);
    expect(result[0].variable).toBe("name");
  });

  it("role이 없으면 'text'로 fallback", () => {
    const nodes = [
      makeNode("n1", { subject: { source: "user_input" } }),
    ];
    const result = collectUserInputFields(nodes);
    expect(result[0].role).toBe("text");
  });
});
