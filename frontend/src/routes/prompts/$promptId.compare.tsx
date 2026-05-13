/**
 * F05 단계 5 — /prompts/:promptId/compare 라우트.
 *
 * URL query params:
 *   from=<version_id>   from 버전 ID (ULID)
 *   to=<version_id>     to 버전 ID (ULID)
 *   ab=<ab_id>          A/B comparison ID (선택, 현재 미사용 — run_id는 state에서)
 *
 * location.state (navigate에서 전달):
 *   fromRunId: string | null
 *   toRunId:   string | null
 *
 * URL 직접 접근(state 없음) 시:
 *   → fromRunId/toRunId가 없으므로 결과 비교 불가 — 안내 + "새로 비교 실행" CTA.
 */

import { Link, useParams, useSearchParams, useLocation } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitBranch, AlertCircle, Wand2 } from "lucide-react";
import { promptsApi } from "@/api/prompts";
import { usePromptOptimizations } from "@/hooks/usePromptOptimizations";
import { PromptDiffView } from "@/features/prompts/PromptDiffView";
import { AbResultPanel } from "@/features/prompts/AbResultPanel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ─── Location state type ────────────────────────────────────────────────────

interface CompareLocationState {
  fromRunId?: string | null;
  toRunId?: string | null;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PromptComparePage() {
  const { promptId } = useParams<{ promptId: string }>();
  const [searchParams] = useSearchParams();
  const location = useLocation();

  const fromVersionId = searchParams.get("from") ?? "";
  const toVersionId = searchParams.get("to") ?? "";
  const optimizationId = searchParams.get("optimization") ?? "";

  const state = (location.state ?? {}) as CompareLocationState;
  const fromRunId = state.fromRunId ?? null;
  const toRunId = state.toRunId ?? null;

  const hasRunIds = !!fromRunId && !!toRunId;

  // F02 optimization 정보 조회 (optimization query param이 있을 때)
  const { data: optimizationList } = usePromptOptimizations(
    optimizationId ? promptId : null,
    { limit: 20 }
  );

  const optimization = optimizationId
    ? optimizationList?.items.find(
        (item) => item.optimizationId === optimizationId
      ) ?? null
    : null;

  // Fetch from version
  const {
    data: fromVersion,
    isLoading: fromLoading,
    isError: fromError,
  } = useQuery({
    queryKey: ["prompts", promptId, "versions", fromVersionId],
    queryFn: () => promptsApi.getVersionById(promptId!, fromVersionId),
    enabled: !!promptId && !!fromVersionId,
    staleTime: 60_000,
  });

  // Fetch to version
  const {
    data: toVersion,
    isLoading: toLoading,
    isError: toError,
  } = useQuery({
    queryKey: ["prompts", promptId, "versions", toVersionId],
    queryFn: () => promptsApi.getVersionById(promptId!, toVersionId),
    enabled: !!promptId && !!toVersionId,
    staleTime: 60_000,
  });

  const isLoading = fromLoading || toLoading;
  const isError = fromError || toError;

  const fromLabel = fromVersion ? `v${fromVersion.version}` : fromVersionId ? `버전 ${fromVersionId.slice(-8)}` : "From";
  const toLabel = toVersion ? `v${toVersion.version}` : toVersionId ? `버전 ${toVersionId.slice(-8)}` : "To";

  // Validate required params
  if (!fromVersionId || !toVersionId) {
    return (
      <ErrorState
        promptId={promptId ?? ""}
        message="URL에 from, to 버전 파라미터가 없습니다."
      />
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <header className="h-12 border-b border-border-subtle bg-bg-surface flex items-center px-4 gap-3 shrink-0">
        <Link
          to={`/prompts/${promptId}`}
          className={cn(
            "flex items-center gap-1.5 text-caption text-text-tertiary hover:text-text-primary",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded px-1",
            "transition-colors"
          )}
          aria-label="Prompt 상세로 돌아가기"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Prompt
        </Link>

        <span className="text-border-subtle" aria-hidden="true">/</span>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <GitBranch className="h-4 w-4 text-accent-300 shrink-0" aria-hidden="true" />
          <h1 className="text-body font-medium text-text-primary truncate">
            A/B 비교: {fromLabel} → {toLabel}
          </h1>
        </div>

        {/* F02 자동 수정 결과 배지 */}
        {optimization && (
          <div
            className={cn(
              "flex items-center gap-1.5 rounded border px-2 py-1 shrink-0",
              "border-info/30 bg-info/10"
            )}
            role="note"
            aria-label="F02 자동 수정 결과"
          >
            <Wand2 className="h-3.5 w-3.5 text-info shrink-0" aria-hidden="true" />
            <span className="text-caption text-info font-medium">
              F02 자동 수정 결과
            </span>
            {optimization.changeSummary && (
              <span
                className="text-caption text-info/70 truncate max-w-48"
                title={optimization.changeSummary}
              >
                — {optimization.changeSummary}
              </span>
            )}
          </div>
        )}
      </header>

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Diff section */}
        <div className="flex-1 min-h-0 border-b border-border-subtle">
          {isLoading && (
            <div className="p-4 space-y-2">
              <Skeleton className="h-6 w-48 bg-bg-elevated" />
              <Skeleton className="h-64 w-full bg-bg-elevated" />
            </div>
          )}

          {isError && !isLoading && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-2">
                <AlertCircle className="h-8 w-8 text-error mx-auto" aria-hidden="true" />
                <p className="text-body text-error font-medium">버전 본문을 불러오지 못했습니다.</p>
                <Link
                  to={`/prompts/${promptId}`}
                  className="text-accent-300 text-caption hover:text-accent-200"
                >
                  Prompt로 돌아가기
                </Link>
              </div>
            </div>
          )}

          {!isLoading && !isError && fromVersion && toVersion && (
            <PromptDiffView
              fromBody={fromVersion.body}
              toBody={toVersion.body}
              fromLabel={fromLabel}
              toLabel={toLabel}
            />
          )}
        </div>

        {/* Result section */}
        <div className="shrink-0 overflow-y-auto p-4 max-h-96 bg-bg-canvas">
          {!hasRunIds ? (
            <NoRunIdState promptId={promptId ?? ""} />
          ) : (
            <AbResultPanel
              promptId={promptId!}
              fromRunId={fromRunId}
              toRunId={toRunId}
              fromLabel={fromLabel}
              toLabel={toLabel}
              toVersionId={toVersionId}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Error state ──────────────────────────────────────────────────────────────

function ErrorState({ promptId, message }: { promptId: string; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <AlertCircle className="h-8 w-8 text-error" aria-hidden="true" />
      <p className="text-body text-error font-medium">{message}</p>
      <Link
        to={`/prompts/${promptId}`}
        className={cn(
          "text-accent-300 text-caption hover:text-accent-200",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded"
        )}
      >
        Prompt로 돌아가기
      </Link>
    </div>
  );
}

// ─── No run-id state (URL 직접 접근 시) ─────────────────────────────────────

function NoRunIdState({ promptId }: { promptId: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded border border-border-default bg-bg-elevated p-4"
      )}
      role="note"
      aria-label="실행 결과 없음"
    >
      <AlertCircle className="h-4 w-4 text-text-tertiary shrink-0 mt-0.5" aria-hidden="true" />
      <div className="space-y-1.5">
        <p className="text-body font-medium text-text-primary">실행 결과를 표시할 수 없습니다.</p>
        <p className="text-caption text-text-secondary">
          이 URL을 직접 열거나 공유했다면 run_id 정보가 없어 결과를 확인할 수 없습니다.
          Diff는 위에서 확인할 수 있습니다.
        </p>
        <Link
          to={`/prompts/${promptId}`}
          className={cn(
            "inline-block mt-2"
          )}
        >
          <Button
            variant="outline"
            size="sm"
            className="border-border-default text-text-secondary hover:text-text-primary"
          >
            <GitBranch className="h-3.5 w-3.5" aria-hidden="true" />
            새로 비교 실행
          </Button>
        </Link>
      </div>
    </div>
  );
}
