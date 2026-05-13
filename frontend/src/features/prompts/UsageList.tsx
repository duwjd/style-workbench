import { useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { promptsApi } from "@/api/prompts";
import { ScoreChip } from "./ScoreChip";
import { cn } from "@/lib/utils";
import { ExternalLink, Pin, Loader2 } from "lucide-react";
import type { PromptUsageResponse } from "@/types/prompts";

interface UsageListProps {
  promptId: string;
  /** 초기 usages (≤20건, GET /api/prompts/{id} 응답에 포함) */
  initialUsages: PromptUsageResponse[];
  totalCount: number;
}

export function UsageList({ promptId, initialUsages, totalCount }: UsageListProps) {
  const [showAll, setShowAll] = useState(false);
  const [offset, setOffset] = useState(20);

  const { data: extraData, isLoading: extraLoading } = useQuery({
    queryKey: ["prompts", promptId, "usages", offset],
    queryFn: () => promptsApi.listUsages(promptId, 20, offset),
    enabled: showAll && totalCount > 20,
    staleTime: 30_000,
  });

  const extraItems = extraData?.items ?? [];

  return (
    <section aria-labelledby="usage-list-heading">
      <h2
        id="usage-list-heading"
        className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-2"
      >
        사용처 ({totalCount})
      </h2>

      {initialUsages.length === 0 && (
        <div className="rounded border border-border-subtle bg-bg-elevated p-3 text-center">
          <p className="text-caption text-text-disabled">아직 사용처가 없습니다.</p>
        </div>
      )}

      <ul className="space-y-1.5" aria-label="사용처 목록">
        {initialUsages.map((usage) => (
          <UsageItem key={`${usage.styleVersionId}-${usage.nodeId}`} usage={usage} />
        ))}
        {showAll && extraItems.map((usage) => (
          <UsageItem key={`${usage.styleVersionId}-${usage.nodeId}`} usage={usage} />
        ))}
      </ul>

      {extraLoading && (
        <div className="flex justify-center py-2" role="status">
          <Loader2 className="h-4 w-4 animate-spin text-text-tertiary" aria-hidden="true" />
          <span className="sr-only">더 불러오는 중...</span>
        </div>
      )}

      {!showAll && totalCount > 20 && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className={cn(
            "mt-2 w-full rounded border border-border-subtle px-2 py-1.5",
            "text-caption text-text-secondary hover:bg-bg-hover hover:text-text-primary",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
            "transition-colors"
          )}
        >
          {totalCount - 20}개 더 보기
        </button>
      )}

      {showAll && extraItems.length > 0 && offset + 20 < totalCount && (
        <button
          type="button"
          onClick={() => setOffset((o) => o + 20)}
          disabled={extraLoading}
          className={cn(
            "mt-2 w-full rounded border border-border-subtle px-2 py-1.5",
            "text-caption text-text-secondary hover:bg-bg-hover hover:text-text-primary",
            "disabled:opacity-40 disabled:pointer-events-none",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
            "transition-colors"
          )}
        >
          더 불러오기
        </button>
      )}
    </section>
  );
}

function UsageItem({ usage }: { usage: PromptUsageResponse }) {
  return (
    <li className="rounded border border-border-subtle bg-bg-elevated p-2 space-y-1">
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0 flex-1">
          <p className="text-caption text-text-secondary truncate" aria-label="Style 이름">
            {usage.styleName ?? (
              <span className="text-text-disabled">Style 이름 없음</span>
            )}
          </p>
          <p className="text-xs font-mono text-text-tertiary truncate" aria-label="Style 버전 ID">
            {usage.styleVersionId.slice(-12)}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {usage.pinned && (
            <span
              className="text-warning"
              title="버전 고정됨"
              aria-label="버전 고정됨"
            >
              <Pin className="h-3 w-3" aria-hidden="true" />
            </span>
          )}
          <ScoreChip score={usage.lastRunScore} />
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-disabled" aria-label={`노드 ID: ${usage.nodeId}`}>
          노드: {usage.nodeId}
        </span>
        <Link
          to={`/styles/${usage.styleVersionId.split("_")[0]}`}
          className={cn(
            "inline-flex items-center gap-0.5 text-xs text-accent-300",
            "hover:text-accent-200 transition-colors",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded"
          )}
          aria-label="Style Builder로 이동"
        >
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
          열기
        </Link>
      </div>
    </li>
  );
}
