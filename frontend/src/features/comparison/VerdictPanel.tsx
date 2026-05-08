import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { CheckCircle, XCircle, RefreshCw, Loader2 } from "lucide-react";
import { stylesApi } from "@/api/styles";
import { runsApi } from "@/api/runs";
import { useRunStore } from "@/stores/runStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface VerdictPanelProps {
  styleId: string;
  styleVersionId: string;
  runId: string;
  status: "pending" | "succeeded" | "failed";
}

export function VerdictPanel({
  styleId,
  styleVersionId,
  runId,
  status,
}: VerdictPanelProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addRunId } = useRunStore();

  const isPending = status === "pending";
  const isSucceeded = status === "succeeded";

  const { mutate: updateStatus, isPending: isUpdating } = useMutation({
    mutationFn: ({
      status: nextStatus,
    }: {
      status: "approved" | "rejected";
    }) => stylesApi.updateStatus(styleId, nextStatus),
    onSuccess: (_, { status: nextStatus }) => {
      queryClient.invalidateQueries({ queryKey: ["styles"] });
      toast.success(
        nextStatus === "approved"
          ? "Style이 채택되었습니다."
          : "Style이 기각되었습니다."
      );
      navigate("/styles");
    },
    onError: () => {
      toast.error("상태 업데이트에 실패했습니다.");
    },
  });

  const { mutate: rerun, isPending: isRerunning } = useMutation({
    mutationFn: () => runsApi.create(styleVersionId),
    onSuccess: (run) => {
      addRunId(run.id);
      toast.success("재실행이 시작되었습니다.");
      navigate(`/runs/${run.id}`);
    },
    onError: () => {
      toast.error("재실행에 실패했습니다.");
    },
  });

  return (
    <div
      className={cn(
        "h-14 shrink-0 border-t border-border-subtle bg-bg-surface",
        "flex items-center justify-between px-4 gap-4"
      )}
      aria-label="판정 패널"
    >
      <div className="flex items-center gap-2">
        {isPending && (
          <>
            <Loader2
              className="h-4 w-4 animate-spin text-text-tertiary"
              aria-hidden="true"
            />
            <span className="text-sm text-text-secondary">실행 중...</span>
          </>
        )}
        {status === "succeeded" && (
          <span className="text-sm text-success">실행 완료</span>
        )}
        {status === "failed" && (
          <span className="text-sm text-error">실행 실패</span>
        )}
        <span className="text-xs text-text-tertiary">Run #{runId.slice(-8)}</span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => rerun()}
          disabled={isPending || isRerunning || isUpdating}
          aria-label="재실행"
          className="text-text-secondary hover:text-text-primary"
        >
          {isRerunning ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1" aria-hidden="true" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-1" aria-hidden="true" />
          )}
          재실행
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            updateStatus({ status: "rejected" })
          }
          disabled={!isSucceeded || isUpdating || isRerunning}
          aria-label="Style 기각"
          className="border-error/40 text-error hover:bg-error/10 hover:border-error/60 disabled:opacity-40"
        >
          <XCircle className="h-4 w-4 mr-1" aria-hidden="true" />
          기각
        </Button>

        <Button
          size="sm"
          onClick={() => updateStatus({ status: "approved" })}
          disabled={!isSucceeded || isUpdating || isRerunning}
          aria-label="Style 채택"
          className={cn(
            "bg-success/20 text-success hover:bg-success/30 border border-success/40",
            "disabled:opacity-40"
          )}
        >
          {isUpdating ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1" aria-hidden="true" />
          ) : (
            <CheckCircle className="h-4 w-4 mr-1" aria-hidden="true" />
          )}
          채택
        </Button>
      </div>
    </div>
  );
}
