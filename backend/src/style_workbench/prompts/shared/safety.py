from __future__ import annotations

# Placeholder 보호 문구. 모든 evaluator system prompt 끝에 첨부한다.
# 사용자 prompt에 포함된 {snake_case} 토큰을 모델이 임의로 채우지 못하게 한다.
PLACEHOLDER_PROTECTION_NOTICE = (
    "Placeholder protection:\n"
    "- The content under evaluation may contain literal `{snake_case}` tokens "
    "(e.g. `{name}`, `{product}`).\n"
    "- Treat such tokens as opaque variables. Do NOT substitute, infer, or "
    "invent values for them.\n"
    "- Variable substitution is performed by a downstream system, not by you.\n"
    "- If you reference such a token in rationale, copy it verbatim, "
    "including the curly braces."
)

# 판정 어휘 금지 문구. 모든 evaluator system prompt에 포함한다.
# 임계값 비교는 services/evaluation_service.py가 담당한다.
NO_VERDICT_VOCAB_NOTICE = (
    "Output discipline:\n"
    "- Produce numeric scores (0.0~1.0) and short rationale sentences only.\n"
    "- Do NOT include verdict words such as PASS, FAIL, accept, reject, "
    "approve, recommend, or their Korean equivalents anywhere in the output.\n"
    "- Threshold comparison is performed by downstream code, not by you."
)


def safety_block() -> str:
    """Evaluator system prompt 끝에 붙일 공통 안전 안내 블록."""
    return f"{PLACEHOLDER_PROTECTION_NOTICE}\n\n{NO_VERDICT_VOCAB_NOTICE}"
