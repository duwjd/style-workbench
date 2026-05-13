import { useState } from "react";
import { useParams } from "react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, StopCircle } from "lucide-react";
import { runsApi } from "@/api/runs";
import { useRunEvents } from "@/hooks/useRunEvents";
import { useRetryAttempts } from "@/hooks/useRetryAttempts";
import { ComparisonGrid } from "@/features/comparison/ComparisonGrid";
import { VerdictPanel } from "@/features/comparison/VerdictPanel";
import { RetryTimeline } from "@/features/runs/RetryTimeline";
import { PassBanner } from "@/features/runs/PassBanner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "aborted"]);

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const queryClient = useQueryClient();
  const [abortDialogOpen, setAbortDialogOpen] = useState(false);

  const { data: run } = useQuery({
    queryKey: ["runs", runId],
    queryFn: () => runsApi.getById(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || TERMINAL_STATUSES.has(status)) return false;
      return 2000;
    },
  });

  // SSE 구독 — 폴링(refetchInterval 2000)과 병행. SSE가 더 빠른 invalidation 트리거.
  // run이 terminal 상태거나 EventSource 연결 실패 시 폴링만 동작 (fallback).
  useRunEvents(runId, queryClient, run?.status);

  // F01: retry attempt 목록 조회
  const {
    data: retryData,
    isLoading: retryLoading,
    isError: retryError,
  } = useRetryAttempts(runId);

  const { mutate: abortRun, isPending: isAborting } = useMutation({
    mutationFn: () => runsApi.abort(runId!, "사용자 요청"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", runId] });
      toast.success("실행이 중단되었습니다.");
      setAbortDialogOpen(false);
    },
    onError: () => {
      toast.error("중단에 실패했습니다.");
    },
  });

  const isPending = run?.status === "pending";

  // F01 §7.2: 모든 노드 PASS 조건 — run.status='succeeded' AND retryData.succeeded===true
  const showPassBanner =
    run?.status === "succeeded" && retryData?.succeeded === true;

  return (
    <div className="flex flex-col h-full">
      {/* F01 §7.2: PASS 검수 안내 배너 — 조건 충족 시 최상단에 표시 */}
      {showPassBanner && run && (
        <PassBanner styleId={run.styleId} />
      )}

      {/* Abort 버튼 — pending 상태일 때만 노출 */}
      {isPending && (
        <div
          className={cn(
            "flex items-center justify-between px-4 py-2 border-b border-border-subtle",
            "bg-bg-surface shrink-0"
          )}
        >
          <div className="flex items-center gap-2">
            <Loader2
              className="h-4 w-4 animate-spin text-text-tertiary"
              aria-hidden="true"
            />
            <span className="text-sm text-text-secondary">실행 중...</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAbortDialogOpen(true)}
            disabled={isAborting}
            aria-label="실행 중단"
            className="border-error/40 text-error hover:bg-error/10 hover:border-error/60"
          >
            <StopCircle className="h-4 w-4" aria-hidden="true" />
            중단
          </Button>
        </div>
      )}

      <ComparisonGrid run={run ?? null} />

      {/* F01 §7.1: retry timeline — RunStatusPanel 아래, EvaluationPanel(VerdictPanel) 위 */}
      <RetryTimeline
        data={retryData}
        isLoading={retryLoading}
        isError={retryError}
      />

      {run && runId && run.status !== "aborted" && (
        <VerdictPanel
          styleId={run.styleId}
          styleVersionId={run.styleVersionId}
          runId={runId}
          status={run.status as "pending" | "succeeded" | "failed"}
        />
      )}

      {/* Abort 확인 Dialog */}
      <Dialog open={abortDialogOpen} onOpenChange={setAbortDialogOpen}>
        <DialogContent className="bg-bg-surface border-border-default text-text-primary">
          <DialogHeader>
            <DialogTitle>실행을 중단하시겠습니까?</DialogTitle>
            <DialogDescription className="text-text-secondary">
              진행 중인 노드 실행이 즉시 중단됩니다. 이 작업은 되돌릴 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button
                variant="outline"
                size="sm"
                className="border-border-default text-text-secondary"
                aria-label="취소"
              >
                취소
              </Button>
            </DialogClose>
            <Button
              size="sm"
              onClick={() => abortRun()}
              disabled={isAborting}
              aria-label="실행 중단 확인"
              className="bg-error/20 text-error hover:bg-error/30 border border-error/40"
            >
              {isAborting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <StopCircle className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              중단
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
