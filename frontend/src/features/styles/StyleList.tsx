import { Plus, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { StyleListItem } from "@/types";

interface StyleListProps {
  styles: StyleListItem[];
  isLoading: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
}

type StatusKey = "draft" | "approved" | "rejected";

const STATUS_CONFIG: Record<
  StatusKey,
  { label: string; className: string }
> = {
  draft: {
    label: "Draft",
    className: "bg-bg-elevated text-text-secondary border border-border-default",
  },
  approved: {
    label: "Approved",
    className: "bg-success/15 text-success border border-success/30",
  },
  rejected: {
    label: "Rejected",
    className: "bg-error/15 text-error border border-error/30",
  },
};

function StatusBadge({ status }: { status: StatusKey }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium",
        config.className
      )}
      aria-label={`상태: ${config.label}`}
    >
      {config.label}
    </span>
  );
}

function StyleCardSkeleton() {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-surface p-4 space-y-3">
      <div className="flex items-start justify-between">
        <Skeleton className="h-4 w-32 bg-bg-elevated" />
        <Skeleton className="h-5 w-16 bg-bg-elevated rounded" />
      </div>
      <Skeleton className="h-3 w-full bg-bg-elevated" />
      <Skeleton className="h-3 w-3/4 bg-bg-elevated" />
      <div className="flex gap-2 pt-1">
        <Skeleton className="h-4 w-12 bg-bg-elevated rounded" />
        <Skeleton className="h-4 w-12 bg-bg-elevated rounded" />
      </div>
    </div>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <div className="rounded-full bg-bg-elevated p-4">
        <Layers className="h-8 w-8 text-text-tertiary" aria-hidden="true" />
      </div>
      <div className="text-center space-y-1">
        <p className="text-text-primary font-medium">Style이 없습니다</p>
        <p className="text-text-secondary text-sm">
          새 Style을 만들어 시작하세요.
        </p>
      </div>
      <Button onClick={onNew} className="bg-accent-500 hover:bg-accent-600 text-text-on-accent">
        <Plus className="h-4 w-4 mr-1" aria-hidden="true" />
        새 Style
      </Button>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function StyleList({ styles, isLoading, onNew, onSelect }: StyleListProps) {
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Styles</h1>
          <p className="text-text-secondary text-sm mt-0.5">
            {isLoading ? "로딩 중..." : `${styles.length}개의 Style`}
          </p>
        </div>
        <Button
          onClick={onNew}
          className="bg-accent-500 hover:bg-accent-600 text-text-on-accent"
          aria-label="새 Style 만들기"
        >
          <Plus className="h-4 w-4 mr-1" aria-hidden="true" />
          새 Style
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <StyleCardSkeleton key={i} />
          ))}
        </div>
      ) : styles.length === 0 ? (
        <EmptyState onNew={onNew} />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {styles.map((style) => (
            <button
              key={style.id}
              onClick={() => onSelect(style.id)}
              className={cn(
                "rounded-lg border border-border-subtle bg-bg-surface p-4 text-left",
                "hover:bg-bg-hover hover:border-border-default transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                "space-y-3"
              )}
              aria-label={`Style: ${style.name}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-text-primary text-sm leading-tight line-clamp-1">
                  {style.name}
                </span>
                <StatusBadge status={style.status} />
              </div>

              <p className="text-text-secondary text-xs line-clamp-2">
                {style.concept}
              </p>

              <div className="flex flex-wrap gap-1">
                {style.tags.slice(0, 4).map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-bg-elevated text-text-tertiary"
                  >
                    {tag}
                  </span>
                ))}
                {style.tags.length > 4 && (
                  <span className="text-xs text-text-disabled">
                    +{style.tags.length - 4}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between text-xs text-text-tertiary pt-1">
                <span>v{style.currentVersion}</span>
                <span>{formatDate(style.createdAt)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
