import { useState } from "react";
import { X, Library, ExternalLink, Pin } from "lucide-react";
import { Link } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { promptsApi } from "@/api/prompts";
import { PromptLibraryPickerDialog } from "@/features/prompts/PromptLibraryPickerDialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Node } from "@xyflow/react";
import type { PromptResponse, PromptNodeType } from "@/types/prompts";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type VariableMappingSource = "user_input" | "node_output" | "constant";

export interface VariableMapping {
  source: VariableMappingSource;
  /** source === "user_input" 일 때 */
  role?: string;
  /** source === "node_output" 일 때 */
  nodeId?: string;
  /** source === "constant" 일 때 */
  value?: string;
}

export type VariableMappingMap = Record<string, VariableMapping>;

const VARIABLE_RE = /\{(\w+)\}/g;

/** 템플릿에서 {placeholder} 목록 추출 (중복 제거) */
export function extractVariables(template: string): string[] {
  const matches = [...template.matchAll(VARIABLE_RE)].map((m) => m[1]);
  return [...new Set(matches)];
}

const SOURCE_LABELS: Record<VariableMappingSource, string> = {
  user_input: "사용자 입력",
  node_output: "노드 출력",
  constant: "고정값",
};

const NODE_TYPE_LABELS: Record<string, string> = {
  text_generation: "Text Generation",
  image_generation: "Image Generation",
  video_generation: "Video Generation",
  composition: "Composition",
};

interface VariableMappingRowProps {
  variable: string;
  mapping: VariableMapping;
  otherNodes: Node[];
  onChange: (updated: VariableMapping) => void;
}

