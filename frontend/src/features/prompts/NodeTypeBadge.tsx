import { cn } from "@/lib/utils";
import type { PromptNodeType } from "@/types/prompts";

const NODE_TYPE_META: Record<PromptNodeType, { label: string; colorClass: string }> = {
  text: { label: "Text", colorClass: "bg-node-text/15 text-node-text border-node-text/30" },
  image: { label: "Image", colorClass: "bg-node-image/15 text-node-image border-node-image/30" },
  video: { label: "Video", colorClass: "bg-node-video/15 text-node-video border-node-video/30" },
  composition: { label: "Composition", colorClass: "bg-node-comp/15 text-node-comp border-node-comp/30" },
};

interface NodeTypeBadgeProps {
  nodeType: PromptNodeType;
  className?: string;
}

export function NodeTypeBadge({ nodeType, className }: NodeTypeBadgeProps) {
  const meta = NODE_TYPE_META[nodeType] ?? { label: nodeType, colorClass: "bg-bg-elevated text-text-secondary border-border-subtle" };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        meta.colorClass,
        className
      )}
      aria-label={`노드 타입: ${meta.label}`}
    >
      <span className={cn("mr-1 h-1.5 w-1.5 rounded-full", `bg-node-${nodeType === "composition" ? "comp" : nodeType}`)} aria-hidden="true" />
      {meta.label}
    </span>
  );
}
