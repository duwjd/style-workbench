import { useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { runsApi } from "@/api/runs";
import { ComparisonGrid } from "@/features/comparison/ComparisonGrid";
import { VerdictPanel } from "@/features/comparison/VerdictPanel";

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();

  const { data: run } = useQuery({
    queryKey: ["runs", runId],
    queryFn: () => runsApi.getById(runId!),
    enabled: !!runId,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ? 2000 : false,
  });

  return (
    <div className="flex flex-col h-full">
      <ComparisonGrid run={run ?? null} />
      {run && runId && (
        <VerdictPanel
          styleId={run.styleId}
          styleVersionId={run.styleVersionId}
          runId={runId}
          status={run.status}
        />
      )}
    </div>
  );
}
