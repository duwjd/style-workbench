from __future__ import annotations

from style_workbench.domain.style.entity import NodeType

_NODE_TYPE_LABEL: dict[NodeType, str] = {
    NodeType.IMAGE_GENERATION: "image generation",
    NodeType.VIDEO_GENERATION: "video generation",
    NodeType.TEXT_GENERATION: "text generation",
    NodeType.COMPOSITION: "composition",
}


def summarize_for_evaluator(node_type: NodeType, brief_summary: str) -> str:
    """
    원본 prompt를 포함하지 않는 평가자용 컨텍스트 문자열을 반환한다.
    brief_summary는 caller(RunService)가 제공하는 brief 요약이며,
    비어 있으면 최소 컨텍스트를 반환한다.
    """
    label = _NODE_TYPE_LABEL.get(node_type, "content")
    if not brief_summary:
        return f"Evaluate the quality of this AI-generated {label}."
    return f"Content type: AI-generated {label}.\nBrief context: {brief_summary}"
