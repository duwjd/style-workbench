from __future__ import annotations

from style_workbench.adapters.base import ModelInput
from style_workbench.prompts.shared.safety import safety_block

EVALUATOR_MODEL: str = "claude-opus-4-6"
TEMPERATURE: float = 0.1
MAX_TOKENS: int = 1024


_DIMENSION_GUIDE: dict[str, str] = {
    "text_absence": (
        "Are there any unintended text artifacts, watermarks, logos, "
        "letters, or numbers anywhere in the image? A fully clean image "
        "scores 1.0; visible spurious text drops the score sharply."
    ),
    "resolution_quality": (
        "Is the image sharp with adequate resolution and free of blur, "
        "noise, banding, and compression artifacts?"
    ),
    "composition": (
        "Is the main subject placed deliberately (e.g. rule of thirds, "
        "balanced framing) with appropriate margins and no awkward cropping?"
    ),
    "face_natural": (
        "If a face is present, does it look anatomically natural with "
        "symmetric, well-proportioned features and no uncanny artifacts?"
    ),
    "skin_tone": (
        "If skin is visible, is the tone realistic with no plastic "
        "smoothing or unnatural color cast?"
    ),
    "identity_match": (
        "If a reference subject is implied by the brief context, is the "
        "subject's identity visually preserved (face, key design details)?"
    ),
    "scale_natural": (
        "Are the relative scales of subjects and objects physically "
        "plausible for the implied scene?"
    ),
    "lighting_match": (
        "Is the lighting direction, intensity, and color temperature "
        "consistent across all elements in the scene?"
    ),
    "shadow_consistent": (
        "Do all shadows agree on direction, softness, and darkness, "
        "consistent with a coherent light source?"
    ),
    "seam_clean": (
        "If the image is composited, are the boundaries between elements "
        "free of halos, color bleed, or edge artifacts?"
    ),
    "object_preserved": (
        "If a key object is implied by the brief context, is its shape, "
        "color, texture, and design preserved without arbitrary alteration?"
    ),
    "effect_physics": (
        "If a visual effect is present, does it obey real-world physics "
        "(light interaction, reflections, refractions, directional force)?"
    ),
    "effect_intensity": (
        "Is any visual effect calibrated to enhance rather than overwhelm the main subject?"
    ),
    "color_tone": (
        "Does the overall color grading and white balance feel intentional "
        "and consistent with the brief context?"
    ),
}


def _render_dimensions(dimensions: list[str]) -> str:
    lines: list[str] = []
    for d in dimensions:
        guide = _DIMENSION_GUIDE.get(d, "Score this dimension based on visual evidence.")
        lines.append(f"- {d}: {guide}")
    return "\n".join(lines)


def _build_system_prompt(dimensions: list[str]) -> str:
    dim_block = _render_dimensions(dimensions)
    schema_keys = ", ".join(f'"{d}"' for d in dimensions)
    return f"""You are a neutral image quality reviewer for an AI content workbench.
Your only job is to score a single generated image against named quality
dimensions, using the visual evidence in the attached image.

You are NOT the author of the image. You did NOT see the original
generation prompt. You are given only:
1. A short brief context (downstream summary of the designer's intent).
2. The generated image (attached).
3. The list of dimensions you must score.

Be strict and evidence-based. Score from what is actually visible.
If a dimension cannot be assessed because the relevant feature is not
present (e.g. no face for `face_natural`), score 1.0 and note in the
rationale that the dimension is not applicable.

Dimensions to score (each in [0.0, 1.0]):
{dim_block}

Output requirements (STRICT):
- Reply with a single JSON object and nothing else.
- Wrap it in a ```json ... ``` fenced block.
- Schema:
```json
{{
  "scores": {{ {schema_keys}: <float in [0.0, 1.0]> }},
  "rationale": {{ {schema_keys}: "<one short sentence citing visual evidence>" }},
  "notable_issues": ["<concrete observable defect>", "..."]
}}
```
- `scores` and `rationale` MUST contain exactly the dimension keys listed
  above and no others.
- `notable_issues` enumerates concrete visible defects that drove any
  low score. It may be empty.

{safety_block()}
"""


def build_image_eval_input(
    brief_ctx: str,
    image_url: str,
    dimensions: list[str],
) -> ModelInput:
    """이미지 노드 평가용 ModelInput을 만든다.

    brief_ctx는 ``shared.format_brief.summarize_for_evaluator`` 결과여야 하며,
    원본 prompt를 포함하지 않는다. ``image_url``은 vision 어댑터에 그대로
    전달된다.
    """
    if not dimensions:
        raise ValueError("dimensions must not be empty")
    if not image_url:
        raise ValueError("image_url must be provided for image evaluation")

    system = _build_system_prompt(dimensions)
    user_prompt = (
        f"{brief_ctx}\n\n"
        "The single generated image is attached. "
        "Score every listed dimension and produce the JSON object as specified."
    )
    return ModelInput(
        model_id=EVALUATOR_MODEL,
        prompt=user_prompt,
        system=system,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        image_urls=[image_url],
    )
