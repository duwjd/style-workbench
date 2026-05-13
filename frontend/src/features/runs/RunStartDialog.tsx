import { useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Play, ImageIcon, Type } from "lucide-react";
import type { Node } from "@xyflow/react";
import { cn } from "@/lib/utils";
import { runsApi } from "@/api/runs";
import { stylesApi } from "@/api/styles";
import type { SaveDagPayload } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
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
import type { VariableMappingMap } from "@/features/style-builder/PromptEditor";

// ───────────────────────────────────────────
// 타입 정의
// ───────────────────────────────────────────

/** DAG 전체 노드에서 user_input 변수 목록 수집 */
export interface UserInputField {
  /** {placeholder} 이름 */
  variable: string;
  /** 역할 (photo / text / 일반 string) */
  role: string;
}

export function collectUserInputFields(nodes: Node[]): UserInputField[] {
  const seen = new Set<string>();
  const fields: UserInputField[] = [];

  for (const node of nodes) {
    const mapping = (
      node.data as { variableMapping?: VariableMappingMap }
    ).variableMapping;
    if (!mapping) continue;

    for (const [variable, m] of Object.entries(mapping)) {
      if (m.source !== "user_input") continue;
      if (seen.has(variable)) continue;
      seen.add(variable);
      fields.push({ variable, role: m.role ?? "text" });
    }
  }

  return fields;
}

// ───────────────────────────────────────────
// Zod schema (동적 생성)
// ───────────────────────────────────────────

function buildSchema(fields: UserInputField[]) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const f of fields) {
    if (isPhotoRole(f.role)) {
      // 파일 필드: FileList로 받아 첫 번째 파일 검사
      shape[f.variable] = z
        .custom<FileList>((v) => v instanceof FileList && v.length > 0, {
          message: "파일을 선택해주세요.",
        })
        .optional();
    } else {
      shape[f.variable] = z
        .string()
        .min(1, `${f.variable} 값을 입력해주세요.`);
    }
  }
  return z.object(shape);
}

function isPhotoRole(role: string): boolean {
  return role === "photo" || role === "image";
}

// ───────────────────────────────────────────
// 파일 → dataURL 변환 (백엔드 multipart 미지원 시 임시)
// ───────────────────────────────────────────

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// ───────────────────────────────────────────
// 개별 입력 필드 컴포넌트
// ───────────────────────────────────────────

interface FieldInputProps {
  field: UserInputField;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  formField: any;
}

function FieldInput({ field, formField }: FieldInputProps) {
  const fileRef = useRef<HTMLInputElement | null>(null);

  if (isPhotoRole(field.role)) {
    return (
      <div className="space-y-1">
        <div
          className={cn(
            "flex items-center gap-2 rounded border-2 border-dashed",
            "border-border-default bg-bg-canvas px-3 py-4 cursor-pointer",
            "hover:border-accent-500/60 hover:bg-bg-hover transition-colors",
            "focus-within:border-accent-500 focus-within:ring-1 focus-within:ring-accent-500"
          )}
          role="button"
          tabIndex={0}
          aria-label={`${field.variable} 이미지 파일 선택`}
          onClick={() => fileRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") fileRef.current?.click();
          }}
        >
          <ImageIcon className="h-5 w-5 text-text-tertiary shrink-0" aria-hidden="true" />
          <div className="flex-1 min-w-0">
            {formField.value && formField.value.length > 0 ? (
              <p className="text-xs text-text-primary truncate">
                {(formField.value as FileList)[0].name}
              </p>
            ) : (
              <p className="text-xs text-text-disabled">
                클릭하여 이미지 선택 (jpg, png, webp)
              </p>
            )}
          </div>
        </div>
        <input
          ref={(el) => {
            fileRef.current = el;
            formField.ref(el);
          }}
          type="file"
          accept="image/*"
          className="sr-only"
          aria-hidden="true"
          onChange={(e) => formField.onChange(e.target.files)}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Type className="h-4 w-4 text-text-tertiary shrink-0" aria-hidden="true" />
      <input
        {...formField}
        type="text"
        placeholder={`${field.variable} 값을 입력하세요`}
        className={cn(
          "flex-1 rounded border border-border-default bg-bg-canvas",
          "px-2 py-1.5 text-sm text-text-primary placeholder:text-text-disabled",
          "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
          "transition-colors"
        )}
      />
    </div>
  );
}

