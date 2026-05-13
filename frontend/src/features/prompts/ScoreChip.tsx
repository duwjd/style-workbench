import { cn } from "@/lib/utils";

interface ScoreChipProps {
  score: number | null | undefined;
  className?: string;
}

/**
 * F05 §7.5 회귀 점수 색상:
 * ≤0.5 → text-error (danger), 0.5~0.75 → text-warning, ≥0.75 → text-success
 */
export function ScoreChip({ score, className }: ScoreChipProps) {
  if (score == null) {
    return (
      <span className={cn("text-xs text-text-disabled", className)} aria-label="점수 없음">
        —
      </span>
    );
  }

  const colorClass =
    score >= 0.75 ? "text-success" : score >= 0.5 ? "text-warning" : "text-error";

  const label = score <= 0.5 ? "낮음" : score <= 0.75 ? "보통" : "높음";

  return (
    <span
      className={cn("text-xs font-mono font-medium", colorClass, className)}
      aria-label={`점수 ${(score * 100).toFixed(0)}점 (${label})`}
    >
      {(score * 100).toFixed(0)}
    </span>
  );
}
