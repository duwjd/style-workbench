import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { NodeExecution } from "@/types";

interface StageCellProps {
  execution: NodeExecution | undefined;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; className: string }
> = {
  pending: {
    label: "대기 중",
    className: "bg-bg-elevated text-text-secondary border border-border-default",
  },
  running: {
    label: "실행 중",
    className: "bg-info/15 text-info border border-info/30",
  },
  succeeded: {
    label: "완료",
    className: "bg-success/15 text-success border border-success/30",
  },
  failed: {
    label: "실패",
    className: "bg-error/15 text-error border border-error/30",
  },
};

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG["pending"];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium",
        config.className
      )}
    >
      {config.label}
    </span>
  );
}

export function StageCell({ execution }: StageCellProps) {
  if (!execution) {
    return (
      <div className="p-2">
        <Skeleton className="w-full h-32 bg-bg-elevated" />
      </div>
    );
  }

  const { artifactUrl, nodeType, status } = execution;

  function renderArtifact() {
    if (!artifactUrl) {
      return <Skeleton className="w-full h-32 bg-bg-elevated" />;
    }

    if (nodeType === "image_generation" || nodeType === "composition") {
      return (
        <img
          src={artifactUrl}
          alt={`${nodeType} 결과물`}
          className="w-full h-auto rounded object-cover"
        />
      );
    }

    if (nodeType === "video_generation") {
      return (
        <video
          src={artifactUrl}
          controls
          className="w-full rounded"
          aria-label={`${nodeType} 결과물`}
        />
      );
    }

    // text_generation — artifact_url이 텍스트 내용을 담거나 URL일 수 있음
    return (
      <div className="rounded border border-border-subtle bg-bg-elevated p-2">
        <p className="text-text-primary text-xs break-words">{artifactUrl}</p>
      </div>
    );
  }

  return (
    <div className="p-2 space-y-2">
      {renderArtifact()}
      <div className="flex items-center justify-between">
        <StatusBadge status={status} />
        {execution.cost != null && (
          <span className="text-xs text-text-tertiary">
            ${execution.cost.toFixed(4)}
          </span>
        )}
      </div>
    </div>
  );
}
