import { cn } from "@/lib/utils";

const PALETTE_ITEMS = [
  {
    type: "text_generation",
    label: "Text",
    dotColor: "bg-node-text",
    description: "텍스트 생성",
  },
  {
    type: "image_generation",
    label: "Image",
    dotColor: "bg-node-image",
    description: "이미지 생성",
  },
  {
    type: "video_generation",
    label: "Video",
    dotColor: "bg-node-video",
    description: "비디오 생성",
  },
  {
    type: "composition",
    label: "Composition",
    dotColor: "bg-node-comp",
    description: "컴포지션",
  },
] as const;

export function NodePalette() {
  return (
    <aside
      className="w-48 bg-bg-surface border-r border-border-subtle flex flex-col shrink-0"
      aria-label="노드 팔레트"
    >
      <div className="px-3 py-2 border-b border-border-subtle">
        <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          노드
        </p>
      </div>

      <div className="p-2 space-y-1">
        {PALETTE_ITEMS.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("nodeType", item.type);
              e.dataTransfer.effectAllowed = "copy";
            }}
            className={cn(
              "flex items-center gap-2 p-2 rounded cursor-grab",
              "hover:bg-bg-hover transition-colors",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
              "active:cursor-grabbing"
            )}
            role="button"
            tabIndex={0}
            aria-label={`${item.label} 노드 드래그하여 추가`}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
              }
            }}
          >
            <span
              className={cn("h-2 w-2 rounded-full shrink-0", item.dotColor)}
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="text-sm text-text-primary leading-tight">
                {item.label}
              </p>
              <p className="text-xs text-text-tertiary">{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
