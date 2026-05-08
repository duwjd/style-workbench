from __future__ import annotations

from style_workbench.adapters.base import ModelInput
from style_workbench.prompts.shared.safety import safety_block

EVALUATOR_MODEL: str = "claude-opus-4-6"
TEMPERATURE: float = 0.1
MAX_TOKENS: int = 1024


_DIMENSION_GUIDE: dict[str, str] = {
    "motion_artifact": (
        "Across the supplied frames, are there flickering, warping, "
        "morphing, or glitch artifacts between frames? A clean video "
        "scores 1.0; visible inter-frame artifacts drop the score."
    ),
    "subject_preservation": (
        "Is the subject's shape, identity, and key features preserved "
        "across all supplied frames with no melting or stretching?"
    ),
    "motion_compliance": (
        "Does the camera/subject motion match the type implied by the "
        "brief context (e.g. zoom vs pan vs tilt)? Score lower if a "
        "different motion is observed than implied."
    ),
    "speed_consistency": (
        "Is the motion speed approximately uniform across the supplied "
        "frames, with no unexplained acceleration, deceleration, or pauses?"
    ),
    "face_consistency": (
        "If a face is present, is it the same identity across all frames "
        "with no morphing or feature drift?"
    ),
    "composite_seam": (
        "If composited elements are implied, do their boundaries remain "
        "invisible across frames during motion?"
    ),
    "object_stability": (
        "If a composited or attached object is implied, does it move as a "
        "rigid body with the subject, with no floating, sliding, or drift?"
    ),
    "effect_continuity": (
        "If a visual effect is present, is it temporally continuous with "
        "no sudden appearance, disappearance, or flicker?"
    ),
}


def _render_dimensions(dimensions: list[str]) -> str:
    lines: list[str] = []
    for d in dimensions:
        guide = _DIMENSION_GUIDE.get(d, "Score this dimension based on the supplied frames.")
        lines.append(f"- {d}: {guide}")
    return "\n".join(lines)


def _build_system_prompt(dimensions: list[str], n_frames: int) -> str:
    dim_block = _render_dimensions(dimensions)
    schema_keys = ", ".join(f'"{d}"' for d in dimensions)
    if n_frames > 0:
        evidence_clause = (
            f"You are given {n_frames} sampled frames from the video, in "
            "temporal order (earliest to latest). Treat them as keyframes "
            "and reason about inter-frame consistency from them."
        )
    else:
        evidence_clause = (
            "No frames are attached. Score based only on the brief context "
            "and any textual evidence available; for any dimension that "
            "requires direct visual evidence, score around 0.5 and note the "
            "lack of frames in the rationale."
        )
    return f"""You are a neutral video quality reviewer for an AI content workbench.
Your only job is to score a generated video against named quality
dimensions, using the supplied frame evidence.

You are NOT the author of the video. You did NOT see the original
generation prompt. You are given only:
1. A short brief context (downstream summary of the designer's intent).
2. {evidence_clause}
3. The list of dimensions you must score.

Be strict and evidence-based. Reason about temporal continuity from the
ordered frames; do not invent motion that is not visible.

Dimensions to score (each in [0.0, 1.0]):
{dim_block}

Output requirements (STRICT):
- Reply with a single JSON object and nothing else.
- Wrap it in a ```json ... ``` fenced block.
- Schema:
```json
{{
  "scores": {{ {schema_keys}: <float in [0.0, 1.0]> }},
  "rationale": {{ {schema_keys}: "<one short sentence citing frame evidence>" }},
  "notable_issues": ["<concrete observable defect, ideally referencing a frame index>", "..."]
}}
```
- `scores` and `rationale` MUST contain exactly the dimension keys listed
  above and no others.
- `notable_issues` enumerates concrete defects that drove any low score.
  It may be empty.

{safety_block()}
"""


def build_video_eval_input(
    brief_ctx: str,
    frame_urls: list[str],
    dimensions: list[str],
) -> ModelInput:
    """비디오 노드 평가용 ModelInput을 만든다.

    brief_ctx는 ``shared.format_brief.summarize_for_evaluator`` 결과여야 한다.
    ``frame_urls``는 비디오에서 샘플링한 프레임 URL의 시간 순 리스트.
    비어 있으면 ``image_urls=[]``로 처리한다(URL-only 평가).
    """
    if not dimensions:
        raise ValueError("dimensions must not be empty")

    system = _build_system_prompt(dimensions, n_frames=len(frame_urls))
    if frame_urls:
        evidence_line = f"{len(frame_urls)} sampled frame(s) are attached in temporal order."
    else:
        evidence_line = (
            "No frames are attached. Score under the constraints noted in the system prompt."
        )
    user_prompt = (
        f"{brief_ctx}\n\n"
        f"{evidence_line}\n"
        "Score every listed dimension and produce the JSON object as specified."
    )
    return ModelInput(
        model_id=EVALUATOR_MODEL,
        prompt=user_prompt,
        system=system,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        image_urls=list(frame_urls),
    )
