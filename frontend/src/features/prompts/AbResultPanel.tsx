/**
 * F05 단계 5 — A/B 실행 결과 패널.
 *
 * run_id 두 개를 받아 각 Run의 node_executions를 표시하고
 * 평가 점수 diff (있을 경우)를 테이블로 보여준다.
 *
 * "v2 promote" / "v1 유지" 버튼 포함.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Loader2, TrendingUp, RotateCcw, CheckCircle2, AlertTriangle } from "lucide-react";
import { runsApi } from "@/api/runs";
import { promptsApi } from "@/api/prompts";
import { StageCell } from "@/features/comparison/StageCell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ─── Props ───────────────────────────────────────────────────────────────────

interface AbResultPanelProps {
  promptId: string;
  fromRunId: string;
  toRunId: string;
  fromLabel: string;
  toLabel: string;
  toVersionId: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function AbResultPanel({
  promptId,
  fromRunId,
  toRunId,
  fromLabel,
  toLabel,
  toVersionId,
}: AbResultPanelProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: fromRun, isLoading: fromLoading } = useQuery({
    queryKey: ["runs", fromRunId],
    queryFn: () => runsApi.getById(fromRunId),
    staleTime: 60_000,
  });

  const { data: toRun, isLoading: toLoading } = useQuery({
    queryKey: ["runs", toRunId],
    queryFn: () => runsApi.getById(toRunId),
    staleTime: 60_000,
  });

  const isLoading = fromLoading || toLoading;

  // Promote to version
  const { mutate: promote, isPending: isPromoting } = useMutation({
    mutationFn: () => promptsApi.promoteVersionById(promptId, toVersionId),
    onSuccess: () => {
      toast.success(`${toLabel}이 current 버전으로 승격되었습니다.`);
      queryClient.invalidateQueries({ queryKey: ["prompts", promptId] });
      navigate(`/prompts/${promptId}`);
    },
    onError: () => {
      toast.error("승격에 실패했습니다.");
    },
  });

  const fromNodeExecs = fromRun?.nodeExecutions ?? [];
  const toNodeExecs = toRun?.nodeExecutions ?? [];

  // Compute per-node cost diff for display
  const allNodeIds = Array.from(
    new Set([...fromNodeExecs.map((e) => e.nodeId), ...toNodeExecs.map((e) => e.nodeId)])
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-h3 font-semibold text-text-primary">실행 결과 비교</h2>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/prompts/${promptId}`)}
            disabled={isPromoting}
            aria-label="v1 유지 — 이전 페이지로 돌아가기"
            className="text-text-secondary hover:text-text-primary"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            {fromLabel} 유지
          </Button>
          <Button
            size="sm"
            onClick={() => promote()}
            disabled={isLoading || isPromoting}
            aria-label={`${toLabel}을 current로 승격`}
            className={cn(
              "bg-success/20 text-success hover:bg-success/30 border border-success/40",
              "disabled:opacity-40"
            )}
          >
            {isPromoting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {toLabel} Promote
          </Button>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-8 gap-2" role="status">
          <Loader2 className="h-5 w-5 animate-spin text-text-tertiary" aria-hidden="true" />
          <span className="text-body text-text-secondary">결과 불러오는 중...</span>
        </div>
      )}

      {/* Run status summary */}
      {!isLoading && (
        <div className="grid grid-cols-2 gap-3">
          <RunSummaryCard label={fromLabel} run={fromRun} />
          <RunSummaryCard label={toLabel} run={toRun} />
        </div>
      )}

      {/* Node executions side-by-side */}
      {!isLoading && allNodeIds.length > 0 && (
        <div>
          <h3 className="text-caption font-medium text-text-secondary uppercase tracking-wider mb-2">
            노드별 결과
          </h3>
          <div className="space-y-3">
            {allNodeIds.map((nodeId) => {
              const fromExec = fromNodeExecs.find((e) => e.nodeId === nodeId);
              const toExec = toNodeExecs.find((e) => e.nodeId === nodeId);
              return (
                <div key={nodeId} className="rounded border border-border-subtle bg-bg-surface overflow-hidden">
                  <div className="px-3 py-1.5 border-b border-border-subtle bg-bg-elevated flex items-center gap-2">
                    <span className="text-caption font-mono text-text-tertiary">{nodeId}</span>
                    <span className="text-caption text-text-disabled">
                      {fromExec?.nodeType ?? toExec?.nodeType ?? ""}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 divide-x divide-border-subtle">
                    <div>
                      <div className="px-2 py-1 text-caption text-text-tertiary border-b border-border-subtle">
                        {fromLabel}
                      </div>
                      <StageCell execution={fromExec} />
                    </div>
                    <div>
                      <div className="px-2 py-1 text-caption text-text-tertiary border-b border-border-subtle">
                        {toLabel}
                      </div>
                      <StageCell execution={toExec} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cost comparison */}
      {!isLoading && (fromRun || toRun) && (
        <div className="rounded border border-border-subtle bg-bg-elevated p-3">
          <h3 className="text-caption font-medium text-text-secondary uppercase tracking-wider mb-2">
            비용 비교
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center justify-between">
              <span className="text-caption text-text-tertiary">{fromLabel}</span>
              <span className="text-caption font-mono text-text-secondary">
                {fromRun?.totalCost != null ? `$${fromRun.totalCost.toFixed(4)}` : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-caption text-text-tertiary">{toLabel}</span>
              <span className="text-caption font-mono text-text-secondary">
                {toRun?.totalCost != null ? `$${toRun.totalCost.toFixed(4)}` : "—"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub-component: Run summary card ────────────────────────────────────────

import type { Run } from "@/types";

function RunSummaryCard({ label, run }: { label: string; run: Run | undefined }) {
  if (!run) return null;

  const isSucceeded = run.status === "succeeded";
  const isFailed = run.status === "failed";

  return (
    <div className="rounded border border-border-subtle bg-bg-elevated p-3 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-caption font-medium text-text-secondary">{label}</span>
        <span
          className={cn(
            "inline-flex items-center gap-1 text-caption font-medium",
            isSucceeded && "text-success",
            isFailed && "text-error",
            !isSucceeded && !isFailed && "text-text-tertiary"
          )}
          aria-label={`${label} Run 상태: ${run.status}`}
        >
          {isSucceeded && <CheckCircle2 className="h-3 w-3" aria-hidden="true" />}
          {isFailed && <AlertTriangle className="h-3 w-3" aria-hidden="true" />}
          {isSucceeded ? "완료" : isFailed ? "실패" : run.status}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-caption text-text-disabled">Run ID</span>
        <span className="text-caption font-mono text-text-tertiary">#{run.id.slice(-8)}</span>
      </div>
      {run.totalCost != null && (
        <div className="flex items-center justify-between">
          <span className="text-caption text-text-disabled">비용</span>
          <span className="text-caption font-mono text-text-secondary">
            ${run.totalCost.toFixed(4)}
          </span>
        </div>
      )}
    </div>
  );
}
