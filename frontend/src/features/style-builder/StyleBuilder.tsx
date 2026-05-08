import { useCallback, useEffect } from "react";
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
import { useUiStore } from "@/stores/uiStore";
import { NodePalette } from "./NodePalette";
import { PromptEditor } from "./PromptEditor";
import { TextNode } from "./nodes/TextNode";
import { ImageNode } from "./nodes/ImageNode";
import { VideoNode } from "./nodes/VideoNode";
import { CompositionNode } from "./nodes/CompositionNode";
import type { StyleDetail, DagNode } from "@/types";

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

interface StyleBuilderInnerProps {
  style: StyleDetail;
}

function StyleBuilderInner({ style }: StyleBuilderInnerProps) {
  const { selectedNodeId, setSelectedNodeId } = useUiStore();
  const { screenToFlowPosition } = useReactFlow();

  const initialNodes: Node[] = style.dag.nodes.map(dagNodeToFlowNode);
  const initialEdges: Edge[] = style.dag.edges.map(dagEdgeToFlowEdge);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

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

  // 키보드 단축키
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const isMeta = e.metaKey || e.ctrlKey;

      // Cmd/Ctrl + S — 저장
      if (isMeta && e.key === "s") {
        e.preventDefault();
        console.log("save", { nodes, edges });
        toast.success("저장되었습니다. (DAG 저장 API 준비 중)");
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
  }, [nodes, edges, selectedNodeId, setNodes, setEdges, setSelectedNodeId]);

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
      </div>

      {selectedNodeId && (
        <PromptEditor
          selectedNodeId={selectedNodeId}
          nodes={nodes}
          onClose={() => setSelectedNodeId(null)}
          onUpdateNode={onUpdateNode}
        />
      )}
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
