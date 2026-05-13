/**
 * F05 단계 5 — 두 버전 본문의 line-by-line diff 렌더.
 *
 * 외부 diff 라이브러리 없이 자체 line-by-line diff 구현.
 * (diff 라이브러리를 추가하면 package.json 변경 필요 → 자체 구현으로 간소화)
 *
 * 색상:
 *   추가 (to-only) → bg-success/15 border-l-2 border-success
 *   삭제 (from-only) → bg-error/15 border-l-2 border-error
 *   공통 → 기본
 */

import { cn } from "@/lib/utils";

interface DiffLine {
  kind: "common" | "added" | "removed";
  content: string;
  fromLineNo?: number;
  toLineNo?: number;
}

/** Myers diff — 간단한 LCS 기반 line diff */
function computeLineDiff(fromBody: string, toBody: string): DiffLine[] {
  const fromLines = fromBody.split("\n");
  const toLines = toBody.split("\n");

  const m = fromLines.length;
  const n = toLines.length;

  // DP table for LCS lengths
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array(n + 1).fill(0)
  );

  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (fromLines[i] === toLines[j]) {
        dp[i][j] = 1 + dp[i + 1][j + 1];
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  // Trace back LCS to build diff
  const result: DiffLine[] = [];
  let i = 0;
  let j = 0;
  let fromLine = 1;
  let toLine = 1;

  while (i < m || j < n) {
    if (i < m && j < n && fromLines[i] === toLines[j]) {
      result.push({
        kind: "common",
        content: fromLines[i],
        fromLineNo: fromLine++,
        toLineNo: toLine++,
      });
      i++;
      j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      result.push({
        kind: "added",
        content: toLines[j],
        toLineNo: toLine++,
      });
      j++;
    } else {
      result.push({
        kind: "removed",
        content: fromLines[i],
        fromLineNo: fromLine++,
      });
      i++;
    }
  }

  return result;
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface PromptDiffViewProps {
  fromBody: string;
  toBody: string;
  fromLabel: string;
  toLabel: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function PromptDiffView({
  fromBody,
  toBody,
  fromLabel,
  toLabel,
}: PromptDiffViewProps) {
  const diff = computeLineDiff(fromBody, toBody);

  const addedCount = diff.filter((l) => l.kind === "added").length;
  const removedCount = diff.filter((l) => l.kind === "removed").length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle bg-bg-elevated shrink-0">
        <div className="flex items-center gap-4">
          <span className="text-caption font-medium text-text-secondary">
            Diff: <span className="text-text-primary">{fromLabel}</span>
            <span className="text-text-tertiary mx-1.5">→</span>
            <span className="text-text-primary">{toLabel}</span>
          </span>
        </div>
        <div className="flex items-center gap-3 text-caption">
          {addedCount > 0 && (
            <span className="text-success">
              +{addedCount} 줄
            </span>
          )}
          {removedCount > 0 && (
            <span className="text-error">
              -{removedCount} 줄
            </span>
          )}
          {addedCount === 0 && removedCount === 0 && (
            <span className="text-text-disabled">변경 없음</span>
          )}
        </div>
      </div>

      {/* Diff content */}
      <div
        className="flex-1 overflow-auto font-mono text-caption"
        aria-label="Prompt 본문 diff"
        role="region"
      >
        <table className="w-full border-collapse">
          <thead className="sr-only">
            <tr>
              <th scope="col">From 줄 번호</th>
              <th scope="col">To 줄 번호</th>
              <th scope="col">변경 종류</th>
              <th scope="col">내용</th>
            </tr>
          </thead>
          <tbody>
            {diff.map((line, idx) => (
              <tr
                key={idx}
                className={cn(
                  "group",
                  line.kind === "added" && "bg-success/10",
                  line.kind === "removed" && "bg-error/10"
                )}
              >
                {/* From line number */}
                <td
                  className={cn(
                    "w-10 shrink-0 select-none px-2 py-px text-right text-text-disabled",
                    "border-r border-border-subtle"
                  )}
                  aria-label={`From 줄 ${line.fromLineNo ?? ""}`}
                >
                  {line.fromLineNo ?? ""}
                </td>

                {/* To line number */}
                <td
                  className={cn(
                    "w-10 shrink-0 select-none px-2 py-px text-right text-text-disabled",
                    "border-r border-border-subtle"
                  )}
                  aria-label={`To 줄 ${line.toLineNo ?? ""}`}
                >
                  {line.toLineNo ?? ""}
                </td>

                {/* Marker */}
                <td
                  className={cn(
                    "w-6 shrink-0 select-none text-center py-px",
                    "border-r border-border-subtle font-bold",
                    line.kind === "added" && "text-success border-l-2 border-l-success",
                    line.kind === "removed" && "text-error border-l-2 border-l-error",
                    line.kind === "common" && "text-text-disabled"
                  )}
                  aria-hidden="true"
                >
                  {line.kind === "added" ? "+" : line.kind === "removed" ? "-" : " "}
                </td>

                {/* Content */}
                <td
                  className={cn(
                    "py-px pl-3 pr-2 whitespace-pre-wrap break-all text-text-primary",
                    line.kind === "added" && "text-success",
                    line.kind === "removed" && "text-error line-through decoration-error/50"
                  )}
                >
                  {line.content || " "}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
