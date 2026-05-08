import { cn } from "@/lib/utils";
import type { StyleSummary } from "@/types";

interface VariantPickerProps {
  variants: StyleSummary[];
  onSelect: (id: string) => void;
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      month: "short",
      day: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function VariantPicker({ variants, onSelect }: VariantPickerProps) {
  return (
    <div className="max-w-4xl mx-auto py-10 px-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-text-primary">변주 선택</h1>
        <p className="text-text-secondary text-sm mt-1">
          마음에 드는 변주를 선택하세요. 선택 후 DAG 편집기에서 상세 설정을 조정할 수 있습니다.
        </p>
      </div>

      {variants.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <p className="text-text-tertiary text-sm">생성된 변주가 없습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {variants.map((variant, index) => (
            <button
              key={variant.id}
              onClick={() => onSelect(variant.id)}
              className={cn(
                "rounded-lg border border-border-subtle bg-bg-surface p-4 text-left",
                "hover:bg-bg-hover hover:border-accent-500 transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                "space-y-3"
              )}
              aria-label={`변주 ${index + 1}: ${variant.name}`}
            >
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-500/20 text-accent-300 text-xs font-semibold">
                  {index + 1}
                </span>
                <span className="font-medium text-text-primary text-sm leading-tight line-clamp-2">
                  {variant.name}
                </span>
              </div>

              <div className="flex flex-wrap gap-1">
                {variant.tags.slice(0, 5).map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-bg-elevated text-text-tertiary"
                  >
                    {tag}
                  </span>
                ))}
                {variant.tags.length > 5 && (
                  <span className="text-xs text-text-disabled">
                    +{variant.tags.length - 5}
                  </span>
                )}
              </div>

              <div className="text-xs text-text-tertiary">
                {formatDate(variant.createdAt)}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
