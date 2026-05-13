import { useState } from "react";
import { Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DeclaredVariable } from "@/types/prompts";

interface DeclaredVariablesEditorProps {
  variables: DeclaredVariable[];
  onChange: (variables: DeclaredVariable[]) => void;
  readOnly?: boolean;
}

export function DeclaredVariablesEditor({
  variables,
  onChange,
  readOnly = false,
}: DeclaredVariablesEditorProps) {
  const [varName, setVarName] = useState("");
  const [varRole, setVarRole] = useState("");

  function addVariable() {
    const name = varName.trim();
    if (!name) return;
    if (variables.find((v) => v.name === name)) return;
    onChange([...variables, { name, role: varRole.trim(), required: true }]);
    setVarName("");
    setVarRole("");
  }

  function removeVariable(name: string) {
    onChange(variables.filter((v) => v.name !== name));
  }

  function toggleRequired(name: string) {
    onChange(variables.map((v) => v.name === name ? { ...v, required: !v.required } : v));
  }

  return (
    <div className="space-y-2">
      <p className="text-caption font-medium text-text-secondary" id="declared-vars-label">
        선언 변수 (Declared Variables)
      </p>

      {/* Variable list */}
      {variables.length > 0 && (
        <ul className="space-y-1" aria-labelledby="declared-vars-label">
          {variables.map((v) => (
            <li
              key={v.name}
              className="flex items-center gap-2 rounded border border-border-subtle bg-bg-elevated px-2 py-1.5"
            >
              <span
                className="inline-flex rounded px-1.5 py-0.5 text-xs font-mono bg-accent-500/15 text-accent-300 border border-accent-500/30 shrink-0"
                aria-label={`변수명: ${v.name}`}
              >
                {"{"}{v.name}{"}"}
              </span>
              <span className="flex-1 text-xs text-text-tertiary truncate" aria-label={`역할: ${v.role || "—"}`}>
                {v.role || <span className="text-text-disabled italic">역할 없음</span>}
              </span>
              {!readOnly && (
                <>
                  <button
                    type="button"
                    onClick={() => toggleRequired(v.name)}
                    className={cn(
                      "text-xs rounded px-1 py-0.5 border transition-colors shrink-0",
                      v.required
                        ? "border-error/30 bg-error/10 text-error"
                        : "border-border-subtle bg-bg-elevated text-text-disabled",
                      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                    )}
                    aria-label={v.required ? `${v.name} 필수 → 선택으로 변경` : `${v.name} 선택 → 필수로 변경`}
                  >
                    {v.required ? "필수" : "선택"}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeVariable(v.name)}
                    className={cn(
                      "rounded p-0.5 text-text-tertiary hover:text-error shrink-0",
                      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
                    )}
                    aria-label={`변수 ${v.name} 제거`}
                  >
                    <X className="h-3 w-3" aria-hidden="true" />
                  </button>
                </>
              )}
              {readOnly && (
                <span
                  className={cn(
                    "text-xs rounded px-1 py-0.5 border shrink-0",
                    v.required
                      ? "border-error/30 bg-error/10 text-error"
                      : "border-border-subtle bg-bg-elevated text-text-disabled"
                  )}
                >
                  {v.required ? "필수" : "선택"}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {variables.length === 0 && (
        <p className="text-caption text-text-disabled rounded border border-border-subtle bg-bg-elevated p-2 text-center">
          선언된 변수 없음
        </p>
      )}

      {/* Add variable row */}
      {!readOnly && (
        <div className="flex gap-1.5">
          <input
            type="text"
            value={varName}
            onChange={(e) => setVarName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addVariable())}
            placeholder="변수명"
            className={cn(
              "flex-1 min-w-0 rounded border border-border-default bg-bg-canvas",
              "px-2 py-1 text-xs text-text-primary placeholder:text-text-disabled",
              "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
            )}
            aria-label="새 변수명 입력"
          />
          <input
            type="text"
            value={varRole}
            onChange={(e) => setVarRole(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addVariable())}
            placeholder="역할"
            className={cn(
              "flex-1 min-w-0 rounded border border-border-default bg-bg-canvas",
              "px-2 py-1 text-xs text-text-primary placeholder:text-text-disabled",
              "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
            )}
            aria-label="변수 역할 입력"
          />
          <button
            type="button"
            onClick={addVariable}
            className={cn(
              "rounded border border-border-default bg-bg-elevated px-2 py-1 shrink-0",
              "text-text-secondary hover:text-text-primary hover:bg-bg-hover",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
              "transition-colors"
            )}
            aria-label="변수 추가"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
}
