from __future__ import annotations

from style_workbench.adapters.base import ModelInput
from style_workbench.prompts.shared.safety import safety_block

EVALUATOR_MODEL: str = "claude-opus-4-6"
TEMPERATURE: float = 0.1
MAX_TOKENS: int = 1024


_DIMENSION_GUIDE: dict[str, str] = {
    "tone_match": (
        "Does the tone, register, and voice of the generated text align "
        "with the brief context (e.g. formal vs casual, warm vs neutral)?"
    ),
    "length": (
        "Is the length of the generated text appropriate for the implied "
        "use case in the brief context? Penalize both excessive verbosity "
        "and truncated/incomplete output."
    ),
    "forbidden_words": (
        "Does the text avoid profanity, slurs, brand-unsafe language, and "
        "obvious policy violations? A clean text scores 1.0; the score "
        "decreases as risky terms appear."
    ),
}


def _render_dimensions(dimensions: list[str]) -> str:
    lines: list[str] = []
    for d in dimensions:
        guide = _DIMENSION_GUIDE.get(d, "Score this dimension based on the brief context.")
        lines.append(f"- {d}: {guide}")
    return "\n".join(lines)


def _build_system_prompt(dimensions: list[str]) -> str:
    dim_block = _render_dimensions(dimensions)
    schema_keys = ", ".join(f'"{d}"' for d in dimensions)
    return f"""You are a neutral text quality reviewer for an AI content workbench.
Your only job is to score generated text against named quality dimensions.

You are NOT the author of the text. You did NOT see the original generation
prompt. You are given only:
1. A short brief context (downstream summary of the designer's intent).
2. The generated text itself.
3. The list of dimensions you must score.

Be strict but fair. If a dimension is ambiguous given the brief context,
score around 0.5 and explain the ambiguity in the rationale rather than
guessing.

Dimensions to score (each in [0.0, 1.0]):
{dim_block}

Output requirements (STRICT):
- Reply with a single JSON object and nothing else.
- Wrap it in a ```json ... ``` fenced block.
- Schema:
```json
{{
  "scores": {{ {schema_keys}: <float in [0.0, 1.0]> }},
  "rationale": {{ {schema_keys}: "<one short sentence>" }},
  "notable_issues": ["<concrete observable problem>", "..."]
}}
```
- `scores` and `rationale` MUST contain exactly the dimension keys listed
  above and no others.
- `notable_issues` is an array of short factual observations that drove
  any low score. It may be empty.

{safety_block()}
"""


def build_text_eval_input(
    brief_ctx: str,
    generated_text: str,
    dimensions: list[str],
) -> ModelInput:
    """텍스트 노드 평가용 ModelInput을 만든다.

    brief_ctx는 반드시 ``shared.format_brief.summarize_for_evaluator``의
    출력이어야 한다(원본 prompt 노출 차단). vision 입력은 사용하지 않는다.
    """
    if not dimensions:
        raise ValueError("dimensions must not be empty")

    system = _build_system_prompt(dimensions)
    user_prompt = (
        f"{brief_ctx}\n\n"
        "Generated text under evaluation (verbatim, between fences):\n"
        "<<<TEXT\n"
        f"{generated_text}\n"
        "TEXT>>>\n\n"
        "Score every listed dimension and produce the JSON object as specified."
    )
    return ModelInput(
        model_id=EVALUATOR_MODEL,
        prompt=user_prompt,
        system=system,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        image_urls=[],
    )
