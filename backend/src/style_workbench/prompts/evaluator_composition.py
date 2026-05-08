from __future__ import annotations

from style_workbench.adapters.base import ModelInput
from style_workbench.prompts.shared.safety import safety_block

EVALUATOR_MODEL: str = "claude-opus-4-6"
TEMPERATURE: float = 0.1
MAX_TOKENS: int = 1024


_DIMENSION_GUIDE: dict[str, str] = {
    "consistency": (
        "Is the composed result internally consistent in style, lighting, "
        "color grade, and perspective across its constituent elements?"
    ),
    "aesthetic_balance": (
        "Is the visual weight, framing, and negative space balanced and "
        "intentional rather than crowded or off-center?"
    ),
    "brief_match": (
        "Does the composition fulfill the intent implied by the brief "
        "context (subject, mood, vertical) without obvious deviation?"
    ),
}


def _render_dimensions(dimensions: list[str]) -> str:
    lines: list[str] = []
    for d in dimensions:
        guide = _DIMENSION_GUIDE.get(d, "Score this dimension based on visual evidence.")
        lines.append(f"- {d}: {guide}")
    return "\n".join(lines)


def _build_system_prompt(dimensions: list[str], has_image: bool) -> str:
    dim_block = _render_dimensions(dimensions)
    schema_keys = ", ".join(f'"{d}"' for d in dimensions)
    if has_image:
        evidence_clause = "The composed image is attached. Score from what is actually visible."
    else:
        evidence_clause = (
            "No composed image is attached. For any dimension that requires "
            "direct visual evidence, score around 0.5 and note the missing "
            "evidence in the rationale."
        )
    return f"""You are a neutral composition reviewer for an AI content workbench.
Your only job is to score a composed visual against named quality
dimensions, using the visual evidence available.

You are NOT the author of the composition. You did NOT see the original
generation prompt. You are given only:
1. A short brief context (downstream summary of the designer's intent).
2. {evidence_clause}
3. The list of dimensions you must score.

Be strict and evidence-based.

Dimensions to score (each in [0.0, 1.0]):
{dim_block}

Output requirements (STRICT):
- Reply with a single JSON object and nothing else.
- Wrap it in a ```json ... ``` fenced block.
- Schema:
```json
{{
  "scores": {{ {schema_keys}: <float in [0.0, 1.0]> }},
  "rationale": {{ {schema_keys}: "<one short sentence citing visual or contextual evidence>" }},
  "notable_issues": ["<concrete observable defect>", "..."]
}}
```
- `scores` and `rationale` MUST contain exactly the dimension keys listed
  above and no others.
- `notable_issues` enumerates concrete defects that drove any low score.
  It may be empty.

{safety_block()}
"""


def build_composition_eval_input(
    brief_ctx: str,
    image_url: str | None,
    dimensions: list[str],
) -> ModelInput:
    """Composition 노드 평가용 ModelInput을 만든다.

    brief_ctx는 ``shared.format_brief.summarize_for_evaluator`` 결과여야 한다.
    ``image_url``이 None이면 ``image_urls=[]``로 처리한다.
    """
    if not dimensions:
        raise ValueError("dimensions must not be empty")

    has_image = image_url is not None and image_url != ""
    system = _build_system_prompt(dimensions, has_image=has_image)
    if has_image:
        evidence_line = "The composed image is attached."
    else:
        evidence_line = (
            "No composed image is attached. Score under the constraints noted in the system prompt."
        )
    user_prompt = (
        f"{brief_ctx}\n\n"
        f"{evidence_line}\n"
        "Score every listed dimension and produce the JSON object as specified."
    )
    image_urls: list[str] = [image_url] if has_image and image_url is not None else []
    return ModelInput(
        model_id=EVALUATOR_MODEL,
        prompt=user_prompt,
        system=system,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        image_urls=image_urls,
    )
