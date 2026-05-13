import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import type { RetryAttempt, RetryAttemptList } from "@/types";

// ─── 유틸 ────────────────────────────────────────────────────────────────────

function formatCostWon(costWon: string): string {
  const num = parseFloat(costWon);
  if (Number.isNaN(num)) return costWon;
  return `${Math.round(num).toLocaleString("ko-KR")}원`;
}

function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return "진행 중";
  const diffMs =
    new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  if (diffMs < 0) return "-";
  const seconds = Math.round(diffMs / 1000);
  if (seconds < 60) return `${seconds}초`;
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = seconds % 60;
  return remainSeconds > 0 ? `${minutes}분 ${remainSeconds}초` : `${minutes}분`;
}

/** nodeId 문자열에서 노드 타입을 추정해 색상 토큰 반환 */
function nodeColorClass(nodeId: string): string {
  const id = nodeId.toLowerCase();
  if (id.includes("text")) return "bg-node-text";
  if (id.includes("image") || id.includes("img")) return "bg-node-image";
  if (id.includes("video") || id.includes("vid")) return "bg-node-video";
  if (id.includes("comp")) return "bg-node-comp";
  return "bg-border-default";
}

// ─── 배지 ────────────────────────────────────────────────────────────────────

interface ResultBadgeProps {
  passed: boolean | null;
}

function ResultBadge({ passed }: ResultBadgeProps) {
  if (passed === true) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5",
          "text-xs font-semibold border",
          "text-success border-success/30 bg-success/10"
        )}
        aria-label="평가 결과: PASS"
      >
        {/* 색에만 의존하지 않도록 아이콘 동반 */}
        <span aria-hidden="true">✓</span>
        PASS
      </span>
    );
  }
  if (passed === false) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5",
          "text-xs font-semibold border",
          "text-warning border-warning/30 bg-warning/10"
        )}
        aria-label="평가 결과: FAIL"
      >
        <span aria-hidden="true">✗</span>
        FAIL
      </span>
    );
  }
  // passed === null → 예산 초과로 evaluator 미호출
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5",
        "text-xs font-semibold border",
        "text-error border-error/30 bg-error/10"
      )}
      aria-label="평가 결과: 예산 초과"
    >
      <span aria-hidden="true">!</span>
      예산 초과
    </span>
  );
}

// ─── 개별 Attempt 카드 ────────────────────────────────────────────────────────

interface AttemptCardProps {
  attempt: RetryAttempt;
  isLast: boolean;
}

