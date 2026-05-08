import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Node } from "@xyflow/react";

interface PromptEditorProps {
  selectedNodeId: string | null;
  nodes: Node[];
  onClose: () => void;
  onUpdateNode: (nodeId: string, data: Record<string, unknown>) => void;
}

function extractVariables(template: string): string[] {
  const matches = template.match(/\{([^}]+)\}/g) ?? [];
  return [...new Set(matches.map((m) => m.slice(1, -1)))];
}

const NODE_TYPE_LABELS: Record<string, string> = {
  text_generation: "Text Generation",
  image_generation: "Image Generation",
  video_generation: "Video Generation",
  composition: "Composition",
};

export function PromptEditor({
  selectedNodeId,
  nodes,
  onClose,
  onUpdateNode,
}: PromptEditorProps) {
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  if (!selectedNode) return null;

  const data = selectedNode.data as {
    promptTemplate?: string;
    model?: { provider?: string; modelId?: string };
  };

  const promptTemplate = data.promptTemplate ?? "";
  const variables = extractVariables(promptTemplate);
  const nodeTypeLabel =
    NODE_TYPE_LABELS[selectedNode.type ?? ""] ?? selectedNode.type ?? "노드";

  return (
    <aside
      className="w-72 bg-bg-surface border-l border-border-subtle flex flex-col shrink-0"
      aria-label="노드 편집기"
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle">
        <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          {nodeTypeLabel}
        </p>
        <button
          onClick={onClose}
          className={cn(
            "rounded p-0.5 text-text-tertiary hover:text-text-primary hover:bg-bg-hover",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
            "nodrag nopan"
          )}
          aria-label="편집기 닫기"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* 모델 정보 */}
        {data.model && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-text-secondary">모델</p>
            <div className="rounded border border-border-subtle bg-bg-elevated px-2 py-1.5 space-y-0.5">
              <p className="text-xs text-text-tertiary">
                <span className="text-text-secondary">Provider: </span>
                {data.model.provider || (
                  <span className="text-text-disabled">미설정</span>
                )}
              </p>
              <p className="text-xs text-text-tertiary">
                <span className="text-text-secondary">Model ID: </span>
                {data.model.modelId || (
                  <span className="text-text-disabled">미설정</span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* 프롬프트 편집 */}
        <div className="space-y-1">
          <label
            htmlFor="prompt-template"
            className="text-xs font-medium text-text-secondary"
          >
            프롬프트 템플릿
          </label>
          <textarea
            id="prompt-template"
            value={promptTemplate}
            onChange={(e) => {
              onUpdateNode(selectedNode.id, {
                ...data,
                promptTemplate: e.target.value,
              });
            }}
            placeholder="{subject}를 이용하여 생성하세요..."
            rows={8}
            className={cn(
              "w-full resize-y rounded border border-border-default bg-bg-canvas",
              "px-2 py-1.5 text-xs text-text-primary placeholder:text-text-disabled",
              "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
              "transition-colors nodrag nopan"
            )}
            aria-describedby="prompt-variables-hint"
          />
        </div>

        {/* 변수 목록 */}
        <div className="space-y-1">
          <p
            className="text-xs font-medium text-text-secondary"
            id="prompt-variables-hint"
          >
            감지된 변수
          </p>
          {variables.length === 0 ? (
            <p className="text-xs text-text-disabled">
              {"{variable}"} 형태로 변수를 입력하세요.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {variables.map((v) => (
                <span
                  key={v}
                  className="inline-flex items-center rounded px-2 py-0.5 text-xs bg-accent-500/15 text-accent-300 border border-accent-500/30"
                >
                  {"{"}
                  {v}
                  {"}"}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 노드 ID */}
        <div className="space-y-1">
          <p className="text-xs font-medium text-text-secondary">노드 ID</p>
          <p className="text-xs text-text-disabled font-mono break-all">
            {selectedNode.id}
          </p>
        </div>
      </div>
    </aside>
  );
}
