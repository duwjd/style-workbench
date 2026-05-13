import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { promptsApi } from "@/api/prompts";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Form, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { PromptNodeType, DeclaredVariable } from "@/types/prompts";

const createPromptSchema = z.object({
  name: z.string().min(1, "이름을 입력해주세요").max(200),
  nodeType: z.enum(["text", "image", "video", "composition"] as const),
  body: z.string().min(1, "프롬프트 본문을 입력해주세요"),
  tags: z.string().optional(),
});

type CreatePromptFormValues = z.infer<typeof createPromptSchema>;

interface CreatePromptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (promptId: string) => void;
}

export function CreatePromptDialog({
  open,
  onOpenChange,
  onCreated,
}: CreatePromptDialogProps) {
  const queryClient = useQueryClient();
  const [declaredVars, setDeclaredVars] = useState<DeclaredVariable[]>([]);
  const [varName, setVarName] = useState("");
  const [varRole, setVarRole] = useState("");

  const form = useForm<CreatePromptFormValues>({
    resolver: zodResolver(createPromptSchema),
    defaultValues: {
      name: "",
      nodeType: "text",
      body: "",
      tags: "",
    },
  });

  const { mutate: createPrompt, isPending } = useMutation({
    mutationFn: (values: CreatePromptFormValues) =>
      promptsApi.create({
        name: values.name,
        nodeType: values.nodeType as PromptNodeType,
        body: values.body,
        tags: values.tags ? values.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
        declaredVariables: declaredVars,
      }),
    onSuccess: (result) => {
      toast.success("Prompt가 생성되었습니다.");
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      form.reset();
      setDeclaredVars([]);
      onOpenChange(false);
      onCreated?.(result.data.id);
    },
    onError: () => {
      toast.error("Prompt 생성에 실패했습니다.");
    },
  });

  function addVariable() {
    if (!varName.trim()) return;
    const already = declaredVars.find((v) => v.name === varName.trim());
    if (already) {
      toast.warning("이미 추가된 변수명입니다.");
      return;
    }
    setDeclaredVars([
      ...declaredVars,
      { name: varName.trim(), role: varRole.trim(), required: true },
    ]);
    setVarName("");
    setVarRole("");
  }

  function removeVariable(name: string) {
    setDeclaredVars(declaredVars.filter((v) => v.name !== name));
  }

  function onSubmit(values: CreatePromptFormValues) {
    createPrompt(values);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "max-w-lg bg-bg-surface border-border-default text-text-primary",
          "sm:max-w-lg"
        )}
      >
        <DialogHeader>
          <DialogTitle className="text-h2 text-text-primary">새 Prompt 만들기</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Name */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary">이름</FormLabel>
                  <Input
                    {...field}
                    placeholder="Business portrait — formal greeting"
                    className="bg-bg-canvas border-border-default text-text-primary placeholder:text-text-disabled"
                    aria-required="true"
                  />
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Node Type */}
            <FormField
              control={form.control}
              name="nodeType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary">Node Type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger className="bg-bg-canvas border-border-default text-text-primary">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="text">Text</SelectItem>
                      <SelectItem value="image">Image</SelectItem>
                      <SelectItem value="video">Video</SelectItem>
                      <SelectItem value="composition">Composition</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Tags */}
            <FormField
              control={form.control}
              name="tags"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary">태그 (쉼표 구분)</FormLabel>
                  <Input
                    {...field}
                    placeholder="portrait, professional, korean"
                    className="bg-bg-canvas border-border-default text-text-primary placeholder:text-text-disabled"
                  />
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Body */}
            <FormField
              control={form.control}
              name="body"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-text-secondary">프롬프트 본문</FormLabel>
                  <Textarea
                    {...field}
                    rows={5}
                    placeholder="{name}을 위한 공식 인사말을 생성해주세요..."
                    className="bg-bg-canvas border-border-default text-text-primary placeholder:text-text-disabled resize-y"
                    aria-required="true"
                  />
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Declared Variables */}
            <div className="space-y-2">
              <p className="text-caption font-medium text-text-secondary">선언 변수 (Declared Variables)</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={varName}
                  onChange={(e) => setVarName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addVariable())}
                  placeholder="변수명 (예: name)"
                  className={cn(
                    "flex-1 rounded border border-border-default bg-bg-canvas",
                    "px-2 py-1 text-body text-text-primary placeholder:text-text-disabled",
                    "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                  )}
                  aria-label="변수명 입력"
                />
                <input
                  type="text"
                  value={varRole}
                  onChange={(e) => setVarRole(e.target.value)}
                  placeholder="역할 (예: person_name)"
                  className={cn(
                    "flex-1 rounded border border-border-default bg-bg-canvas",
                    "px-2 py-1 text-body text-text-primary placeholder:text-text-disabled",
                    "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                  )}
                  aria-label="변수 역할 입력"
                />
                <button
                  type="button"
                  onClick={addVariable}
                  className={cn(
                    "rounded border border-border-default bg-bg-elevated px-2 py-1",
                    "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
                    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                    "transition-colors"
                  )}
                  aria-label="변수 추가"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              {declaredVars.length > 0 && (
                <ul className="space-y-1" aria-label="선언된 변수 목록">
                  {declaredVars.map((v) => (
                    <li
                      key={v.name}
                      className="flex items-center justify-between rounded border border-border-subtle bg-bg-elevated px-2 py-1"
                    >
                      <span className="text-xs font-mono text-accent-300">{"{"}  {v.name} {"}"}</span>
                      <span className="text-xs text-text-tertiary mx-2">{v.role || "—"}</span>
                      <button
                        type="button"
                        onClick={() => removeVariable(v.name)}
                        className={cn(
                          "rounded p-0.5 text-text-tertiary hover:text-error",
                          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                        )}
                        aria-label={`변수 ${v.name} 제거`}
                      >
                        <X className="h-3 w-3" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                취소
              </Button>
              <Button
                type="submit"
                disabled={isPending}
                className="bg-accent-500 hover:bg-accent-600 text-text-on-accent border-transparent"
              >
                {isPending ? "저장 중..." : "생성"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
