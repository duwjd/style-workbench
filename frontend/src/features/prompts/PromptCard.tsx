import { cn } from "@/lib/utils";
import { NodeTypeBadge } from "./NodeTypeBadge";
import { StatusBadge } from "./StatusBadge";
import { ScoreChip } from "./ScoreChip";
import type { PromptResponse } from "@/types/prompts";

interface PromptCardProps {
  prompt: PromptResponse;
  onClick: () => void;
}

export function PromptCard({ prompt, onClick }: PromptCardProps) {
  const avgScore =
    prompt.usages.length > 0
      ? prompt.usages.reduce((sum, u) => sum + (u.lastRunScore ?? 0), 0) /
        prompt.usages.filter((u) => u.lastRunScore != null).length
      : null;

  const validScoreCount = prompt.usages.filter((u) => u.lastRunScore != null).length;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-lg border border-border-default bg-bg-surface p-4",
        "hover:border-border-strong hover:bg-bg-hover",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
        "transition-colors"
      )}
      aria-label={`${prompt.name} 편집`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-body font-medium text-text-primary truncate leading-tight">
          {prompt.name}
        </p>
        <NodeTypeBadge nodeType={prompt.nodeType} className="shrink-0" />
      </div>

      <div className="flex items-center gap-1.5 mb-3">
        <StatusBadge status={prompt.status} />
      </div>

      {/* Tags */}
      {prompt.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3" aria-label="태그 목록">
          {prompt.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="inline-flex rounded px-1.5 py-0.5 text-xs bg-bg-elevated text-text-tertiary border border-border-subtle"
            >
              {tag}
            </span>
          ))}
          {prompt.tags.length > 4 && (
            <span className="text-xs text-text-disabled">+{prompt.tags.length - 4}</span>
          )}
        </div>
      )}

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs text-text-tertiary">
        <span aria-label={`사용처 ${prompt.usageCountTotal}건`}>
          사용 {prompt.usageCountTotal}
        </span>
        {validScoreCount > 0 && (
          <span className="flex items-center gap-1" aria-label="평균 점수">
            <span className="text-text-disabled">avg</span>
            <ScoreChip score={avgScore} />
          </span>
        )}
        {prompt.currentVersion && (
          <span className="text-text-disabled">v{prompt.currentVersion.version}</span>
        )}
      </div>
    </button>
  );
}