function AttemptCard({ attempt, isLast }: AttemptCardProps) {
  const [guidanceOpen, setGuidanceOpen] = useState(false);

  const attemptLabel = `Attempt #${attempt.attemptNumber + 1}`;

  return (
    <div className="relative flex gap-3">
      {/* Timeline 세로선 */}
      {!isLast && (
        <div
          className="absolute left-3 top-7 bottom-0 w-px bg-border-subtle"
          aria-hidden="true"
        />
      )}

      {/* 타임라인 점 */}
      <div
        className={cn(
          "mt-1.5 h-6 w-6 shrink-0 rounded-full border-2 flex items-center justify-center",
          attempt.passed === true
            ? "border-success bg-success/10"
            : attempt.passed === false
              ? "border-warning bg-warning/10"
              : "border-error bg-error/10"
        )}
        aria-hidden="true"
      >
        <span
          className={cn(
            "text-xs font-bold",
            attempt.passed === true
              ? "text-success"
              : attempt.passed === false
                ? "text-warning"
                : "text-error"
          )}
        >
          {attempt.attemptNumber + 1}
        </span>
      </div>

      {/* 카드 본문 */}
      <div
        className={cn(
          "flex-1 mb-3 rounded-lg border bg-bg-elevated p-3",
          "border-border-subtle"
        )}
      >
        {/* 카드 헤더 */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span className="text-sm font-semibold text-text-primary">
            {attemptLabel}
          </span>
          <ResultBadge passed={attempt.passed} />
        </div>

        {/* 메타 정보 줄 */}
        <div className="mt-1.5 flex items-center gap-3 flex-wrap text-xs text-text-tertiary">
          {/* Prompt version 링크 또는 인라인 표시 */}
          {attempt.promptVersionIdUsed ? (
            <a
              href={`/prompts/${attempt.promptVersionIdUsed}`}
              className={cn(
                "inline-flex items-center gap-1",
                "text-info hover:underline focus-visible:ring-1 focus-visible:ring-accent-500 rounded"
              )}
              aria-label={`프롬프트 버전 ${attempt.promptVersionIdUsed} 보기`}
            >
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
              {attempt.promptVersionIdUsed.slice(-8)}
            </a>
          ) : (
            <span className="text-text-disabled">(inline prompt)</span>
          )}

          {/* 소요 시간 */}
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" aria-hidden="true" />
            {formatDuration(attempt.startedAt, attempt.finishedAt)}
          </span>

          {/* 비용 */}
          <span>{formatCostWon(attempt.costWon)}</span>
        </div>

        {/* 실패 차원 chip 리스트 */}
        {attempt.passed === false && attempt.failedDimensions.length > 0 && (
          <div
            className="mt-2 flex flex-wrap gap-1"
            aria-label="실패 평가 항목"
          >
            {attempt.failedDimensions.map((dim) => (
              <span
                key={dim}
                className={cn(
                  "inline-flex items-center rounded px-1.5 py-0.5",
                  "text-xs border border-warning/30 bg-warning/10 text-warning"
                )}
              >
                {dim}
              </span>
            ))}
          </div>
        )}

        {/* retryGuidance 토글 */}
        {attempt.retryGuidance && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setGuidanceOpen((v) => !v)}
              className={cn(
                "inline-flex items-center gap-1 text-xs text-text-secondary",
                "hover:text-text-primary transition-colors",
                "focus-visible:ring-1 focus-visible:ring-accent-500 rounded"
              )}
              aria-expanded={guidanceOpen}
              aria-controls={`guidance-${attempt.id}`}
            >
              {guidanceOpen ? (
                <ChevronDown className="h-3 w-3" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-3 w-3" aria-hidden="true" />
              )}
              재시도 가이던스
            </button>

            {guidanceOpen && (
              <div
                id={`guidance-${attempt.id}`}
                className={cn(
                  "mt-1.5 rounded border border-border-subtle bg-bg-surface",
                  "p-2 text-xs text-text-secondary"
                )}
              >
                <RetryGuidanceContent guidance={attempt.retryGuidance} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── RetryGuidance 렌더러 ────────────────────────────────────────────────────

interface RetryGuidanceContentProps {
  guidance: Record<string, unknown>;
}

function RetryGuidanceContent({ guidance }: RetryGuidanceContentProps) {
  // `instruction` 키를 최우선 표시, 나머지는 JSON pretty-print
  const { instruction, ...rest } = guidance;

  return (
    <div className="space-y-1">
      {typeof instruction === "string" && (
        <p className="text-text-primary leading-relaxed">{instruction}</p>
      )}
      {Object.keys(rest).length > 0 && (
        <pre className="overflow-x-auto text-text-tertiary whitespace-pre-wrap break-words">
          {JSON.stringify(rest, null, 2)}
        </pre>
      )}
      {typeof instruction !== "string" && Object.keys(rest).length === 0 && (
        <pre className="overflow-x-auto text-text-tertiary whitespace-pre-wrap break-words">
          {JSON.stringify(guidance, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ─── 노드별 그룹 ─────────────────────────────────────────────────────────────

interface NodeGroupProps {
  nodeId: string;
  attempts: RetryAttempt[];
}

function NodeGroup({ nodeId, attempts }: NodeGroupProps) {
  return (
    <div className="space-y-0">
      {/* 노드 헤더 */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={cn(
            "h-2 w-2 rounded-full shrink-0",
            nodeColorClass(nodeId)
          )}
          aria-hidden="true"
        />
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          {nodeId}
        </span>
        <span className="text-xs text-text-disabled ml-1">
          {attempts.length}회 시도
        </span>
      </div>

      {/* Attempt 카드들 */}
      <div className="pl-1">
        {attempts.map((attempt, idx) => (
          <AttemptCard
            key={attempt.id}
            attempt={attempt}
            isLast={idx === attempts.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

// ─── 로딩/에러/빈 상태 ───────────────────────────────────────────────────────

function TimelineSkeleton() {
  return (
    <div className="space-y-3 px-4 py-3" aria-label="로딩 중">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex gap-3">
          <Skeleton className="mt-1.5 h-6 w-6 rounded-full bg-bg-elevated" />
          <Skeleton className="flex-1 h-16 rounded-lg bg-bg-elevated" />
        </div>
      ))}
    </div>
  );
}

// ─── RetryTimeline 메인 컴포넌트 ────────────────────────────────────────────

interface RetryTimelineProps {
  data: RetryAttemptList | undefined;
  isLoading: boolean;
  isError: boolean;
}

export function RetryTimeline({
  data,
  isLoading,
  isError,
}: RetryTimelineProps) {
  // 섹션 자체는 데이터가 없거나 attempt가 0건이면 표시하지 않는다
  // (처음 실행에서 retry가 없는 경우 섹션 노출 불필요)
  if (isLoading) {
    return (
      <section
        aria-label="재시도 타임라인"
        className="border-b border-border-subtle"
      >
        <div className="px-4 pt-3 pb-1">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            재시도 타임라인
          </h2>
        </div>
        <TimelineSkeleton />
      </section>
    );
  }

  if (isError) {
    return (
      <section
        aria-label="재시도 타임라인"
        className="border-b border-border-subtle px-4 py-3"
      >
        <p className="text-xs text-error">
          재시도 이력을 불러오지 못했습니다.
        </p>
      </section>
    );
  }

  if (!data || data.totalAttempts === 0) {
    // attempt가 없으면 섹션 미표시
    return null;
  }

  // nodeId 순서 보존을 위해 첫 등장 순서 기준 그룹화
  const nodeOrder: string[] = [];
  const nodeMap = new Map<string, RetryAttempt[]>();
  for (const attempt of data.attempts) {
    if (!nodeMap.has(attempt.nodeId)) {
      nodeOrder.push(attempt.nodeId);
      nodeMap.set(attempt.nodeId, []);
    }
    nodeMap.get(attempt.nodeId)!.push(attempt);
  }

  return (
    <section
      aria-label="재시도 타임라인"
      className="border-b border-border-subtle"
    >
      <div className="px-4 pt-3 pb-1 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          재시도 타임라인
        </h2>
        <span className="text-xs text-text-disabled">
          총 {data.totalAttempts}회 시도
        </span>
      </div>

      <div className="px-4 pb-3 space-y-4">
        {nodeOrder.map((nodeId) => (
          <NodeGroup
            key={nodeId}
            nodeId={nodeId}
            attempts={nodeMap.get(nodeId)!}
          />
        ))}
      </div>
    </section>
  );
}
