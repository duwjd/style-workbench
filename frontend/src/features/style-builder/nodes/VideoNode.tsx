import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";

export type VideoNodeData = {
  promptTemplate: string;
  model: { provider: string; modelId: string };
};

export function VideoNode({
  data,
  selected,
}: NodeProps) {
  const nodeData = data as VideoNodeData;
  return (
    <div
      className={cn(
        "w-60 rounded-lg border bg-bg-surface shadow-md",
        "border-border-default",
        selected && "ring-1 ring-accent-500"
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-node-input !border-border-default"
        aria-label="입력 핸들"
      />

      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
        <span
          className="h-2 w-2 rounded-full bg-node-video shrink-0"
          aria-hidden="true"
        />
        <div className="min-w-0">
          <p className="text-xs font-semibold text-text-primary leading-tight">
            Video Generation
          </p>
          {nodeData.model?.provider && (
            <p className="text-xs text-text-tertiary truncate">
              {nodeData.model.provider} / {nodeData.model.modelId}
            </p>
          )}
        </div>
      </div>

      <div className="px-3 py-2">
        <p className="text-xs text-text-secondary line-clamp-3 break-words">
          {nodeData.promptTemplate || (
            <span className="text-text-disabled italic">프롬프트 없음</span>
          )}
        </p>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!bg-node-video !border-border-default"
        aria-label="출력 핸들"
      />
    </div>
  );
}
