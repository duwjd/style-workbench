/**
 * F02 — OptimizeDialog
 *
 * /prompts/:id PromptDetail의 "Optimize" 버튼 클릭 시 열리는 다이얼로그.
 *
 * 두 모드:
 *   Mode A (auto)  — evaluation_id 기반 자동 추출. 현재는 skeleton — 후속 작업(F06 평가 list endpoint) 필요.
 *   Mode B (manual) — retry_guidance / failed_dimensions / parent_version_id 직접 입력.
 *
 * 응답 처리:
 *   succeeded=true  → toast 성공 + navigate to compare
 *   succeeded=false → toast 에러 + 다이얼로그 유지
 *   HTTP 4xx       → toast 에러 + 다이얼로그 유지
 */

import { useState } from "react";
import { useNavigate } from "react-router";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2, Wand2, AlertCircle, Plus, X, Info } from "lucide-react";
import { useOptimizePrompt } from "@/hooks/useOptimizePrompt";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PromptVersionResponse } from "@/types/prompts";

// ─── Constants ────────────────────────────────────────────────────────────────

/** F01 evaluator dimension 권장 목록 */
const DIMENSION_SUGGESTIONS = [
  "composition",
  "lighting",
  "subject",
  "mood",
  "style",
  "motion",
  "temporal_consistency",
] as const;

// ─── Schema ──────────────────────────────────────────────────────────────────

const modeASchema = z.object({
  mode: z.literal("auto"),
  evaluationId: z.string().min(1, "evaluation_id를 입력하세요."),
});

const modeBSchema = z.object({
  mode: z.literal("manual"),
  retryGuidance: z.string().min(1, "수정 지침을 입력하세요."),
  failedDimensions: z
    .array(z.object({ value: z.string().min(1) }))
    .min(1, "실패 차원을 1개 이상 추가하세요."),
  parentVersionId: z.string().min(1, "기준 버전을 선택하세요."),
});

const optimizeSchema = z.discriminatedUnion("mode", [modeASchema, modeBSchema]);

type OptimizeFormValues = z.infer<typeof optimizeSchema>;

// ─── Props ───────────────────────────────────────────────────────────────────

