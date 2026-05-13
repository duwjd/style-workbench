/**
 * F05 단계 5 — A/B 비교 트리거 다이얼로그.
 *
 * Props:
 *   open          Dialog 열림 상태
 *   onOpenChange  Dialog 열림 상태 변경 핸들러
 *   promptId      대상 Prompt ID
 *   versions      prompt 버전 목록 (현재 prompt 조회 응답에서 전달)
 *   currentVersionId  현재 current_version의 id (디폴트 from)
 *   usages        prompt 사용처 목록 (style version 선택용)
 *   onSuccess     A/B 트리거 성공 시 콜백 (PromptAbResponse 전달)
 *
 * NOTE: F03 미구현으로 API 응답 시점에 두 Run 모두 완료됨 (직렬 실행).
 * 따라서 로딩 중 "직렬 실행 중" 안내를 표시한다.
 */

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Loader2, GitBranch, AlertCircle } from "lucide-react";
import { promptsApi } from "@/api/prompts";
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
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { PromptVersionResponse, PromptUsageResponse } from "@/types/prompts";

// ─── Schema ──────────────────────────────────────────────────────────────────

const abSchema = z
  .object({
    fromVersion: z.string().min(1, "From 버전을 선택하세요."),
    toVersion: z.string().min(1, "To 버전을 선택하세요."),
    styleVersionId: z.string().min(1, "Style 버전을 선택하세요."),
    userInput: z.record(z.string(), z.string()),
  })
  .refine((v) => v.fromVersion !== v.toVersion, {
    message: "From 버전과 To 버전이 같습니다. 서로 다른 버전을 선택하세요.",
    path: ["toVersion"],
  });

type AbFormValues = z.infer<typeof abSchema>;

// ─── Props ───────────────────────────────────────────────────────────────────

interface AbTriggerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  promptId: string;
  /** prompt 전체 버전 목록 — GET /api/prompts/{id}/versions 응답. 없으면 현재 버전만. */
  versions: PromptVersionResponse[];
  currentVersionId: string | null;
  usages: PromptUsageResponse[];
}

// ─── Component ───────────────────────────────────────────────────────────────

