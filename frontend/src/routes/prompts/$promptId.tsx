import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  Save,
  GitBranch,
  Ban,
  Loader2,
  TrendingUp,
  Wand2,
} from "lucide-react";
import { usePrompt } from "@/hooks/usePrompt";
import { usePromptVersions } from "@/hooks/usePromptVersions";
import { useCreatePromptVersion } from "@/hooks/useCreatePromptVersion";
import { promptsApi } from "@/api/prompts";
import { PreconditionFailedError } from "@/types/prompts";
import { PromptBodyEditor } from "@/features/prompts/PromptBodyEditor";
import { DeclaredVariablesEditor } from "@/features/prompts/DeclaredVariablesEditor";
import { StatusBadge } from "@/features/prompts/StatusBadge";
import { NodeTypeBadge } from "@/features/prompts/NodeTypeBadge";
import { UsageList } from "@/features/prompts/UsageList";
import { AbTriggerDialog } from "@/features/prompts/AbTriggerDialog";
import { OptimizeDialog } from "@/features/prompts/OptimizeDialog";
import { OptimizationHistoryPanel } from "@/features/prompts/OptimizationHistoryPanel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { DeclaredVariable, PromptStatus } from "@/types/prompts";

const STATUS_TRANSITIONS: Record<PromptStatus, PromptStatus[]> = {
  draft: ["reviewing"],
  reviewing: ["approved", "draft"],
  approved: ["deprecated"],
  deprecated: [],
};

const STATUS_TRANSITION_LABELS: Record<PromptStatus, string> = {
  draft: "Draft",
  reviewing: "Reviewing",
  approved: "Approved",
  deprecated: "Deprecated",
};

