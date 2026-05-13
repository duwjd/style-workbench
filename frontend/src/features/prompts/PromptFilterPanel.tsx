import { cn } from "@/lib/utils";
import type { PromptNodeType, PromptStatus } from "@/types/prompts";

const NODE_TYPES: { value: PromptNodeType; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video" },
  { value: "composition", label: "Composition" },
];

const STATUSES: { value: PromptStatus; label: string }[] = [
  { value: "approved", label: "Approved" },
  { value: "reviewing", label: "Reviewing" },
  { value: "draft", label: "Draft" },
  { value: "deprecated", label: "Deprecated" },
];

interface PromptFilterPanelProps {
  selectedNodeTypes: PromptNodeType[];
  selectedStatuses: PromptStatus[];
  tagInput: string;
  selectedTags: string[];
  onNodeTypeToggle: (nodeType: PromptNodeType) => void;
  onStatusToggle: (status: PromptStatus) => void;
  onTagInputChange: (value: string) => void;
  onTagAdd: (tag: string) => void;
  onTagRemove: (tag: string) => void;
}

export function PromptFilterPanel({
  selectedNodeTypes,
  selectedStatuses,
  tagInput,
  selectedTags,
  onNodeTypeToggle,
  onStatusToggle,
  onTagInputChange,
  onTagAdd,
  onTagRemove,
}: PromptFilterPanelProps) {
  function handleTagKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && tagInput.trim()) {
      e.preventDefault();
      onTagAdd(tagInput.trim());
    }
  }

  return (
    <aside
      className="w-52 shrink-0 bg-bg-surface border-r border-border-subtle p-4 space-y-6 overflow-y-auto"
      aria-label="필터 패널"
    >
      {/* Node Type 필터 */}
      <section aria-labelledby="filter-node-type-heading">
        <h2
          id="filter-node-type-heading"
          className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-2"
        >
          Node Type
        </h2>
        <div className="space-y-1.5">
          {NODE_TYPES.map(({ value, label }) => (
            <label
              key={value}
              className={cn(
                "flex items-center gap-2 cursor-pointer rounded px-2 py-1",
                "hover:bg-bg-hover transition-colors",
                "focus-within:ring-1 focus-within:ring-accent-500"
              )}
            >
              <input
                type="checkbox"
                checked={selectedNodeTypes.includes(value)}
                onChange={() => onNodeTypeToggle(value)}
                className={cn(
                  "h-3.5 w-3.5 rounded border border-border-default bg-bg-canvas",
                  "accent-accent-500 focus:outline-none"
                )}
                aria-label={`${label} 필터`}
              />
              <span className="text-body text-text-secondary">{label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* Status 필터 */}
      <section aria-labelledby="filter-status-heading">
        <h2
          id="filter-status-heading"
          className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-2"
        >
          Status
        </h2>
        <div className="space-y-1.5">
          {STATUSES.map(({ value, label }) => (
            <label
              key={value}
              className={cn(
                "flex items-center gap-2 cursor-pointer rounded px-2 py-1",
                "hover:bg-bg-hover transition-colors",
                "focus-within:ring-1 focus-within:ring-accent-500"
              )}
            >
              <input
                type="checkbox"
                checked={selectedStatuses.includes(value)}
                onChange={() => onStatusToggle(value)}
                className={cn(
                  "h-3.5 w-3.5 rounded border border-border-default bg-bg-canvas",
                  "accent-accent-500 focus:outline-none"
                )}
                aria-label={`${label} 상태 필터`}
              />
              <span className="text-body text-text-secondary">{label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* Tags 필터 */}
      <section aria-labelledby="filter-tags-heading">
        <h2
          id="filter-tags-heading"
          className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-2"
        >
          Tags
        </h2>
        <input
          type="text"
          value={tagInput}
          onChange={(e) => onTagInputChange(e.target.value)}
          onKeyDown={handleTagKeyDown}
          placeholder="태그 입력 후 Enter"
          className={cn(
            "w-full rounded border border-border-default bg-bg-canvas",
            "px-2 py-1 text-body text-text-primary placeholder:text-text-disabled",
            "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
            "transition-colors"
          )}
          aria-label="태그 필터 입력"
        />
        {selectedTags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {selectedTags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => onTagRemove(tag)}
                className={cn(
                  "inline-flex items-center gap-1 rounded px-1.5 py-0.5",
                  "text-xs bg-accent-500/15 text-accent-300 border border-accent-500/30",
                  "hover:bg-accent-500/25 transition-colors",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                )}
                aria-label={`태그 ${tag} 제거`}
              >
                {tag}
                <span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </aside>
  );
}
