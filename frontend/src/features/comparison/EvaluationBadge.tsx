import { cn } from "@/lib/utils";

interface EvaluationBadgeProps {
  score: number;
  label?: string;
}

function scoreToStep(score: number): 0 | 3 | 5 | 7 | 9 {
  if (score < 0.15) return 0;
  if (score < 0.4) return 3;
  if (score < 0.6) return 5;
  if (score < 0.8) return 7;
  return 9;
}

const STEP_LABELS: Record<number, string> = {
  0: "매우 낮음",
  3: "낮음",
  5: "보통",
  7: "높음",
  9: "매우 높음",
};

export function EvaluationBadge({ score, label }: EvaluationBadgeProps) {
  const step = scoreToStep(score);
  const displayLabel = label ?? STEP_LABELS[step];
  const pct = Math.round(score * 100);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium text-bg-base",
        `bg-eval-${step}`
      )}
      aria-label={`평가 점수: ${pct}% (${displayLabel})`}
      title={`${pct}%`}
    >
      <span aria-hidden="true">{pct}%</span>
      <span className="sr-only">{displayLabel}</span>
    </span>
  );
}
