import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  ReactFlowProvider,
  useReactFlow,
  BackgroundVariant,
  type Connection,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useUiStore } from "@/stores/uiStore";
import { NodePalette } from "./NodePalette";
import { PromptEditor } from "./PromptEditor";
import { TextNode } from "./nodes/TextNode";
import { ImageNode } from "./nodes/ImageNode";
import { VideoNode } from "./nodes/VideoNode";
import { CompositionNode } from "./nodes/CompositionNode";
import { RunStartDialog } from "@/features/runs/RunStartDialog";
import { Button } from "@/components/ui/button";
import { stylesApi } from "@/api/styles";
import { cn } from "@/lib/utils";
import type { StyleDetail, DagNode, NodeInput, SaveDagPayload } from "@/types";
import type { VariableMappingMap } from "./PromptEditor";

const NODE_TYPES = {
  text_generation: TextNode,
  image_generation: ImageNode,
  video_generation: VideoNode,
  composition: CompositionNode,
};

function dagNodeToFlowNode(dagNode: DagNode, index: number): Node {
  return {
    id: dagNode.id,
    type: dagNode.type,
    position: { x: index * 280 + 40, y: 120 },
    data: {
      promptTemplate: dagNode.promptTemplate,
      model: dagNode.model,
      inputs: dagNode.inputs,
    },
  };
}

function dagEdgeToFlowEdge(dagEdge: { source: string; target: string }, index: number): Edge {
  return {
    id: `edge-${index}-${dagEdge.source}-${dagEdge.target}`,
    source: dagEdge.source,
    target: dagEdge.target,
  };
}

/** {variable} 형태의 변수를 모든 노드에서 추출해 중복 제거 */
function extractVariablesFromNodes(nodes: Node[]): string[] {
  const all: string[] = [];
  for (const n of nodes) {
    const template = (n.data as { promptTemplate?: string }).promptTemplate ?? "";
    const matches = template.match(/\{([^}]+)\}/g) ?? [];
    for (const m of matches) {
      all.push(m.slice(1, -1));
    }
  }
  return [...new Set(all)];
}

/** ReactFlow Node[]를 백엔드 DAG payload로 직렬화 */
function buildDagPayload(nodes: Node[], edges: Edge[]): SaveDagPayload["dag"] {
  return {
    nodes: nodes.map((n) => {
      const d = n.data as {
        model?: { provider: string; modelId: string };
        promptTemplate?: string;
        inputs?: NodeInput[];
        variableMapping?: VariableMappingMap;
      };
      return {
        id: n.id,
        type: n.type ?? "text_generation",
        model: d.model ?? { provider: "", modelId: "" },
        promptTemplate: d.promptTemplate ?? "",
        inputs: d.inputs ?? [],
        variableMapping: d.variableMapping ?? {},
      };
    }),
    edges: edges.map((e) => ({ source: e.source, target: e.target })),
    variables: extractVariablesFromNodes(nodes),
  };
}

interface StyleBuilderInnerProps {
  style: StyleDetail;
}

