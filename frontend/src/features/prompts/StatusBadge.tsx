import { cn } from "@/lib/utils";
import type { PromptStatus } from "@/types/prompts";

const STATUS_META: Record<PromptStatus, { label: string; colorClass: string }> = {
  draft: { label: "Draft", colorClass: "bg-text-tertiary/15 text-text-tertiary border-text-tertiary/30" },
  reviewing: { label: "Reviewing", colorClass: "bg-info/15 text-info border-info/30" },
  approved: { label: "Approved", colorClass: "bg-success/15 text-success border-success/30" },
  deprecated: { label: "Deprecated", colorClass: "bg-error/15 text-error border-error/30" },
};

interface StatusBadgeProps {
  status: PromptStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const meta = STATUS_META[status] ?? { label: status, colorClass: "bg-bg-elevated text-text-secondary border-border-subtle" };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        meta.colorClass,
        className
      )}
      aria-label={`상태: ${meta.label}`}
    >
      {meta.label}
    </span>
  );
}
