import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle } from "lucide-react";
import type { DeclaredVariable } from "@/types/prompts";

const PLACEHOLDER_RE = /\{(\w+)\}/g;

function extractPlaceholders(body: string): string[] {
  const matches = [...body.matchAll(PLACEHOLDER_RE)].map((m) => m[1]);
  return [...new Set(matches)];
}

interface ValidationResult {
  undeclared: string[];  // body에 있지만 declared에 없는 것
  unused: string[];      // declared에 있지만 body에 없는 것
}

function validateVariables(body: string, declared: DeclaredVariable[]): ValidationResult {
  const inBody = extractPlaceholders(body);
  const declaredNames = declared.map((v) => v.name);
  const undeclared = inBody.filter((p) => !declaredNames.includes(p));
  const unused = declaredNames.filter((n) => !inBody.includes(n));
  return { undeclared, unused };
}

interface PromptBodyEditorProps {
  body: string;
  onChange: (body: string) => void;
  declaredVariables: DeclaredVariable[];
  warnings?: string[];
  readOnly?: boolean;
}

export function PromptBodyEditor({
  body,
  onChange,
  declaredVariables,
  warnings = [],
  readOnly = false,
}: PromptBodyEditorProps) {
  const { undeclared, unused } = validateVariables(body, declaredVariables);
  const placeholders = extractPlaceholders(body);
  const isValid = undeclared.length === 0;

  return (
    <div className="space-y-3">
      {/* Textarea */}
      <div className="relative">
        <textarea
          value={body}
          onChange={(e) => onChange(e.target.value)}
          readOnly={readOnly}
          rows={10}
          placeholder="{name}님의 공식 인사말을 생성해주세요..."
          className={cn(
            "w-full resize-y rounded border bg-bg-canvas",
            "px-3 py-2 text-body text-text-primary placeholder:text-text-disabled font-mono",
            "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
            "transition-colors",
            readOnly
              ? "border-border-subtle opacity-70 cursor-not-allowed"
              : "border-border-default",
            !isValid && !readOnly && "border-error/50 focus:ring-error/50"
          )}
          aria-label="프롬프트 본문"
          aria-invalid={!isValid}
          aria-describedby="prompt-body-hints"
        />
        {readOnly && (
          <div className="absolute top-2 right-2">
            <span className="text-xs text-text-disabled rounded border border-border-subtle px-1.5 py-0.5 bg-bg-elevated">
              읽기 전용
            </span>
          </div>
        )}
      </div>

      {/* Validation hints */}
      <div id="prompt-body-hints" className="space-y-2">
        {/* 감지된 placeholder */}
        {placeholders.length > 0 && (
          <div className="flex flex-wrap gap-1 items-center">
            <span className="text-caption text-text-tertiary">감지된 변수:</span>
            {placeholders.map((p) => {
              const isUndeclared = undeclared.includes(p);
              return (
                <span
                  key={p}
                  className={cn(
                    "inline-flex items-center rounded px-1.5 py-0.5 text-xs border",
                    isUndeclared
                      ? "bg-error/15 text-error border-error/30"
                      : "bg-accent-500/15 text-accent-300 border-accent-500/30"
                  )}
                  aria-label={isUndeclared ? `미선언 변수: ${p}` : `선언된 변수: ${p}`}
                >
                  {"{"}  {p}  {"}"}
                  {isUndeclared && (
                    <AlertTriangle className="ml-1 h-3 w-3" aria-hidden="true" />
                  )}
                </span>
              );
            })}
          </div>
        )}

        {/* 오류: 미선언 변수 */}
        {undeclared.length > 0 && (
          <div
            className="flex items-start gap-1.5 rounded border border-error/30 bg-error/10 px-2 py-1.5"
            role="alert"
          >
            <AlertTriangle className="h-4 w-4 text-error shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <p className="text-caption text-error font-medium">미선언 변수</p>
              <p className="text-caption text-error/80">
                {undeclared.map((v) => `{${v}}`).join(", ")}를 아래 선언 변수에 추가해주세요.
              </p>
            </div>
          </div>
        )}

        {/* 경고: 사용되지 않는 선언 변수 */}
        {unused.length > 0 && (
          <div
            className="flex items-start gap-1.5 rounded border border-warning/30 bg-warning/10 px-2 py-1.5"
          >
            <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-caption text-warning">
              선언되었지만 본문에 없는 변수: {unused.map((v) => `{${v}}`).join(", ")}
            </p>
          </div>
        )}

        {/* 서버 경고 (의심스러운 패턴) */}
        {warnings.map((w, i) => (
          <div
            key={i}
            className="flex items-start gap-1.5 rounded border border-warning/30 bg-warning/10 px-2 py-1.5"
          >
            <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-caption text-warning">{w}</p>
          </div>
        ))}

        {/* 모든 검증 통과 */}
        {isValid && placeholders.length > 0 && !readOnly && (
          <div className="flex items-center gap-1.5">
            <CheckCircle className="h-4 w-4 text-success" aria-hidden="true" />
            <p className="text-caption text-success">모든 변수가 선언되었습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
