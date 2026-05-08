import { Skeleton } from "@/components/ui/skeleton";
import { StageCell } from "./StageCell";
import { cn } from "@/lib/utils";
import type { Run, NodeExecution } from "@/types";

interface ComparisonGridProps {
  run: Run | null;
}

const NODE_TYPE_LABELS: Record<string, string> = {
  text_generation: "Text",
  image_generation: "Image",
  video_generation: "Video",
  composition: "Composition",
};

const NODE_TYPE_DOT: Record<string, string> = {
  text_generation: "bg-node-text",
  image_generation: "bg-node-image",
  video_generation: "bg-node-video",
  composition: "bg-node-comp",
};

function groupByType(executions: NodeExecution[]): {
  type: string;
  executions: NodeExecution[];
}[] {
  const order = [
    "text_generation",
    "image_generation",
    "video_generation",
    "composition",
  ];
  const map = new Map<string, NodeExecution[]>();

  for (const exec of executions) {
    const key = exec.nodeType;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(exec);
  }

  const result: { type: string; executions: NodeExecution[] }[] = [];
  for (const type of order) {
    if (map.has(type)) {
      result.push({ type, executions: map.get(type)! });
    }
  }
  // 나머지 타입
  for (const [type, execs] of map) {
    if (!order.includes(type)) {
      result.push({ type, executions: execs });
    }
  }

  return result;
}

function GridSkeleton() {
  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-6 w-24 bg-bg-elevated" />
            <Skeleton className="h-32 w-full bg-bg-elevated" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ComparisonGrid({ run }: ComparisonGridProps) {
  if (!run) {
    return <GridSkeleton />;
  }

  const columns = groupByType(run.nodeExecutions);

  if (columns.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-text-tertiary text-sm">실행 결과가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-4">
      <div
        className={cn(
          "grid gap-3",
          `grid-cols-${Math.min(columns.length, 4)}`
        )}
        style={{
          gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))`,
        }}
      >
        {columns.map(({ type, executions }) => (
          <div
            key={type}
            className="rounded-lg border border-border-subtle bg-bg-surface overflow-hidden"
          >
            {/* 컬럼 헤더 */}
            <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
              <span
                className={cn(
                  "h-2 w-2 rounded-full shrink-0",
                  NODE_TYPE_DOT[type] ?? "bg-bg-elevated"
                )}
                aria-hidden="true"
              />
              <span className="text-xs font-medium text-text-primary">
                {NODE_TYPE_LABELS[type] ?? type}
              </span>
              <span className="text-xs text-text-tertiary ml-auto">
                {executions.length}개
              </span>
            </div>

            {/* 셀 */}
            {executions.map((exec) => (
              <StageCell key={exec.id} execution={exec} />
            ))}
          </div>
        ))}
      </div>

      {/* 전체 비용 */}
      {run.totalCost != null && (
        <div className="mt-3 flex justify-end">
          <span className="text-xs text-text-tertiary">
            총 비용:{" "}
            <span className="text-text-secondary font-medium">
              ${run.totalCost.toFixed(4)}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