// ───────────────────────────────────────────
// RunStartDialog
// ───────────────────────────────────────────

interface RunStartDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  styleId: string;
  nodes: Node[];
  edges: { source: string; target: string }[];
  /** 저장 후 받은 최신 versionId */
  versionId: string;
  /** DAG가 dirty 상태인지 — dirty면 저장 후 run 생성 */
  isDirty: boolean;
  buildDagPayload: () => SaveDagPayload["dag"];
  onBeforeSave?: () => void;
  onAfterSave?: (newVersionId: string) => void;
}

export function RunStartDialog({
  open,
  onOpenChange,
  styleId,
  nodes,
  versionId,
  isDirty,
  buildDagPayload,
  onAfterSave,
}: RunStartDialogProps) {
  const navigate = useNavigate();

  const fields = collectUserInputFields(nodes);
  const schema = buildSchema(fields);
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: Object.fromEntries(fields.map((f) => [f.variable, ""])) as FormValues,
  });

  const { mutate: submitRun, isPending } = useMutation({
    mutationFn: async (values: FormValues) => {
      // 1. dirty면 먼저 저장
      let activeVersionId = versionId;
      if (isDirty) {
        const saved = await stylesApi.saveDag(styleId, {
          dag: buildDagPayload(),
        });
        activeVersionId = saved.versionId;
        onAfterSave?.(saved.versionId);
      }

      // 2. user_input 빌드 — 파일은 dataURL로 변환 (백엔드 multipart endpoint 미지원 시 임시 처리)
      const userInput: Record<string, string> = {};
      for (const field of fields) {
        const raw = values[field.variable as keyof FormValues];
        if (isPhotoRole(field.role)) {
          const fileList = raw as FileList | undefined;
          if (fileList && fileList.length > 0) {
            userInput[field.variable] = await fileToDataUrl(fileList[0]);
          }
        } else {
          userInput[field.variable] = String(raw ?? "");
        }
      }

      return runsApi.create(activeVersionId, userInput);
    },
    onSuccess: (run) => {
      toast.success("실행이 시작되었습니다.");
      onOpenChange(false);
      navigate(`/runs/${run.id}`);
    },
    onError: () => {
      toast.error("실행 시작에 실패했습니다.");
    },
  });

  function onSubmit(values: FormValues) {
    submitRun(values);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "bg-bg-surface border-border-default text-text-primary",
          "max-w-md"
        )}
      >
        <DialogHeader>
          <DialogTitle className="text-text-primary">실행 시작</DialogTitle>
          <DialogDescription className="text-text-secondary">
            {fields.length > 0
              ? "실행에 필요한 입력값을 제공해주세요."
              : "입력값 없이 바로 실행합니다."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {fields.length === 0 ? (
              <div className="rounded border border-border-subtle bg-bg-elevated px-3 py-4 text-center">
                <p className="text-sm text-text-tertiary">
                  변수 매핑에 사용자 입력 변수가 없습니다.
                </p>
                <p className="text-xs text-text-disabled mt-1">
                  노드 편집기의 &ldquo;변수 매핑&rdquo; 탭에서 설정하세요.
                </p>
              </div>
            ) : (
              fields.map((field) => (
                <FormField
                  key={field.variable}
                  control={form.control}
                  name={field.variable as never}
                  render={({ field: formField }) => (
                    <FormItem>
                      <FormLabel className="text-text-secondary">
                        <span className="font-mono text-accent-300 text-xs">
                          {"{"}
                          {field.variable}
                          {"}"}
                        </span>
                        <span className="ml-2 text-xs text-text-tertiary">
                          ({field.role || "text"})
                        </span>
                      </FormLabel>
                      <FormControl>
                        <FieldInput field={field} formField={formField} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ))
            )}

            <DialogFooter className="bg-transparent border-0 p-0 -mx-0 -mb-0">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
                className="border-border-default text-text-secondary"
              >
                취소
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={isPending}
                aria-label="실행 시작"
                className={cn(
                  "bg-accent-500 hover:bg-accent-600 text-text-on-accent border-transparent",
                  "focus-visible:ring-accent-500"
                )}
              >
                {isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                실행
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
