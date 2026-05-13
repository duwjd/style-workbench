import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import { StyleBuilder } from "./StyleBuilder";
import type { StyleDetail } from "@/types";

// React Flow requires ResizeObserver and requestAnimationFrame in test env
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Minimal style fixture
const makeStyle = (id = "style-1"): StyleDetail => ({
  id,
  name: "Test Style",
  concept: "test",
  vertical: "portrait",
  tags: [],
  status: "draft",
  currentVersion: 1,
  versionId: "v1",
  createdAt: new Date().toISOString(),
  dag: {
    nodes: [
      {
        id: "n1",
        type: "text_generation",
        model: { provider: "anthropic", modelId: "claude-sonnet-4-6" },
        promptTemplate: "hello {concept}",
        inputs: [],
      },
    ],
    edges: [],
    variables: ["concept"],
  },
});

// Mock @xyflow/react to avoid full canvas setup in jsdom
vi.mock("@xyflow/react", async () => {
  const actual = await vi.importActual<typeof import("@xyflow/react")>("@xyflow/react");
  return {
    ...actual,
    ReactFlow: vi.fn(({ nodes, onNodesChange }) => (
      <div data-testid="mock-reactflow" data-node-count={nodes?.length ?? 0}>
        <button
          data-testid="trigger-drag"
          onClick={() => {
            // Simulate a position change (drag) event
            if (onNodesChange) {
              onNodesChange([{ id: "n1", type: "position", position: { x: 200, y: 300 }, dragging: false }]);
            }
          }}
        >
          drag
        </button>
      </div>
    )),
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    useNodesState: actual.useNodesState,
    useEdgesState: actual.useEdgesState,
    addEdge: actual.addEdge,
    BackgroundVariant: actual.BackgroundVariant,
    useReactFlow: () => ({ screenToFlowPosition: (p: { x: number; y: number }) => p }),
  };
});

// Mock Zustand store
vi.mock("@/stores/uiStore", () => ({
  useUiStore: vi.fn(() => ({
    selectedNodeId: null,
    setSelectedNodeId: vi.fn(),
  })),
}));

// Mock TanStack Query
const mockMutate = vi.fn();
vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query");
  return {
    ...actual,
    useMutation: vi.fn(() => ({
      mutate: mockMutate,
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
    })),
    useQueryClient: vi.fn(() => ({
      invalidateQueries: vi.fn(),
    })),
  };
});

// Mock react-router navigate
const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock API modules
vi.mock("@/api/styles", () => ({
  stylesApi: {
    saveDag: vi.fn(() =>
      Promise.resolve({ versionId: "v2", version: 2, currentVersion: 2, createdAt: new Date().toISOString() })
    ),
  },
}));

vi.mock("@/api/runs", () => ({
  runsApi: {
    create: vi.fn(() =>
      Promise.resolve({ id: "run-1", styleVersionId: "v2", styleId: "style-1", status: "pending", totalCost: null, createdAt: new Date().toISOString(), startedAt: null, finishedAt: null, nodeExecutions: [] })
    ),
  },
  subscribeRun: vi.fn(() => () => {}),
}));

// RunStartDialog mock — 실제 Dialog 대신 간단한 div (Portal 불필요)
vi.mock("@/features/runs/RunStartDialog", () => ({
  RunStartDialog: vi.fn(({ open }: { open: boolean }) =>
    open ? <div data-testid="run-start-dialog">Run Dialog</div> : null
  ),
}));

describe("StyleBuilder — initial nodes stability", () => {
  it("renders without crashing with a single text node", () => {
    const { getByTestId } = render(<StyleBuilder style={makeStyle()} />);
    expect(getByTestId("mock-reactflow")).toBeInTheDocument();
  });

  it("passes correct node count to ReactFlow", () => {
    const { getByTestId } = render(<StyleBuilder style={makeStyle()} />);
    const rf = getByTestId("mock-reactflow");
    expect(rf.getAttribute("data-node-count")).toBe("1");
  });

  it("onNodesChange fires without error when drag position event is simulated", () => {
    const { getByTestId } = render(<StyleBuilder style={makeStyle()} />);
    const btn = getByTestId("trigger-drag");
    // Should not throw
    expect(() => btn.click()).not.toThrow();
  });

  it("re-render with same style.id does not reset nodes", () => {
    const style = makeStyle("style-stable");
    const { rerender, getByTestId } = render(<StyleBuilder style={style} />);
    // Rerender with a new object reference but same id (simulates TanStack Query fresh ref)
    const sameIdNewRef: StyleDetail = { ...style, name: "Updated Name" };
    rerender(<StyleBuilder style={sameIdNewRef} />);
    // Node count should stay the same (not reset)
    expect(getByTestId("mock-reactflow").getAttribute("data-node-count")).toBe("1");
  });
});

describe("StyleBuilder — save and run", () => {
  it("renders 실행 button", () => {
    const { getByRole } = render(<StyleBuilder style={makeStyle()} />);
    const runBtn = getByRole("button", { name: /실행/i });
    expect(runBtn).toBeInTheDocument();
  });

  it("shows 저장됨 indicator initially", () => {
    const { getByLabelText } = render(<StyleBuilder style={makeStyle()} />);
    expect(getByLabelText("저장됨")).toBeInTheDocument();
  });

  it("shows 저장 안됨 indicator after nodes change", async () => {
    const { getByTestId, getByLabelText } = render(<StyleBuilder style={makeStyle()} />);
    // Simulate a drag (position change) which triggers nodes update → dirty
    fireEvent.click(getByTestId("trigger-drag"));
    await waitFor(() => {
      expect(getByLabelText("저장되지 않은 변경 있음")).toBeInTheDocument();
    });
  });

  it("clicking 실행 button opens RunStartDialog", async () => {
    const { getByRole, queryByTestId, findByTestId } = render(
      <StyleBuilder style={makeStyle()} />
    );
    // dialog initially closed
    expect(queryByTestId("run-start-dialog")).toBeNull();

    const runBtn = getByRole("button", { name: /실행/i });
    fireEvent.click(runBtn);

    // dialog should be open after click
    expect(await findByTestId("run-start-dialog")).toBeInTheDocument();
  });
});
