import { useState, useCallback } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { usePrompts } from "@/hooks/usePrompts";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { PromptCard } from "./PromptCard";
import { PromptFilterPanel } from "./PromptFilterPanel";
import { cn } from "@/lib/utils";
import type { PromptNodeType, PromptStatus, PromptResponse } from "@/types/prompts";
import { Search, Loader2 } from "lucide-react";

interface PromptLibraryPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 선택 시 콜백 */
  onSelect: (prompt: PromptResponse) => void;
  /** 필터 초기값: 노드 타입에 맞는 것만 보이게 */
  defaultNodeType?: PromptNodeType;
}

export function PromptLibraryPickerDialog({
  open,
  onOpenChange,
  onSelect,
  defaultNodeType,
}: PromptLibraryPickerDialogProps) {
  const [searchInput, setSearchInput] = useState("");
  const [selectedNodeTypes, setSelectedNodeTypes] = useState<PromptNodeType[]>(
    defaultNodeType ? [defaultNodeType] : []
  );
  const [selectedStatuses, setSelectedStatuses] = useState<PromptStatus[]>(["approved", "draft", "reviewing"]);
  const [tagInput, setTagInput] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);

  const q = useDebounce(searchInput, 300);

  const { data, isLoading, isError } = usePrompts({
    q: q || undefined,
    nodeType: selectedNodeTypes.length > 0 ? selectedNodeTypes : undefined,
    status: selectedStatuses.length > 0 ? selectedStatuses : undefined,
    tags: selectedTags.length > 0 ? selectedTags : undefined,
    limit: 20,
    offset,
  });

  const toggleNodeType = useCallback((nodeType: PromptNodeType) => {
    setSelectedNodeTypes((prev) =>
      prev.includes(nodeType) ? prev.filter((t) => t !== nodeType) : [...prev, nodeType]
    );
    setOffset(0);
  }, []);

  const toggleStatus = useCallback((status: PromptStatus) => {
    setSelectedStatuses((prev) =>
      prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
    );
    setOffset(0);
  }, []);

  const addTag = useCallback((tag: string) => {
    setSelectedTags((prev) => prev.includes(tag) ? prev : [...prev, tag]);
    setTagInput("");
    setOffset(0);
  }, []);

  const removeTag = useCallback((tag: string) => {
    setSelectedTags((prev) => prev.filter((t) => t !== tag));
    setOffset(0);
  }, []);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const hasMore = offset + 20 < total;
  const hasPrev = offset > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "max-w-4xl w-full h-[80vh] flex flex-col gap-0 p-0",
          "bg-bg-surface border-border-default text-text-primary sm:max-w-4xl"
        )}
        showCloseButton
      >
        <DialogHeader className="px-4 pt-4 pb-3 border-b border-border-subtle shrink-0">
          <DialogTitle className="text-h2 text-text-primary">Library에서 Prompt 선택</DialogTitle>
        </DialogHeader>

        {/* Search bar */}
        <div className="px-4 py-2 border-b border-border-subtle shrink-0">
          <div className="relative">
            <Search
              className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary pointer-events-none"
              aria-hidden="true"
            />
            <Input
              value={searchInput}
              onChange={(e) => { setSearchInput(e.target.value); setOffset(0); }}
              placeholder="이름 또는 태그로 검색..."
              className="pl-8 bg-bg-canvas border-border-default text-text-primary placeholder:text-text-disabled"
              aria-label="Prompt 검색"
              autoFocus
            />
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          <PromptFilterPanel
            selectedNodeTypes={selectedNodeTypes}
            selectedStatuses={selectedStatuses}
            tagInput={tagInput}
            selectedTags={selectedTags}
            onNodeTypeToggle={toggleNodeType}
            onStatusToggle={toggleStatus}
            onTagInputChange={setTagInput}
            onTagAdd={addTag}
            onTagRemove={removeTag}
          />

          <main className="flex-1 overflow-y-auto p-4">
            {isLoading && (
              <div className="flex items-center justify-center h-32" role="status" aria-label="로딩 중">
                <Loader2 className="h-6 w-6 animate-spin text-text-tertiary" aria-hidden="true" />
                <span className="sr-only">로딩 중...</span>
              </div>
            )}

            {isError && (
              <div className="rounded-lg border border-error/30 bg-error/10 p-4 text-center" role="alert">
                <p className="text-error text-body">Prompt 목록을 불러오지 못했습니다.</p>
              </div>
            )}

            {!isLoading && !isError && items.length === 0 && (
              <div className="flex flex-col items-center justify-center h-32 gap-2 text-center">
                <p className="text-body text-text-secondary">검색 결과가 없습니다.</p>
                <p className="text-caption text-text-disabled">필터를 변경하거나 새 Prompt를 만들어보세요.</p>
              </div>
            )}

            {!isLoading && !isError && items.length > 0 && (
              <>
                <p className="text-caption text-text-tertiary mb-3">
                  {total}개 중 {offset + 1}–{Math.min(offset + items.length, total)}
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {items.map((prompt) => (
                    <PromptCard
                      key={prompt.id}
                      prompt={prompt}
                      onClick={() => {
                        onSelect(prompt);
                        onOpenChange(false);
                      }}
                    />
                  ))}
                </div>

                {/* Pagination */}
                {(hasPrev || hasMore) && (
                  <div className="flex justify-between items-center mt-4">
                    <button
                      type="button"
                      onClick={() => setOffset((o) => Math.max(0, o - 20))}
                      disabled={!hasPrev}
                      className={cn(
                        "rounded border border-border-default px-3 py-1 text-body text-text-secondary",
                        "hover:bg-bg-hover hover:text-text-primary transition-colors",
                        "disabled:opacity-40 disabled:pointer-events-none",
                        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                      )}
                    >
                      이전
                    </button>
                    <button
                      type="button"
                      onClick={() => setOffset((o) => o + 20)}
                      disabled={!hasMore}
                      className={cn(
                        "rounded border border-border-default px-3 py-1 text-body text-text-secondary",
                        "hover:bg-bg-hover hover:text-text-primary transition-colors",
                        "disabled:opacity-40 disabled:pointer-events-none",
                        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                      )}
                    >
                      다음
                    </button>
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </DialogContent>
    </Dialog>
  );
}