export function AbTriggerDialog({
  open,
  onOpenChange,
  promptId,
  versions,
  currentVersionId,
  usages,
}: AbTriggerDialogProps) {
  const navigate = useNavigate();

  const defaultFrom = currentVersionId ?? versions[0]?.id ?? "";
  const defaultStyle = usages[0]?.styleVersionId ?? "";

  const form = useForm<AbFormValues>({
    resolver: zodResolver(abSchema),
    defaultValues: {
      fromVersion: defaultFrom,
      toVersion: "",
      styleVersionId: defaultStyle,
      userInput: {},
    },
  });

  const fromVersionId = form.watch("fromVersion");

  // from_version 변경 시 declared_variables 조회 — user_input 필드 동적 생성
  const { data: fromVersionData } = useQuery({
    queryKey: ["prompts", promptId, "versions", fromVersionId],
    queryFn: () => promptsApi.getVersionById(promptId, fromVersionId),
    enabled: open && !!fromVersionId,
    staleTime: 60_000,
  });

  const declaredVars = fromVersionData?.declaredVariables ?? [];

  // from_version 변경 시 userInput 초기화
  useEffect(() => {
    if (!fromVersionData) return;
    const emptyInput = Object.fromEntries(
      fromVersionData.declaredVariables.map((v) => [v.name, ""])
    );
    form.setValue("userInput", emptyInput);
  }, [fromVersionData, form]);

  const { mutate: triggerAb, isPending } = useMutation({
    mutationFn: (values: AbFormValues) =>
      promptsApi.triggerAb(promptId, {
        fromVersion: values.fromVersion,
        toVersion: values.toVersion,
        styleVersionId: values.styleVersionId,
        userInput: values.userInput,
      }),
    onSuccess: (result) => {
      toast.success("A/B 비교가 완료되었습니다.");
      onOpenChange(false);
      navigate(
        `/prompts/${promptId}/compare?from=${result.fromVersionId}&to=${result.toVersionId}&ab=${result.abId}`,
        {
          state: {
            fromRunId: result.fromRunId,
            toRunId: result.toRunId,
          },
        }
      );
    },
    onError: () => {
      toast.error("A/B 비교 실행에 실패했습니다.");
    },
  });

  function onSubmit(values: AbFormValues) {
    triggerAb(values);
  }

  // 다른 버전 목록 (from 제외)
  const toVersionOptions = versions.filter((v) => v.id !== fromVersionId);

  return (
    <Dialog open={open} onOpenChange={!isPending ? onOpenChange : undefined}>
      <DialogContent
        className={cn(
          "bg-bg-surface border-border-default text-text-primary",
          "sm:max-w-lg"
        )}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-text-primary">
            <GitBranch className="h-4 w-4 text-accent-300" aria-hidden="true" />
            A/B 비교 시작
          </DialogTitle>
          <DialogDescription className="text-text-secondary">
            두 버전을 같은 입력으로 실행해 평가 점수를 비교합니다.
          </DialogDescription>
        </DialogHeader>

        {/* F03 미구현 한계 안내 */}
        <div
          className={cn(
            "flex items-start gap-2 rounded border border-warning/30 bg-warning/10 px-3 py-2"
          )}
          role="note"
          aria-label="직렬 실행 안내"
        >
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-warning mt-0.5" aria-hidden="true" />
          <p className="text-caption text-warning">
            F03(병렬 실행) 미구현으로 두 Run이 순서대로 실행됩니다. 응답까지
            수십 초~수 분이 걸릴 수 있습니다.
          </p>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* From version */}
            <FormField
              control={form.control}
              name="fromVersion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary text-caption">
                    From 버전 (기준)
                  </FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      disabled={isPending}
                      aria-label="From 버전 선택"
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

            {/* To version */}
            <FormField
              control={form.control}
              name="toVersion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary text-caption">
                    To 버전 (비교 대상)
                  </FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      disabled={isPending || toVersionOptions.length === 0}
                      aria-label="To 버전 선택"
                      className={cn(
                        "w-full rounded border border-border-default bg-bg-canvas",
                        "px-2 py-1.5 text-body text-text-primary",
                        "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                        "disabled:opacity-40 disabled:pointer-events-none"
                      )}
                    >
                      <option value="">버전 선택...</option>
                      {toVersionOptions.map((v) => (
                        <option key={v.id} value={v.id}>
                          v{v.version}
                          {v.id === currentVersionId ? " (current)" : ""}
                          {v.changeNote ? ` — ${v.changeNote}` : ""}
                        </option>
                      ))}
                    </select>
                  </FormControl>
                  {toVersionOptions.length === 0 && (
                    <p className="text-caption text-text-disabled mt-1">
                      비교할 다른 버전이 없습니다. 버전을 먼저 저장하세요.
                    </p>
                  )}
                  <FormMessage className="text-error text-caption" />
                </FormItem>
              )}
            />

            {/* Style version */}
            <FormField
              control={form.control}
              name="styleVersionId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary text-caption">
                    Style 버전 (실행 컨텍스트)
                  </FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      disabled={isPending || usages.length === 0}
                      aria-label="Style 버전 선택"
                      className={cn(
                        "w-full rounded border border-border-default bg-bg-canvas",
                        "px-2 py-1.5 text-body text-text-primary",
                        "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                        "disabled:opacity-40 disabled:pointer-events-none"
                      )}
                    >
                      <option value="">Style 선택...</option>
                      {usages.map((u) => (
                        <option key={u.styleVersionId} value={u.styleVersionId}>
                          {u.styleName ?? u.styleVersionId} — 노드: {u.nodeId}
                        </option>
                      ))}
                    </select>
                  </FormControl>
                  {usages.length === 0 && (
                    <p className="text-caption text-text-disabled mt-1">
                      이 Prompt를 사용하는 Style이 없습니다. Style Builder에서 먼저 연결하세요.
                    </p>
                  )}
                  <FormMessage className="text-error text-caption" />
                </FormItem>
              )}
            />

            {/* Dynamic user_input fields */}
            {declaredVars.length > 0 && (
              <fieldset className="space-y-3">
                <legend className="text-caption font-medium text-text-secondary">
                  입력값 ({declaredVars.length}개)
                </legend>
                {declaredVars.map((variable) => (
                  <FormField
                    key={variable.name}
                    control={form.control}
                    name={`userInput.${variable.name}`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-text-secondary text-caption">
                          {variable.name}
                          {variable.required && (
                            <span className="text-error ml-1" aria-label="필수">*</span>
                          )}
                        </FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            value={field.value ?? ""}
                            disabled={isPending}
                            placeholder={`{${variable.name}} 값 입력...`}
                            aria-label={`${variable.name} 입력값`}
                            className={cn(
                              "bg-bg-canvas border-border-default text-text-primary",
                              "placeholder:text-text-disabled",
                              "focus:ring-accent-500 focus:border-accent-500"
                            )}
                          />
                        </FormControl>
                        <FormMessage className="text-error text-caption" />
                      </FormItem>
                    )}
                  />
                ))}
              </fieldset>
            )}

            {/* Loading state */}
            {isPending && (
              <div
                className="flex items-center gap-2 rounded border border-info/30 bg-info/10 px-3 py-2"
                role="status"
                aria-live="polite"
              >
                <Loader2 className="h-4 w-4 animate-spin text-info shrink-0" aria-hidden="true" />
                <p className="text-caption text-info">
                  비교 실행 중... (직렬 실행, 시간이 걸릴 수 있습니다)
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
                disabled={isPending || versions.length < 2 || usages.length === 0}
                aria-label="A/B 비교 시작"
                className={cn(
                  "bg-accent-500 hover:bg-accent-600 text-text-on-accent",
                  "disabled:opacity-40"
                )}
              >
                {isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <GitBranch className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                비교 시작
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