export default function PromptDetailPage() {
  const { promptId } = useParams<{ promptId: string }>();
  const queryClient = useQueryClient();

  const { data: prompt, isLoading, isError, etagRef } = usePrompt(promptId);

  const [body, setBody] = useState("");
  const [declaredVariables, setDeclaredVariables] = useState<DeclaredVariable[]>([]);
  const [changeNote, setChangeNote] = useState("");
  const [serverWarnings, setServerWarnings] = useState<string[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [abDialogOpen, setAbDialogOpen] = useState(false);
  const [optimizeDialogOpen, setOptimizeDialogOpen] = useState(false);

  // F05 단계 5: 버전 목록 — GET /api/prompts/{id}/versions 실제 호출
  const versionsQuery = usePromptVersions(promptId);
  const allVersions = versionsQuery.data?.items ?? [];

  // Init from server data
  useEffect(() => {
    if (prompt?.currentVersion) {
      setBody(prompt.currentVersion.body);
      setDeclaredVariables(prompt.currentVersion.declaredVariables);
      setIsDirty(false);
    }
  }, [prompt?.id, prompt?.currentVersion?.id]);

  const handleBodyChange = useCallback((newBody: string) => {
    setBody(newBody);
    setIsDirty(true);
  }, []);

  const handleVarsChange = useCallback((vars: DeclaredVariable[]) => {
    setDeclaredVariables(vars);
    setIsDirty(true);
  }, []);

  // New version mutation
  const { mutate: createVersion, isPending: isCreatingVersion } = useCreatePromptVersion({
    promptId: promptId!,
    etagRef,
    onSuccess: () => {
      setServerWarnings([]);
      setChangeNote("");
      setIsDirty(false);
    },
  });

  // Update meta mutation (status change)
  const { mutate: updateMeta, isPending: isUpdatingMeta } = useMutation({
    mutationFn: ({ status }: { status: PromptStatus }) =>
      promptsApi.updateMeta(promptId!, { status }, etagRef.current),
    onSuccess: () => {
      toast.success("상태가 변경되었습니다.");
      queryClient.invalidateQueries({ queryKey: ["prompts", promptId] });
    },
    onError: (e) => {
      if (e instanceof PreconditionFailedError) {
        toast.error(e.message);
      } else {
        toast.error("상태 변경에 실패했습니다.");
      }
    },
  });

  // Promote version mutation
  const { mutate: promoteVersion, isPending: isPromoting } = useMutation({
    mutationFn: () =>
      promptsApi.promoteVersion(promptId!, prompt!.currentVersion!.version),
    onSuccess: () => {
      toast.success("버전이 승격되었습니다.");
      queryClient.invalidateQueries({ queryKey: ["prompts", promptId] });
    },
    onError: () => {
      toast.error("승격에 실패했습니다.");
    },
  });

  // Cmd+S → new version
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const isMeta = e.metaKey || e.ctrlKey;
      if (isMeta && e.shiftKey && e.key === "s") {
        e.preventDefault();
        if (isDirty && !isCreatingVersion) {
          createVersion({ body, declaredVariables, changeNote: changeNote || null });
        }
        return;
      }
      if (isMeta && !e.shiftKey && e.key === "s") {
        e.preventDefault();
        if (isDirty && !isCreatingVersion) {
          createVersion({ body, declaredVariables, changeNote: changeNote || null });
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDirty, isCreatingVersion, body, declaredVariables, changeNote, createVersion]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full" role="status" aria-label="로딩 중">
        <Loader2 className="h-8 w-8 animate-spin text-text-tertiary" aria-hidden="true" />
        <span className="sr-only">로딩 중...</span>
      </div>
    );
  }

  if (isError || !prompt) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <p className="text-error text-body font-medium">Prompt를 불러오지 못했습니다.</p>
        <Link
          to="/prompts"
          className={cn(
            "text-accent-300 text-caption hover:text-accent-200",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded"
          )}
        >
          Library로 돌아가기
        </Link>
      </div>
    );
  }

  const allowedTransitions = STATUS_TRANSITIONS[prompt.status];
  const isMutating = isCreatingVersion || isUpdatingMeta || isPromoting;

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <header className="h-12 border-b border-border-subtle bg-bg-surface flex items-center px-4 gap-3 shrink-0">
        <Link
          to="/prompts"
          className={cn(
            "flex items-center gap-1.5 text-caption text-text-tertiary hover:text-text-primary",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded px-1",
            "transition-colors"
          )}
          aria-label="Library로 돌아가기"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Library
        </Link>

        <span className="text-border-subtle" aria-hidden="true">/</span>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <h1 className="text-body font-medium text-text-primary truncate">{prompt.name}</h1>
          <NodeTypeBadge nodeType={prompt.nodeType} />
          <StatusBadge status={prompt.status} />
        </div>

        {/* Dirty indicator */}
        {isDirty && (
          <span
            className="flex items-center gap-1 text-caption text-warning shrink-0"
            aria-live="polite"
            aria-label="저장되지 않은 변경 있음"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true" />
            저장 안됨
          </span>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => createVersion({ body, declaredVariables, changeNote: changeNote || null })}
            disabled={!isDirty || isMutating}
            aria-label="새 버전으로 저장 (Cmd+Shift+S)"
            className="text-text-secondary hover:text-text-primary"
          >
            {isCreatingVersion ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" aria-hidden="true" />
            ) : (
              <Save className="h-4 w-4 mr-1" aria-hidden="true" />
            )}
            새 버전 저장
          </Button>

          {/* A/B 비교 트리거 */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAbDialogOpen(true)}
            disabled={isMutating || allVersions.length < 2}
            title={
              allVersions.length < 2
                ? "버전이 2개 이상이어야 A/B 비교를 시작할 수 있습니다."
                : "A/B 비교 시작"
            }
            aria-label="A/B 비교 시작"
            className={cn(
              "border-border-default text-text-secondary hover:text-text-primary",
              "disabled:opacity-40 disabled:cursor-not-allowed"
            )}
          >
            <GitBranch className="h-4 w-4 mr-1" aria-hidden="true" />
            A/B
          </Button>

          {/* F02 Optimize 트리거 */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOptimizeDialogOpen(true)}
            disabled={isMutating}
            aria-label="F02 Prompt Optimize 실행"
            className={cn(
              "border-accent-500/40 text-accent-300 hover:bg-accent-500/10 hover:text-accent-200",
              "disabled:opacity-40 disabled:cursor-not-allowed"
            )}
          >
            <Wand2 className="h-4 w-4 mr-1" aria-hidden="true" />
            Optimize
          </Button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: body editor */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Version info */}
          {prompt.currentVersion && (
            <div className="flex items-center gap-2 text-caption text-text-tertiary">
              <span>
                현재 버전: <span className="font-medium text-text-secondary">v{prompt.currentVersion.version}</span>
              </span>
              {prompt.currentVersion.changeNote && (
                <span className="truncate text-text-disabled">— {prompt.currentVersion.changeNote}</span>
              )}
            </div>
          )}

          {/* Body editor */}
          <section aria-labelledby="body-editor-heading">
            <h2 id="body-editor-heading" className="text-caption font-medium text-text-secondary uppercase tracking-wider mb-2">
              프롬프트 본문
            </h2>
            <PromptBodyEditor
              body={body}
              onChange={handleBodyChange}
              declaredVariables={declaredVariables}
              warnings={serverWarnings}
            />
          </section>

          {/* Declared variables */}
          <section>
            <DeclaredVariablesEditor
              variables={declaredVariables}
              onChange={handleVarsChange}
            />
          </section>

          {/* Change note */}
          {isDirty && (
            <section>
              <label
                htmlFor="change-note"
                className="block text-caption font-medium text-text-secondary mb-1"
              >
                변경 메모 (선택)
              </label>
              <input
                id="change-note"
                type="text"
                value={changeNote}
                onChange={(e) => setChangeNote(e.target.value)}
                placeholder="변경 이유를 간략히 설명..."
                className={cn(
                  "w-full rounded border border-border-default bg-bg-canvas",
                  "px-2 py-1.5 text-body text-text-primary placeholder:text-text-disabled",
                  "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                )}
              />
            </section>
          )}

          {/* Save hint */}
          <p className="text-caption text-text-disabled">
            Cmd+S 또는 Cmd+Shift+S로 새 버전 저장
          </p>
        </main>

        {/* Right: sidebar */}
        <aside
          className="w-72 shrink-0 border-l border-border-subtle bg-bg-surface overflow-y-auto p-4 space-y-6"
          aria-label="Prompt 사이드 패널"
        >
          {/* Lifecycle */}
          <section aria-labelledby="lifecycle-heading">
            <h2
              id="lifecycle-heading"
              className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-3"
            >
              Lifecycle
            </h2>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-caption text-text-secondary">현재 상태</span>
                <StatusBadge status={prompt.status} />
              </div>

              {/* Status transition buttons */}
              {allowedTransitions.length > 0 && (
                <div className="space-y-1.5">
                  {allowedTransitions.map((nextStatus) => (
                    <button
                      key={nextStatus}
                      type="button"
                      onClick={() => updateMeta({ status: nextStatus })}
                      disabled={isMutating}
                      className={cn(
                        "w-full rounded border px-3 py-1.5 text-caption text-left",
                        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                        "transition-colors disabled:opacity-40 disabled:pointer-events-none",
                        nextStatus === "approved"
                          ? "border-success/30 bg-success/10 text-success hover:bg-success/20"
                          : nextStatus === "deprecated"
                          ? "border-error/30 bg-error/10 text-error hover:bg-error/20"
                          : "border-border-default bg-bg-elevated text-text-secondary hover:bg-bg-hover"
                      )}
                      aria-label={`${STATUS_TRANSITION_LABELS[nextStatus]}로 상태 변경`}
                    >
                      {nextStatus === "deprecated" && (
                        <Ban className="inline-block h-3 w-3 mr-1" aria-hidden="true" />
                      )}
                      {nextStatus === "approved" && (
                        <TrendingUp className="inline-block h-3 w-3 mr-1" aria-hidden="true" />
                      )}
                      → {STATUS_TRANSITION_LABELS[nextStatus]}
                    </button>
                  ))}
                </div>
              )}

              {/* Promote button — approved only */}
              {prompt.status === "approved" && prompt.currentVersion && (
                <button
                  type="button"
                  onClick={() => promoteVersion()}
                  disabled={isMutating}
                  className={cn(
                    "w-full rounded border border-accent-500/30 bg-accent-500/10 px-3 py-1.5",
                    "text-caption text-accent-300 hover:bg-accent-500/20",
                    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                    "transition-colors disabled:opacity-40 disabled:pointer-events-none"
                  )}
                  aria-label={`v${prompt.currentVersion.version}을 current로 승격`}
                >
                  <TrendingUp className="inline-block h-3 w-3 mr-1" aria-hidden="true" />
                  Promote v{prompt.currentVersion.version} → current
                </button>
              )}
            </div>
          </section>

          {/* Prompt meta */}
          <section aria-labelledby="meta-heading">
            <h2
              id="meta-heading"
              className="text-caption font-medium text-text-tertiary uppercase tracking-wider mb-2"
            >
              메타 정보
            </h2>
            <div className="space-y-1.5">
              {prompt.owner && (
                <div className="flex justify-between items-center">
                  <span className="text-caption text-text-tertiary">작성자</span>
                  <span className="text-caption text-text-secondary">{prompt.owner}</span>
                </div>
              )}
              <div className="flex justify-between items-center">
                <span className="text-caption text-text-tertiary">생성일</span>
                <span className="text-caption text-text-secondary">
                  {new Date(prompt.createdAt).toLocaleDateString("ko-KR")}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-caption text-text-tertiary">수정일</span>
                <span className="text-caption text-text-secondary">
                  {new Date(prompt.updatedAt).toLocaleDateString("ko-KR")}
                </span>
              </div>
              {prompt.tags.length > 0 && (
                <div>
                  <span className="text-caption text-text-tertiary block mb-1">태그</span>
                  <div className="flex flex-wrap gap-1">
                    {prompt.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs rounded px-1.5 py-0.5 bg-bg-elevated text-text-tertiary border border-border-subtle"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Usage list */}
          <UsageList
            promptId={promptId!}
            initialUsages={prompt.usages}
            totalCount={prompt.usageCountTotal}
          />

          {/* F02 optimization history */}
          <OptimizationHistoryPanel promptId={promptId!} />
        </aside>
      </div>

      {/* A/B 트리거 다이얼로그 */}
      <AbTriggerDialog
        open={abDialogOpen}
        onOpenChange={setAbDialogOpen}
        promptId={promptId!}
        versions={allVersions}
        currentVersionId={prompt.currentVersion?.id ?? null}
        usages={prompt.usages}
      />

      {/* F02 Optimize 다이얼로그 */}
      <OptimizeDialog
        open={optimizeDialogOpen}
        onOpenChange={setOptimizeDialogOpen}
        promptId={promptId!}
        versions={allVersions}
        currentVersionId={prompt.currentVersion?.id ?? null}
      />
    </div>
  );
}
