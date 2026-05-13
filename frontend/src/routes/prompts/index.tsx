import { useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Plus, Search, Loader2 } from "lucide-react";
import { useDebounce } from "@/hooks/useDebounce";
import { usePrompts } from "@/hooks/usePrompts";
import { PromptCard } from "@/features/prompts/PromptCard";
import { PromptFilterPanel } from "@/features/prompts/PromptFilterPanel";
import { CreatePromptDialog } from "@/features/prompts/CreatePromptDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { PromptNodeType, PromptStatus } from "@/types/prompts";

export default function PromptsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const [selectedNodeTypes, setSelectedNodeTypes] = useState<PromptNodeType[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<PromptStatus[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

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

  function handleSearchChange(value: string) {
    setSearchInput(value);
    setSearchParams(value ? { q: value } : {});
    setOffset(0);
  }

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const hasMore = offset + 20 < total;
  const hasPrev = offset > 0;

  return (
    <div className="flex h-full">
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

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="border-b border-border-subtle bg-bg-surface px-6 py-4 shrink-0">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-h1 font-semibold text-text-primary">Prompt Library</h1>
              {!isLoading && (
                <p className="text-caption text-text-tertiary mt-0.5">
                  {total}개 Prompt
                </p>
              )}
            </div>
            <Button
              onClick={() => setCreateDialogOpen(true)}
              className="bg-accent-500 hover:bg-accent-600 text-text-on-accent border-transparent shrink-0"
              aria-label="새 Prompt 만들기"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              새 Prompt
            </Button>
          </div>

          {/* Search */}
          <div className="relative mt-3">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary pointer-events-none"
              aria-hidden="true"
            />
            <Input
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="이름 또는 태그로 검색..."
              className="pl-9 bg-bg-canvas border-border-default text-text-primary placeholder:text-text-disabled"
              aria-label="Prompt 검색"
            />
          </div>
        </div>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex items-center justify-center h-48" role="status" aria-label="로딩 중">
              <Loader2 className="h-8 w-8 animate-spin text-text-tertiary" aria-hidden="true" />
              <span className="sr-only">로딩 중...</span>
            </div>
          )}

          {isError && (
            <div className="rounded-lg border border-error/30 bg-error/10 p-6 text-center" role="alert">
              <p className="text-error text-body font-medium">Prompt 목록을 불러오지 못했습니다.</p>
              <p className="text-caption text-error/70 mt-1">잠시 후 다시 시도해주세요.</p>
            </div>
          )}

          {!isLoading && !isError && items.length === 0 && (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
              <div className="rounded-full bg-bg-elevated p-4">
                <Search className="h-8 w-8 text-text-disabled" aria-hidden="true" />
              </div>
              <div>
                <p className="text-body text-text-secondary">Prompt가 없습니다.</p>
                <p className="text-caption text-text-disabled mt-1">
                  "+ 새 Prompt" 버튼으로 첫 번째 Prompt를 만들어보세요.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCreateDialogOpen(true)}
                className="border-border-default text-text-secondary hover:text-text-primary"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                새 Prompt 만들기
              </Button>
            </div>
          )}

          {!isLoading && !isError && items.length > 0 && (
            <>
              {total > 20 && (
                <p className="text-caption text-text-tertiary mb-4">
                  {total}개 중 {offset + 1}–{Math.min(offset + items.length, total)} 표시
                </p>
              )}
              <div className="grid grid-cols-3 gap-4" role="list" aria-label="Prompt 목록">
                {items.map((prompt) => (
                  <div key={prompt.id} role="listitem">
                    <PromptCard
                      prompt={prompt}
                      onClick={() => navigate(`/prompts/${prompt.id}`)}
                    />
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {(hasPrev || hasMore) && (
                <div className="flex justify-between items-center mt-6">
                  <button
                    type="button"
                    onClick={() => setOffset((o) => Math.max(0, o - 20))}
                    disabled={!hasPrev}
                    className={cn(
                      "rounded border border-border-default px-4 py-2 text-body text-text-secondary",
                      "hover:bg-bg-hover hover:text-text-primary transition-colors",
                      "disabled:opacity-40 disabled:pointer-events-none",
                      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                    )}
                  >
                    이전
                  </button>
                  <span className="text-caption text-text-tertiary">
                    {Math.floor(offset / 20) + 1} / {Math.ceil(total / 20)} 페이지
                  </span>
                  <button
                    type="button"
                    onClick={() => setOffset((o) => o + 20)}
                    disabled={!hasMore}
                    className={cn(
                      "rounded border border-border-default px-4 py-2 text-body text-text-secondary",
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

      <CreatePromptDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreated={(id) => navigate(`/prompts/${id}`)}
      />
    </div>
  );
}