interface OptimizeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  promptId: string;
  versions: PromptVersionResponse[];
  currentVersionId: string | null;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function OptimizeDialog({
  open,
  onOpenChange,
  promptId,
  versions,
  currentVersionId,
}: OptimizeDialogProps) {
  const navigate = useNavigate();
  const [activeMode, setActiveMode] = useState<"auto" | "manual">("manual");
  const [dimensionInput, setDimensionInput] = useState("");
  const [failureReason, setFailureReason] = useState<string | null>(null);

  const defaultVersionId = currentVersionId ?? versions[0]?.id ?? "";

  const form = useForm<OptimizeFormValues>({
    resolver: zodResolver(optimizeSchema),
    defaultValues:
      activeMode === "auto"
        ? { mode: "auto", evaluationId: "" }
        : {
            mode: "manual",
            retryGuidance: "",
            failedDimensions: [],
            parentVersionId: defaultVersionId,
          },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    // @ts-expect-error — discriminated union field array type narrowing
    name: "failedDimensions",
  });

  const { mutate: optimize, isPending } = useOptimizePrompt({
    promptId,
    onSuccess: (result) => {
      if (result.succeeded && result.newVersionId) {
        toast.success("Optimize 성공 — 새 버전이 생성되었습니다.");
        onOpenChange(false);
        navigate(
          `/prompts/${promptId}/compare?from=${result.parentVersionId}&to=${result.newVersionId}&optimization=${result.optimizationId}`
        );
      } else {
        setFailureReason(result.failureReason ?? "알 수 없는 실패");
        toast.error(
          `Optimize 실패: ${result.failureReason ?? "LLM 출력이 유효하지 않습니다."}`
        );
      }
    },
    onError: (error) => {
      const message =
        error instanceof Error ? error.message : "요청 중 오류가 발생했습니다.";
      toast.error(`Optimize 요청 오류: ${message}`);
    },
  });

  function switchMode(mode: "auto" | "manual") {
    setActiveMode(mode);
    setFailureReason(null);
    if (mode === "auto") {
      form.reset({ mode: "auto", evaluationId: "" });
    } else {
      form.reset({
        mode: "manual",
        retryGuidance: "",
        failedDimensions: [],
        parentVersionId: defaultVersionId,
      });
    }
  }

  function addDimension(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    const current = form.getValues("failedDimensions" as never) as Array<{
      value: string;
    }>;
    if (current?.some((d) => d.value === trimmed)) return;
    append({ value: trimmed } as never);
    setDimensionInput("");
  }

  function onSubmit(values: OptimizeFormValues) {
    setFailureReason(null);
    if (values.mode === "auto") {
      optimize({ evaluationId: values.evaluationId });
    } else {
      // retry_guidance: JSON parse 시도, 실패 시 instruction 래핑
      let parsedGuidance: Record<string, unknown>;
      try {
        parsedGuidance = JSON.parse(values.retryGuidance) as Record<
          string,
          unknown
        >;
      } catch {
        parsedGuidance = { instruction: values.retryGuidance };
      }
      optimize({
        retryGuidance: parsedGuidance,
        failedDimensions: values.failedDimensions.map((d) => d.value),
        parentVersionId: values.parentVersionId,
      });
    }
  }

  const isManualReady =
    activeMode === "manual" &&
    (form.watch("retryGuidance" as never) as string)?.length > 0 &&
    (form.watch("failedDimensions" as never) as Array<{ value: string }>)
      ?.length >= 1 &&
    (form.watch("parentVersionId" as never) as string)?.length > 0;

  const isAutoReady =
    activeMode === "auto" &&
    (form.watch("evaluationId" as never) as string)?.length > 0;

  const canSubmit = activeMode === "manual" ? isManualReady : isAutoReady;

  return (
    <Dialog
      open={open}
      onOpenChange={!isPending ? onOpenChange : undefined}
    >
      <DialogContent
        className={cn(
          "bg-bg-surface border-border-default text-text-primary",
          "sm:max-w-lg"
        )}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-text-primary">
            <Wand2 className="h-4 w-4 text-accent-300" aria-hidden="true" />
            F02 Prompt Optimize
          </DialogTitle>
          <DialogDescription className="text-text-secondary">
            Claude Opus를 호출해 prompt body를 자동 수정합니다. (P95 ≤8초)
          </DialogDescription>
        </DialogHeader>

        {/* Mode 탭 */}
        <div
          className="flex rounded border border-border-default overflow-hidden"
          role="tablist"
          aria-label="Optimize 모드 선택"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeMode === "manual"}
            onClick={() => switchMode("manual")}
            disabled={isPending}
            className={cn(
              "flex-1 px-3 py-2 text-caption transition-colors",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
              activeMode === "manual"
                ? "bg-accent-500/10 text-accent-300 font-medium"
                : "bg-bg-canvas text-text-secondary hover:bg-bg-hover"
            )}
          >
            Mode B — 직접 입력
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeMode === "auto"}
            onClick={() => switchMode("auto")}
            disabled={isPending}
            className={cn(
              "flex-1 px-3 py-2 text-caption transition-colors border-l border-border-default",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
              activeMode === "auto"
                ? "bg-accent-500/10 text-accent-300 font-medium"
                : "bg-bg-canvas text-text-secondary hover:bg-bg-hover"
            )}
          >
            Mode A — evaluation 자동
          </button>
        </div>

        {/* Mode A — skeleton (후속 작업 placeholder) */}
        {activeMode === "auto" && (
          <div
            className={cn(
              "rounded border border-info/30 bg-info/10 p-3 space-y-2"
            )}
            role="note"
            aria-label="Mode A 안내"
          >
            <div className="flex items-start gap-2">
              <Info
                className="h-3.5 w-3.5 shrink-0 text-info mt-0.5"
                aria-hidden="true"
              />
              <p className="text-caption text-info">
                Mode A는 <strong>후속 작업(F06 evaluation list endpoint)</strong>{" "}
                이후 완성됩니다. 현재는 evaluation_id를 직접 입력하거나{" "}
                <strong>Mode B 사용을 권장</strong>합니다.
              </p>
            </div>
          </div>
        )}

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4"
            noValidate
          >
            {/* ── Mode A 필드 ── */}
            {activeMode === "auto" && (
              <FormField
                control={form.control}
                name={"evaluationId" as never}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-text-secondary text-caption">
                      evaluation_id
                    </FormLabel>
                    <FormControl>
                      <input
                        {...field}
                        value={
                          (field.value as string | undefined) ?? ""
                        }
                        disabled={isPending}
                        placeholder="eval_01J7YK..."
                        aria-label="evaluation_id 입력"
                        className={cn(
                          "w-full rounded border border-border-default bg-bg-canvas",
                          "px-2 py-1.5 text-body text-text-primary placeholder:text-text-disabled",
                          "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                          "disabled:opacity-40 disabled:pointer-events-none"
                        )}
                      />
                    </FormControl>
                    <FormMessage className="text-error text-caption" />
                  </FormItem>
                )}
              />
            )}

            {/* ── Mode B 필드 ── */}
            {activeMode === "manual" && (
              <>
                {/* parent_version_id select */}
                <FormField
                  control={form.control}
                  name={"parentVersionId" as never}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-text-secondary text-caption">
                        기준 버전
                      </FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          value={
                            (field.value as string | undefined) ?? ""
                          }
                          disabled={isPending || versions.length === 0}
                          aria-label="기준 버전 선택"
                          className={cn(
                            "w-full rounded border border-border-default bg-bg-canvas",
                            "px-2 py-1.5 text-body text-text-primary",
                            "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                            "disabled:opacity-40 disabled:pointer-events-none"
                          )}
                        >
                          <option value="">버전 선택...</option>
                          {versions.map((v) => (
                            <option key={v.id} value={v.id}>
                              v{v.version}
                              {v.id === currentVersionId ? " (current)" : ""}
                              {v.changeNote ? ` — ${v.changeNote}` : ""}
                            </option>
                          ))}
                        </select>
                      </FormControl>
                      <FormMessage className="text-error text-caption" />
                    </FormItem>
                  )}
                />

                {/* retry_guidance textarea */}
                <FormField
                  control={form.control}
                  name={"retryGuidance" as never}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-text-secondary text-caption">
                        수정 지침 (retry_guidance)
                      </FormLabel>
                      <FormControl>
                        <textarea
                          {...field}
                          value={
                            (field.value as string | undefined) ?? ""
                          }
                          disabled={isPending}
                          rows={4}
                          placeholder={
                            '{"instruction": "주광원 방향을 왼쪽으로 변경", "confidence": 0.82}\n또는 자유 텍스트 입력 가능'
                          }
                          aria-label="수정 지침 입력"
                          className={cn(
                            "w-full rounded border border-border-default bg-bg-canvas",
                            "px-2 py-1.5 text-body text-text-primary placeholder:text-text-disabled",
                            "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                            "disabled:opacity-40 disabled:pointer-events-none",
                            "resize-y font-mono text-caption"
                          )}
                        />
                      </FormControl>
                      <p className="text-xs text-text-disabled mt-1">
                        JSON 입력 시 그대로 전달, 그 외 자유 텍스트는{" "}
                        <code className="font-mono">
                          {`{"instruction": "..."}`}
                        </code>
                        으로 자동 래핑됩니다.
                      </p>
                      <FormMessage className="text-error text-caption" />
                    </FormItem>
                  )}
                />

                {/* failed_dimensions chip 입력 */}
                <div>
                  <p className="text-caption font-medium text-text-secondary mb-1.5">
                    실패 차원 (failed_dimensions)
                    <span className="text-error ml-1" aria-label="필수">
                      *
                    </span>
                  </p>

                  {/* chip 목록 */}
                  {fields.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {fields.map((field, index) => (
                        <span
                          key={field.id}
                          className={cn(
                            "inline-flex items-center gap-1 rounded border",
                            "border-border-default bg-bg-elevated px-2 py-0.5",
                            "text-caption text-text-secondary"
                          )}
                        >
                          {(field as unknown as { value: string }).value}
                          <button
                            type="button"
                            onClick={() => remove(index)}
                            disabled={isPending}
                            aria-label={`${(field as unknown as { value: string }).value} 차원 제거`}
                            className={cn(
                              "rounded text-text-tertiary hover:text-error",
                              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                              "disabled:opacity-40"
                            )}
                          >
                            <X className="h-3 w-3" aria-hidden="true" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* chip 추가 input */}
                  <div className="flex gap-1.5">
                    <input
                      value={dimensionInput}
                      onChange={(e) => setDimensionInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addDimension(dimensionInput);
                        }
                      }}
                      disabled={isPending}
                      placeholder="차원 입력 후 Enter..."
                      aria-label="실패 차원 입력"
                      list="dimension-suggestions"
                      className={cn(
                        "flex-1 rounded border border-border-default bg-bg-canvas",
                        "px-2 py-1.5 text-caption text-text-primary placeholder:text-text-disabled",
                        "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                        "disabled:opacity-40 disabled:pointer-events-none"
                      )}
                    />
                    <datalist id="dimension-suggestions">
                      {DIMENSION_SUGGESTIONS.map((d) => (
                        <option key={d} value={d} />
                      ))}
                    </datalist>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => addDimension(dimensionInput)}
                      disabled={!dimensionInput.trim() || isPending}
                      aria-label="차원 추가"
                      className="border-border-default text-text-secondary hover:text-text-primary shrink-0"
                    >
                      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                      추가
                    </Button>
                  </div>

                  {/* 권장 차원 quick-add */}
                  <div className="flex flex-wrap gap-1 mt-2">
                    {DIMENSION_SUGGESTIONS.map((d) => {
                      const already = fields.some(
                        (f) =>
                          (f as unknown as { value: string }).value === d
                      );
                      return (
                        <button
                          key={d}
                          type="button"
                          onClick={() => addDimension(d)}
                          disabled={already || isPending}
                          aria-label={`${d} 차원 빠른 추가`}
                          className={cn(
                            "rounded border px-1.5 py-0.5 text-xs transition-colors",
                            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                            already
                              ? "border-border-subtle text-text-disabled cursor-default opacity-40"
                              : "border-border-subtle text-text-tertiary hover:border-accent-500/50 hover:text-accent-300"
                          )}
                        >
                          {d}
                        </button>
                      );
                    })}
                  </div>

                  {/* 필드 배열 에러 메시지 */}
                  {form.formState.errors.failedDimensions &&
                    "message" in form.formState.errors.failedDimensions && (
                      <p className="text-error text-caption mt-1">
                        {
                          (
                            form.formState.errors
                              .failedDimensions as unknown as {
                              message: string;
                            }
                          ).message
                        }
                      </p>
                    )}
                </div>
              </>
            )}

            {/* 실패 결과 표시 (succeeded=false) */}
            {failureReason && (
              <div
                className={cn(
                  "flex items-start gap-2 rounded border border-error/30 bg-error/10 px-3 py-2"
                )}
                role="alert"
                aria-live="assertive"
              >
                <AlertCircle
                  className="h-3.5 w-3.5 shrink-0 text-error mt-0.5"
                  aria-hidden="true"
                />
                <div className="space-y-0.5">
                  <p className="text-caption font-medium text-error">
                    Optimize 실패
                  </p>
                  <p className="text-caption text-error/80">{failureReason}</p>
                  <p className="text-caption text-text-tertiary">
                    지침을 수정한 뒤 다시 시도하세요.
                  </p>
                </div>
              </div>
            )}

            {/* 실행 중 상태 */}
            {isPending && (
              <div
                className={cn(
                  "flex items-center gap-2 rounded border border-info/30 bg-info/10 px-3 py-2"
                )}
                role="status"
                aria-live="polite"
              >
                <Loader2
                  className="h-4 w-4 animate-spin text-info shrink-0"
                  aria-hidden="true"
                />
                <p className="text-caption text-info">
                  Optimizer 실행 중... (Claude Opus 호출, 최대 8초 소요)
                </p>
              </div>
            )}

            {/* Footer actions */}
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={isPending}
                onClick={() => onOpenChange(false)}
                className="text-text-secondary hover:text-text-primary"
              >
                취소
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={isPending || !canSubmit}
                aria-label="Optimize 실행"
                className={cn(
                  "bg-accent-500 hover:bg-accent-600 text-text-on-accent",
                  "disabled:opacity-40"
                )}
              >
                {isPending ? (
                  <Loader2
                    className="h-3.5 w-3.5 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Wand2 className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                Optimize 실행
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