function StyleBuilderInner({ style }: StyleBuilderInnerProps) {
  const { selectedNodeId, setSelectedNodeId } = useUiStore();
  const { screenToFlowPosition } = useReactFlow();
  const queryClient = useQueryClient();

  // dirty 상태: 마지막 저장 이후 변경이 있으면 true
  const [isDirty, setIsDirty] = useState(false);
  // RunStartDialog 열림 상태
  const [runDialogOpen, setRunDialogOpen] = useState(false);
  // 최신 versionId 추적 — saveDag 성공 시 업데이트
  const latestVersionIdRef = useRef<string>(style.versionId);

  // style.id만 의존 — 마운트 시 초기값으로만 사용. style.dag 변경에 재계산 의도적으로 무시.
  const initialNodes = useMemo<Node[]>(
    () => style.dag.nodes.map(dagNodeToFlowNode),
    [style.id] // intentional: initial value only
  );
  const initialEdges = useMemo<Edge[]>(
    () => style.dag.edges.map(dagEdgeToFlowEdge),
    [style.id] // intentional: initial value only
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // nodes/edges가 바뀌면 dirty 표시 (초기 마운트는 제외)
  const mountedRef = useRef(false);
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    setIsDirty(true);
  }, [nodes, edges]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds));
    },
    [setEdges]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData("nodeType");
      if (!type) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode: Node = {
        id: `node-${Date.now()}`,
        type,
        position,
        data: {
          promptTemplate: "",
          model: { provider: "", modelId: "" },
          inputs: [],
        },
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [screenToFlowPosition, setNodes]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }, []);

  const onUpdateNode = useCallback(
    (nodeId: string, data: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === nodeId ? { ...n, data } : n))
      );
    },
    [setNodes]
  );

  // saveDag mutation
  const { mutate: saveDag, isPending: isSaving } = useMutation({
    mutationFn: () =>
      stylesApi.saveDag(style.id, { dag: buildDagPayload(nodes, edges) }),
    onSuccess: (result) => {
      latestVersionIdRef.current = result.versionId;
      setIsDirty(false);
      toast.success("저장되었습니다.");
      queryClient.invalidateQueries({ queryKey: ["styles", style.id] });
    },
    onError: () => {
      toast.error("저장에 실패했습니다.");
    },
  });

  function openRunDialog() {
    setRunDialogOpen(true);
  }

  // 키보드 단축키
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const isMeta = e.metaKey || e.ctrlKey;

      // Cmd/Ctrl + S — 저장
      if (isMeta && e.key === "s") {
        e.preventDefault();
        if (!isSaving) saveDag();
        return;
      }

      // Cmd/Ctrl + Enter — 실행 다이얼로그
      if (isMeta && e.key === "Enter") {
        e.preventDefault();
        if (!isSaving) openRunDialog();
        return;
      }

      // Delete / Backspace — 선택된 노드 삭제
      if (
        (e.key === "Delete" || e.key === "Backspace") &&
        selectedNodeId &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
        setEdges((eds) =>
          eds.filter(
            (edge) =>
              edge.source !== selectedNodeId &&
              edge.target !== selectedNodeId
          )
        );
        setSelectedNodeId(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    nodes,
    edges,
    selectedNodeId,
    isSaving,
    isDirty,
    saveDag,
    openRunDialog,
    setNodes,
    setEdges,
    setSelectedNodeId,
  ]);

  return (
    <div className="flex h-full">
      <NodePalette />

      <div className="flex-1 relative bg-bg-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={NODE_TYPES}
          nodesDraggable
          elementsSelectable
          onNodeClick={(_, node) => setSelectedNodeId(node.id)}
          onPaneClick={() => setSelectedNodeId(null)}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="var(--color-border-subtle)"
          />
          <Controls
            className="!bg-bg-surface !border-border-default !rounded-lg"
            aria-label="캔버스 컨트롤"
          />
          <MiniMap
            className="!bg-bg-elevated !border-border-default !rounded-lg"
            nodeColor="var(--color-bg-surface)"
            maskColor="var(--color-bg-base)"
          />
        </ReactFlow>

        {/* Style 메타 정보 오버레이 */}
        <div className="absolute top-3 left-3 pointer-events-none">
          <div className="rounded-lg border border-border-subtle bg-bg-surface/90 px-3 py-2 backdrop-blur-sm">
            <p className="text-xs font-medium text-text-primary">{style.name}</p>
            <p className="text-xs text-text-tertiary">v{style.currentVersion}</p>
          </div>
        </div>

        {/* 상단 우측 — dirty 인디케이터 + 실행 버튼 */}
        <div className="absolute top-3 right-3 flex items-center gap-2 pointer-events-auto">
          {/* dirty / saved 인디케이터 */}
          <span
            className={cn(
              "text-xs flex items-center gap-1 select-none",
              isDirty ? "text-warning" : "text-text-tertiary"
            )}
            aria-live="polite"
            aria-label={isDirty ? "저장되지 않은 변경 있음" : "저장됨"}
          >
            <span
              className={cn(
                "inline-block h-1.5 w-1.5 rounded-full",
                isDirty ? "bg-warning" : "bg-text-tertiary"
              )}
              aria-hidden="true"
            />
            {isSaving ? "저장 중..." : isDirty ? "저장 안됨" : "저장됨"}
          </span>

          {/* 실행 버튼 */}
          <Button
            size="sm"
            onClick={openRunDialog}
            disabled={isSaving}
            aria-label="Style 실행 (Cmd+Enter)"
            className={cn(
              "bg-accent-500 hover:bg-accent-600 text-text-on-accent border-transparent",
              "focus-visible:ring-accent-500"
            )}
          >
            <Play className="h-3.5 w-3.5" aria-hidden="true" />
            실행
          </Button>
        </div>
      </div>

      {selectedNodeId && (
        <PromptEditor
          selectedNodeId={selectedNodeId}
          nodes={nodes}
          onClose={() => setSelectedNodeId(null)}
          onUpdateNode={onUpdateNode}
        />
      )}

      <RunStartDialog
        open={runDialogOpen}
        onOpenChange={setRunDialogOpen}
        styleId={style.id}
        nodes={nodes}
        edges={edges.map((e) => ({ source: e.source, target: e.target }))}
        versionId={latestVersionIdRef.current}
        isDirty={isDirty}
        buildDagPayload={() => buildDagPayload(nodes, edges)}
        onAfterSave={(newVersionId) => {
          latestVersionIdRef.current = newVersionId;
          setIsDirty(false);
          queryClient.invalidateQueries({ queryKey: ["styles", style.id] });
          toast.success("저장되었습니다.");
        }}
      />
    </div>
  );
}

interface StyleBuilderProps {
  style: StyleDetail;
}

export function StyleBuilder({ style }: StyleBuilderProps) {
  return (
    <ReactFlowProvider>
      <StyleBuilderInner style={style} />
    </ReactFlowProvider>
  );
}
