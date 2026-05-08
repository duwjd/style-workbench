import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { variantsApi } from "@/api/variants";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { StyleSummary } from "@/types";

const STEP_OPTIONS = [
  { value: "text_generation", label: "Text Generation" },
  { value: "image_generation", label: "Image Generation" },
  { value: "video_generation", label: "Video Generation" },
  { value: "composition", label: "Composition" },
] as const;

const INPUT_KIND_OPTIONS = [
  { value: "photo", label: "Photo" },
  { value: "text", label: "Text" },
  { value: "none", label: "None" },
] as const;

const schema = z.object({
  concept: z.string().min(2, "최소 2자 이상 입력하세요"),
  vertical: z.string().min(2, "최소 2자 이상 입력하세요"),
  tone: z.string().min(2, "최소 2자 이상 입력하세요"),
  stepComposition: z
    .array(z.string())
    .min(1, "최소 1개 이상 선택하세요"),
  inputKinds: z.array(z.string()),
  n: z.number().min(1).max(5).default(5),
});

type FormValues = z.infer<typeof schema>;

interface BriefFormProps {
  onSuccess: (variants: StyleSummary[]) => void;
}

export function BriefForm({ onSuccess }: BriefFormProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      concept: "",
      vertical: "",
      tone: "",
      stepComposition: [],
      inputKinds: [],
      n: 5,
    },
  });

  const { mutate, isPending } = useMutation({
    mutationFn: variantsApi.generate,
    onSuccess: (data) => {
      onSuccess(data);
    },
    onError: () => {
      toast.error("변주 생성에 실패했습니다. 다시 시도해 주세요.");
    },
  });

  function onSubmit(values: FormValues) {
    mutate(values);
  }

  return (
    <div className="max-w-xl mx-auto py-10 px-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-text-primary">새 Style 만들기</h1>
        <p className="text-text-secondary text-sm mt-1">
          브리프를 입력하면 AI가 {form.watch("n")}개의 변주를 생성합니다.
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="concept"
            render={({ field }) => (
              <FormItem>
                <FormLabel>컨셉</FormLabel>
                <FormControl>
                  <Input
                    placeholder="예: 자연 속의 고요한 명상"
                    className="bg-bg-surface border-border-default text-text-primary placeholder:text-text-tertiary"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="vertical"
            render={({ field }) => (
              <FormItem>
                <FormLabel>버티컬</FormLabel>
                <FormControl>
                  <Input
                    placeholder="예: wellness, fashion, travel"
                    className="bg-bg-surface border-border-default text-text-primary placeholder:text-text-tertiary"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="tone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>톤</FormLabel>
                <FormControl>
                  <Input
                    placeholder="예: 따뜻하고 몽환적인"
                    className="bg-bg-surface border-border-default text-text-primary placeholder:text-text-tertiary"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="stepComposition"
            render={({ field }) => (
              <FormItem>
                <FormLabel>단계 구성</FormLabel>
                <FormControl>
                  <div className="grid grid-cols-2 gap-2">
                    {STEP_OPTIONS.map((option) => {
                      const checked = field.value.includes(option.value);
                      return (
                        <label
                          key={option.value}
                          className={cn(
                            "flex items-center gap-2 rounded border p-2.5 cursor-pointer text-sm transition-colors nodrag nopan",
                            checked
                              ? "border-accent-500 bg-accent-500/10 text-text-primary"
                              : "border-border-subtle bg-bg-surface text-text-secondary hover:border-border-default hover:bg-bg-hover"
                          )}
                        >
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={checked}
                            onChange={(e) => {
                              const next = e.target.checked
                                ? [...field.value, option.value]
                                : field.value.filter(
                                    (v) => v !== option.value
                                  );
                              field.onChange(next);
                            }}
                          />
                          <span
                            className={cn(
                              "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border",
                              checked
                                ? "border-accent-500 bg-accent-500"
                                : "border-border-default bg-bg-elevated"
                            )}
                            aria-hidden="true"
                          >
                            {checked && (
                              <svg
                                viewBox="0 0 8 8"
                                className="h-2.5 w-2.5 text-text-on-accent"
                                fill="none"
                              >
                                <path
                                  d="M1 4l2 2 4-4"
                                  stroke="currentColor"
                                  strokeWidth="1.5"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              </svg>
                            )}
                          </span>
                          {option.label}
                        </label>
                      );
                    })}
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="inputKinds"
            render={({ field }) => (
              <FormItem>
                <FormLabel>입력 종류</FormLabel>
                <FormControl>
                  <div className="flex gap-2">
                    {INPUT_KIND_OPTIONS.map((option) => {
                      const checked = field.value.includes(option.value);
                      return (
                        <label
                          key={option.value}
                          className={cn(
                            "flex items-center gap-2 rounded border px-3 py-2 cursor-pointer text-sm transition-colors nodrag nopan",
                            checked
                              ? "border-accent-500 bg-accent-500/10 text-text-primary"
                              : "border-border-subtle bg-bg-surface text-text-secondary hover:border-border-default hover:bg-bg-hover"
                          )}
                        >
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={checked}
                            onChange={(e) => {
                              const next = e.target.checked
                                ? [...field.value, option.value]
                                : field.value.filter(
                                    (v) => v !== option.value
                                  );
                              field.onChange(next);
                            }}
                          />
                          {option.label}
                        </label>
                      );
                    })}
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="n"
            render={({ field }) => (
              <FormItem>
                <FormLabel>생성 개수 (최대 5)</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min={1}
                    max={5}
                    className="bg-bg-surface border-border-default text-text-primary w-24"
                    {...field}
                    onChange={(e) => field.onChange(Number(e.target.value))}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button
            type="submit"
            disabled={isPending}
            className="w-full bg-accent-500 hover:bg-accent-600 text-text-on-accent"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" aria-hidden="true" />
                {form.watch("n")}개 변주 생성 중...
              </>
            ) : (
              `${form.watch("n")}개 변주 생성`
            )}
          </Button>
        </form>
      </Form>
    </div>
  );
}
