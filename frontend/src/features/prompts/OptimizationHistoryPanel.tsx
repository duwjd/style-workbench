/**
 * F02 — OptimizationHistoryPanel
 *
 * PromptDetail 우측 사이드패널에 표시하는 "최근 F02 호출 이력" 컴포넌트.
 * GET /api/prompts/{id}/optimizations?limit=5 을 조회한다.
 *
 * 각 row:
 *   - 상대 시간 (createdAt)
 *   - succeeded 배지 (성공/실패 아이콘 + 텍스트 — 색에만 의존 금지)
 *   - cost_won
 *   - change_summary (1줄 truncate)
 *
 * succeeded=true row 클릭 → /prompts/:id/compare?from=parent&to=new&optimization=po_...
 */

import { useNavigate } from "react-router";
import { Loader2, CheckCircle, XCircle, Wand2 } from "lucide-react";
import { usePromptOptimizations } from "@/hooks/usePromptOptimizations";
import { cn } from "@/lib/utils";

interface OptimizationHistoryPanelProps {
  promptId: string;
}

/** 상대 시간 포맷 (간단한 한국어) */
function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "방금";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

export function OptimizationHistoryPanel({
  promptId,
}: OptimizationHistoryPanelProps) {
  const navigate = useNavigate();
  const { data, isLoading, isError } = usePromptOptimizations(promptId, {
    limit: 5,
  });

  const items = data?.items ?? [];

  return (
    <section aria-labelledby="optimization-history-heading">
      <h2
        id="optimization-history-heading"
        className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-2"
      >
        F02 이력
      </h2>

      {isLoading && (
        <div
          className="flex items-center justify-center py-3"
          role="status"
          aria-label="이력 로딩 중"
        >
          <Loader2
            className="h-4 w-4 animate-spin text-text-tertiary"
            aria-hidden="true"
          />
          <span className="sr-only">로딩 중...</span>
        </div>
      )}

      {isError && !isLoading && (
        <p className="text-caption text-error py-2">
          이력을 불러오지 못했습니다.
        </p>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <div className="rounded border border-border-subtle bg-bg-elevated p-3 text-center">
          <Wand2
            className="h-4 w-4 text-text-disabled mx-auto mb-1"
            aria-hidden="true"
          />
          <p className="text-caption text-text-disabled">
            아직 F02 호출 이력이 없습니다.
          </p>
        </div>
      )}

      {!isLoading && !isError && items.length > 0 && (
        <ul className="space-y-1.5" aria-label="F02 호출 이력 목록">
          {items.map((item) => {
            const isClickable =
              item.succeeded &&
              item.newVersionId !== null &&
              item.parentVersionId !== null;

            return (
              <li key={item.optimizationId}>
                <div
                  role={isClickable ? "button" : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                  onClick={
                    isClickable
                      ? () =>
                          navigate(
                            `/prompts/${promptId}/compare?from=${item.parentVersionId}&to=${item.newVersionId}&optimization=${item.optimizationId}`
                          )
                      : undefined
                  }
                  onKeyDown={
                    isClickable
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            navigate(
                              `/prompts/${promptId}/compare?from=${item.parentVersionId}&to=${item.newVersionId}&optimization=${item.optimizationId}`
                            );
                          }
                        }
                      : undefined
                  }
                  aria-label={
                    isClickable
                      ? `Optimization ${item.optimizationId.slice(-8)} — compare 페이지로 이동`
                      : undefined
                  }
                  className={cn(
                    "rounded border border-border-subtle bg-bg-elevated p-2 space-y-1",
                    isClickable &&
                      "cursor-pointer hover:bg-bg-hover transition-colors",
                    isClickable &&
                      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                  )}
                >
                  {/* Row header: 시간 + 배지 */}
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs text-text-disabled">
                      {relativeTime(item.createdAt)}
                    </span>
                    {item.succeeded ? (
                      <span
                        className="inline-flex items-center gap-0.5 text-xs text-success"
                        aria-label="성공"
                      >
                        <CheckCircle
                          className="h-3 w-3"
                          aria-hidden="true"
                        />
                        성공
                      </span>
                    ) : (
                      <span
                        className="inline-flex items-center gap-0.5 text-xs text-error"
                        aria-label="실패"
                      >
                        <XCircle
                          className="h-3 w-3"
                          aria-hidden="true"
                        />
                        실패
                      </span>
                    )}
                  </div>

                  {/* change_summary */}
                  {item.changeSummary && (
                    <p
                      className="text-caption text-text-secondary truncate"
                      title={item.changeSummary}
                    >
                      {item.changeSummary}
                    </p>
                  )}

                  {/* 실패 사유 */}
                  {!item.succeeded && item.failureReason && (
                    <p
                      className="text-caption text-error/80 truncate"
                      title={item.failureReason}
                    >
                      {item.failureReason}
                    </p>
                  )}

                  {/* 비용 */}
                  <p className="text-xs text-text-disabled">
                    비용: {Number(item.costWon).toLocaleString("ko-KR")}원
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