function VariableMappingRow({
  variable,
  mapping,
  otherNodes,
  onChange,
}: VariableMappingRowProps) {
  return (
    <div
      className="rounded border border-border-subtle bg-bg-elevated p-2 space-y-2"
      aria-label={`변수 ${variable} 매핑`}
    >
      <p className="text-xs font-mono text-accent-300">
        {"{"}
        {variable}
        {"}"}
      </p>

      {/* source 선택 */}
      <div className="space-y-1">
        <label className="text-xs text-text-tertiary" htmlFor={`source-${variable}`}>
          소스
        </label>
        <Select
          value={mapping.source}
          onValueChange={(val) =>
            onChange({ source: val as VariableMappingSource })
          }
        >
          <SelectTrigger
            id={`source-${variable}`}
            size="sm"
            className={cn(
              "w-full bg-bg-canvas border-border-default text-text-primary",
              "nodrag nopan"
            )}
            aria-label={`${variable} 소스 선택`}
          >
            <SelectValue placeholder="소스 선택" />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(SOURCE_LABELS) as VariableMappingSource[]).map((src) => (
              <SelectItem key={src} value={src}>
                {SOURCE_LABELS[src]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* source별 추가 입력 */}
      {mapping.source === "user_input" && (
        <div className="space-y-1">
          <label
            className="text-xs text-text-tertiary"
            htmlFor={`role-${variable}`}
          >
            역할(role)
          </label>
          <input
            id={`role-${variable}`}
            type="text"
            value={mapping.role ?? ""}
            onChange={(e) => onChange({ ...mapping, role: e.target.value })}
            placeholder="예: photo, name, description"
            className={cn(
              "w-full rounded border border-border-default bg-bg-canvas",
              "px-2 py-1 text-xs text-text-primary placeholder:text-text-disabled",
              "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
              "nodrag nopan"
            )}
            aria-label={`${variable} 역할 입력`}
          />
        </div>
      )}

      {mapping.source === "node_output" && (
        <div className="space-y-1">
          <label
            className="text-xs text-text-tertiary"
            htmlFor={`node-${variable}`}
          >
            노드 선택
          </label>
          <Select
            value={mapping.nodeId ?? ""}
            onValueChange={(val) => onChange({ ...mapping, nodeId: val })}
          >
            <SelectTrigger
              id={`node-${variable}`}
              size="sm"
              className={cn(
                "w-full bg-bg-canvas border-border-default text-text-primary",
                "nodrag nopan"
              )}
              aria-label={`${variable} 출력 노드 선택`}
            >
              <SelectValue placeholder="노드 선택" />
            </SelectTrigger>
            <SelectContent>
              {otherNodes.length === 0 ? (
                <SelectItem value="__none" disabled>
                  연결 가능한 노드 없음
                </SelectItem>
              ) : (
                otherNodes.map((n) => (
                  <SelectItem key={n.id} value={n.id}>
                    {NODE_TYPE_LABELS[n.type ?? ""] ?? n.type} ({n.id.slice(-6)})
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      )}

      {mapping.source === "constant" && (
        <div className="space-y-1">
          <label
            className="text-xs text-text-tertiary"
            htmlFor={`const-${variable}`}
          >
            고정값
          </label>
          <input
            id={`const-${variable}`}
            type="text"
            value={mapping.value ?? ""}
            onChange={(e) => onChange({ ...mapping, value: e.target.value })}
            placeholder="고정 문자열 입력"
            className={cn(
              "w-full rounded border border-border-default bg-bg-canvas",
              "px-2 py-1 text-xs text-text-primary placeholder:text-text-disabled",
              "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
              "nodrag nopan"
            )}
            aria-label={`${variable} 고정값 입력`}
          />
        </div>
      )}
    </div>
  );
}

// F05: DAG 노드 타입 → Prompt Library 노드 타입 매핑
const DAG_TO_PROMPT_NODE_TYPE: Record<string, PromptNodeType> = {
  text_generation: "text",
  image_generation: "image",
  video_generation: "video",
  composition: "composition",
};

interface PromptEditorProps {
  selectedNodeId: string | null;
  nodes: Node[];
  onClose: () => void;
  onUpdateNode: (nodeId: string, data: Record<string, unknown>) => void;
}

export function PromptEditor({
  selectedNodeId,
  nodes,
  onClose,
  onUpdateNode,
}: PromptEditorProps) {
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  // F05: Library picker + extract-to-library dialog state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [extractDialogOpen, setExtractDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  if (!selectedNode) return null;

  const data = selectedNode.data as {
    promptTemplate?: string;
    model?: { provider?: string; modelId?: string };
    variableMapping?: VariableMappingMap;
    // F05 Library 연동 필드
    promptId?: string;
    promptVersionId?: string;
    promptPinned?: boolean;
  };

  const promptTemplate = data.promptTemplate ?? "";
  const variableMapping: VariableMappingMap = data.variableMapping ?? {};
  const variables = extractVariables(promptTemplate);
  const nodeTypeLabel =
    NODE_TYPE_LABELS[selectedNode.type ?? ""] ?? selectedNode.type ?? "노드";

  // F05: Library 연결 여부
  const isLinkedToLibrary = !!data.promptId;

  // 현재 노드를 제외한 다른 노드들 (node_output 소스 선택용)
  const otherNodes = nodes.filter((n) => n.id !== selectedNode.id);

  function handleMappingChange(variable: string, updated: VariableMapping) {
    const newMapping: VariableMappingMap = {
      ...variableMapping,
      [variable]: updated,
    };
    onUpdateNode(selectedNode.id, {
      ...data,
      variableMapping: newMapping,
    });
  }

  // F05: Library에서 Prompt 선택 시 노드에 링크
  function handleLibrarySelect(prompt: PromptResponse) {
    onUpdateNode(selectedNode.id, {
      ...data,
      promptId: prompt.id,
      promptVersionId: prompt.currentVersion?.id ?? null,
      promptPinned: false,
      promptTemplate: null, // Library 연결 시 인라인 본문 비움
    });
    toast.success(`"${prompt.name}"이 연결되었습니다.`);
  }

  // F05: Library 연결 해제
  function handleUnlink() {
    onUpdateNode(selectedNode.id, {
      ...data,
      promptId: undefined,
      promptVersionId: undefined,
      promptPinned: undefined,
    });
  }

  // F05: Library로 추출 mutation
  const { mutate: extractToLibrary, isPending: isExtracting } = useMutation({
    mutationFn: () => {
      const nodeType = DAG_TO_PROMPT_NODE_TYPE[selectedNode.type ?? ""] ?? "text";
      return promptsApi.create({
        name: `${nodeTypeLabel} — ${selectedNode.id}`,
        nodeType,
        body: promptTemplate,
        declaredVariables: variables.map((v) => ({ name: v, role: "", required: true })),
      });
    },
    onSuccess: (result) => {
      onUpdateNode(selectedNode.id, {
        ...data,
        promptId: result.data.id,
        promptVersionId: result.data.currentVersion?.id ?? null,
        promptPinned: false,
        promptTemplate: null,
      });
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      toast.success("Library에 추출되었습니다.");
      setExtractDialogOpen(false);
    },
    onError: () => {
      toast.error("Library 추출에 실패했습니다.");
    },
  });

  return (
    <aside
      className="w-72 bg-bg-surface border-l border-border-subtle flex flex-col shrink-0"
      aria-label="노드 편집기"
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle shrink-0">
        <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider">
          {nodeTypeLabel}
        </p>
        <button
          onClick={onClose}
          className={cn(
            "rounded p-0.5 text-text-tertiary hover:text-text-primary hover:bg-bg-hover",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
            "nodrag nopan"
          )}
          aria-label="편집기 닫기"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      {/* F05: Library 연결 상태 표시 */}
      {isLinkedToLibrary ? (
        <div className="px-3 pt-3 space-y-1.5 shrink-0">
          <div className="rounded border border-accent-500/30 bg-accent-500/10 px-2 py-2 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1 text-xs text-accent-300 font-medium">
                <Library className="h-3 w-3" aria-hidden="true" />
                Library 연결됨
              </span>
              <Link
                to={`/prompts/${data.promptId}`}
                className={cn(
                  "flex items-center gap-0.5 text-xs text-accent-300 hover:text-accent-200",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded",
                  "nodrag nopan"
                )}
                aria-label="Library에서 편집"
              >
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
                편집
              </Link>
            </div>
            {/* Pinned 토글 */}
            <label className="flex items-center gap-1.5 cursor-pointer nodrag nopan">
              <input
                type="checkbox"
                checked={data.promptPinned ?? false}
                onChange={(e) =>
                  onUpdateNode(selectedNode.id, {
                    ...data,
                    promptPinned: e.target.checked,
                  })
                }
                className="h-3 w-3 rounded border border-border-default bg-bg-canvas accent-accent-500"
                aria-label="버전 고정 (Library에서 promote해도 자동 갱신 안 됨)"
              />
              <span className="flex items-center gap-0.5 text-xs text-text-secondary">
                <Pin className="h-3 w-3" aria-hidden="true" />
                이 버전에 고정
              </span>
            </label>
            <button
              type="button"
              onClick={handleUnlink}
              className={cn(
                "text-xs text-text-tertiary hover:text-error transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500 rounded",
                "nodrag nopan"
              )}
              aria-label="Library 연결 해제"
            >
              연결 해제
            </button>
          </div>
        </div>
      ) : (
        /* F05: Library에서 선택 버튼 (인라인 모드) */
        <div className="px-3 pt-3 shrink-0">
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            className={cn(
              "w-full flex items-center justify-center gap-1.5 rounded border border-border-default",
              "px-2 py-1.5 text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
              "transition-colors nodrag nopan"
            )}
            aria-label="Library에서 Prompt 선택"
          >
            <Library className="h-3.5 w-3.5" aria-hidden="true" />
            Library에서 선택
          </button>
        </div>
      )}

      {/* 모델 정보 (탭 바깥) */}
      {data.model && (
        <div className="px-3 pt-3 space-y-1 shrink-0">
          <p className="text-xs font-medium text-text-secondary">모델</p>
          <div className="rounded border border-border-subtle bg-bg-elevated px-2 py-1.5 space-y-0.5">
            <p className="text-xs text-text-tertiary">
              <span className="text-text-secondary">Provider: </span>
              {data.model.provider || (
                <span className="text-text-disabled">미설정</span>
              )}
            </p>
            <p className="text-xs text-text-tertiary">
              <span className="text-text-secondary">Model ID: </span>
              {data.model.modelId || (
                <span className="text-text-disabled">미설정</span>
              )}
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex-1 overflow-hidden flex flex-col mt-3">
        <Tabs defaultValue="prompt" className="flex flex-col flex-1 overflow-hidden px-3 pb-3">
          <TabsList
            className={cn(
              "shrink-0 w-full bg-bg-elevated border border-border-subtle",
              "rounded-lg p-0.5 mb-3"
            )}
          >
            <TabsTrigger
              value="prompt"
              className={cn(
                "flex-1 text-xs text-text-secondary nodrag nopan",
                "data-active:bg-bg-surface data-active:text-text-primary"
              )}
            >
              프롬프트
            </TabsTrigger>
            <TabsTrigger
              value="variables"
              className={cn(
                "flex-1 text-xs text-text-secondary nodrag nopan",
                "data-active:bg-bg-surface data-active:text-text-primary"
              )}
            >
              변수 매핑
              {variables.length > 0 && (
                <span
                  className="ml-1 inline-flex items-center justify-center rounded-full bg-accent-500/20 text-accent-300 w-4 h-4 text-[10px] leading-none"
                  aria-label={`${variables.length}개 변수`}
                >
                  {variables.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          {/* 프롬프트 탭 */}
          <TabsContent
            value="prompt"
            className="flex-1 overflow-y-auto space-y-3 nodrag"
          >
            <div className="space-y-1">
              <label
                htmlFor="prompt-template"
                className="text-xs font-medium text-text-secondary"
              >
                프롬프트 템플릿
                {isLinkedToLibrary && (
                  <span className="ml-1 text-xs text-text-disabled">(읽기 전용)</span>
                )}
              </label>
              <textarea
                id="prompt-template"
                value={promptTemplate}
                onChange={(e) => {
                  if (isLinkedToLibrary) return;
                  onUpdateNode(selectedNode.id, {
                    ...data,
                    promptTemplate: e.target.value,
                  });
                }}
                readOnly={isLinkedToLibrary}
                placeholder="{subject}를 이용하여 생성하세요..."
                rows={8}
                className={cn(
                  "w-full resize-y rounded border border-border-default bg-bg-canvas",
                  "px-2 py-1.5 text-xs text-text-primary placeholder:text-text-disabled",
                  "focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500",
                  "transition-colors nodrag nopan",
                  isLinkedToLibrary && "opacity-60 cursor-not-allowed border-border-subtle"
                )}
                aria-describedby="prompt-variables-hint"
                aria-readonly={isLinkedToLibrary}
              />
            </div>

            {/* F05: Library로 추출 제안 (인라인 본문이 있을 때) */}
            {!isLinkedToLibrary && promptTemplate.length > 0 && (
              <button
                type="button"
                onClick={() => setExtractDialogOpen(true)}
                className={cn(
                  "w-full flex items-center justify-center gap-1.5 rounded border border-border-subtle",
                  "px-2 py-1.5 text-xs text-text-tertiary hover:text-text-secondary hover:bg-bg-hover",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500",
                  "transition-colors nodrag nopan"
                )}
                aria-label="이 Prompt를 Library로 추출"
              >
                <Library className="h-3.5 w-3.5" aria-hidden="true" />
                Library로 추출 (재사용 가능)
              </button>
            )}

            {/* 감지된 변수 미리보기 */}
            <div className="space-y-1" id="prompt-variables-hint">
              <p className="text-xs font-medium text-text-secondary">감지된 변수</p>
              {variables.length === 0 ? (
                <p className="text-xs text-text-disabled">
                  {"{variable}"} 형태로 변수를 입력하세요.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {variables.map((v) => (
                    <span
                      key={v}
                      className="inline-flex items-center rounded px-2 py-0.5 text-xs bg-accent-500/15 text-accent-300 border border-accent-500/30"
                    >
                      {"{"}
                      {v}
                      {"}"}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* 노드 ID */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-text-secondary">노드 ID</p>
              <p className="text-xs text-text-disabled font-mono break-all">
                {selectedNode.id}
              </p>
            </div>
          </TabsContent>

          {/* 변수 매핑 탭 */}
          <TabsContent
            value="variables"
            className="flex-1 overflow-y-auto space-y-2 nodrag"
          >
            {variables.length === 0 ? (
              <div className="rounded border border-border-subtle bg-bg-elevated p-3 text-center">
                <p className="text-xs text-text-disabled">
                  프롬프트 탭에서{" "}
                  <span className="font-mono text-accent-300">{"{"}</span>
                  variable
                  <span className="font-mono text-accent-300">{"}"}</span>{" "}
                  형태로 변수를 추가하면 여기서 매핑할 수 있습니다.
                </p>
              </div>
            ) : (
              variables.map((variable) => (
                <VariableMappingRow
                  key={variable}
                  variable={variable}
                  mapping={
                    variableMapping[variable] ?? { source: "user_input", role: "" }
                  }
                  otherNodes={otherNodes}
                  onChange={(updated) => handleMappingChange(variable, updated)}
                />
              ))
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* F05: Library picker dialog */}
      <PromptLibraryPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onSelect={handleLibrarySelect}
        defaultNodeType={DAG_TO_PROMPT_NODE_TYPE[selectedNode.type ?? ""] ?? undefined}
      />

      {/* F05: Library로 추출 확인 dialog */}
      <Dialog open={extractDialogOpen} onOpenChange={setExtractDialogOpen}>
        <DialogContent className="bg-bg-surface border-border-default text-text-primary max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-h3 text-text-primary">Library로 추출</DialogTitle>
          </DialogHeader>
          <p className="text-body text-text-secondary">
            이 Prompt를 Library에 저장하면 다른 Style에서도 재사용할 수 있습니다.
            추출 후 이 노드는 Library Prompt와 연결됩니다.
          </p>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setExtractDialogOpen(false)}
              disabled={isExtracting}
            >
              취소
            </Button>
            <Button
              onClick={() => extractToLibrary()}
              disabled={isExtracting}
              className="bg-accent-500 hover:bg-accent-600 text-text-on-accent border-transparent"
            >
              {isExtracting ? "추출 중..." : "Library로 추출"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
