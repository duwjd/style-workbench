from __future__ import annotations

from dataclasses import dataclass

# automation/retry_modifiers.md 기반 modifier 사전.
# 실패한 차원 이름을 키로, 원본 prompt 끝에 append할 문구를 값으로 가진다.
MAX_RETRIES: int = 3

RETRY_MODIFIERS: dict[str, str] = {
    # --- image / pre-eval dimensions ---
    "text_absence": (
        "CRITICAL: Absolutely NO text, NO watermark, NO logo, NO letters, "
        "NO numbers anywhere in the image."
    ),
    "resolution_quality": (
        "Output must be high resolution, sharp details, no blur, no noise, "
        "no compression artifacts."
    ),
    "composition": (
        "Center the main subject. Follow rule of thirds. Leave appropriate margins on all sides."
    ),
    "face_natural": (
        "CRITICAL: The face must look completely natural. No distortion, "
        "no asymmetry, no uncanny valley effect. Eyes, nose, mouth must be "
        "anatomically correct and proportional."
    ),
    "skin_tone": (
        "Skin tone must be natural and realistic. No over-smoothing, no plastic "
        "look, no unnatural color cast on skin areas."
    ),
    "identity_match": (
        "CRITICAL: The person's face and the object's design must be EXACTLY "
        "preserved from the reference images. Zero modifications, zero artistic "
        "interpretation."
    ),
    "scale_natural": (
        "The object size must be physically realistic relative to the person. "
        "Reference real-world proportions exactly."
    ),
    "lighting_match": (
        "IMPORTANT: Both the person and the object must share the SAME lighting "
        "direction and color temperature. Single light source assumption."
    ),
    "shadow_consistent": (
        "All shadows in the scene must point in the same direction. The object's "
        "shadow must be consistent with the person's shadow in angle, softness, "
        "and darkness."
    ),
    "seam_clean": (
        "CRITICAL: The boundary between the person and the composited object must "
        "be COMPLETELY invisible. No edge artifacts, no halo, no color bleeding "
        "at boundaries."
    ),
    "object_preserved": (
        "CRITICAL: The object must remain EXACTLY as the original — same shape, "
        "same color, same texture, same design details."
    ),
    "effect_physics": (
        "The effect must obey physics: fire casts warm light and upward shadows, "
        "water creates reflections and caustics."
    ),
    "effect_intensity": (
        "Adjust the effect to be clearly visible but not overwhelming. "
        "The object must remain the focal point."
    ),
    "color_tone": (
        "This scene's color temperature must match the adjacent scenes exactly. "
        "Use the same white balance and color grading."
    ),
    # --- video / post-eval dimensions ---
    "motion_artifact": (
        "CRITICAL: Absolutely NO flickering, NO warping, NO glitching, NO morphing "
        "between frames. Every single frame must be clean and stable. "
        "Ultra-smooth motion only."
    ),
    "subject_preservation": (
        "The subject must remain EXACTLY the same shape in every frame. No morphing, "
        "no melting, no stretching, no shape changes of any kind."
    ),
    "motion_compliance": (
        "STRICTLY follow the specified motion only. No deviation from the requested "
        "camera movement whatsoever."
    ),
    "speed_consistency": (
        "Camera movement must maintain perfectly constant speed throughout. "
        "No acceleration, no deceleration, no pauses."
    ),
    "face_consistency": (
        "CRITICAL: The person's face must be IDENTICAL in every single frame. "
        "Zero change in facial features, zero morphing between expressions."
    ),
    "composite_seam": (
        "The composite boundary must remain completely invisible throughout ALL "
        "camera movement at ALL angles."
    ),
    "object_stability": (
        "The composited object must move as one rigid body with the person. "
        "No floating, no sliding, no drifting."
    ),
    "effect_continuity": (
        "The visual effect must be temporally consistent from first frame to last. "
        "No flickering, no sudden appearance or disappearance."
    ),
    # --- text dimensions ---
    "tone_match": (
        "Ensure the tone precisely matches the requested style. "
        "Adjust vocabulary and sentence structure accordingly."
    ),
    "length": (
        "Adjust the output to meet the target length requirement. "
        "Be concise or elaborate as specified."
    ),
    "forbidden_words": (
        "Remove all prohibited words and phrases. Check the entire output for compliance."
    ),
    # --- composition dimensions ---
    "consistency": (
        "Ensure all visual elements are consistent with each other "
        "in style, color, and perspective."
    ),
    "aesthetic_balance": (
        "Improve the visual balance. Ensure proper spacing, alignment, and weight distribution."
    ),
    "brief_match": (
        "Ensure the output precisely matches the brief requirements. "
        "Re-read the brief and align every element."
    ),
}


@dataclass
class RetryState:
    node_id: str
    attempt: int = 0


class RetryPolicy:
    @staticmethod
    def should_retry(state: RetryState) -> bool:
        """현재 시도 횟수가 MAX_RETRIES 미만이면 True."""
        return state.attempt < MAX_RETRIES

    @staticmethod
    def apply_modifiers(
        original_prompt: str,
        retry_guidance: str | None,
        failed_dims: list[str],
        state: RetryState,
    ) -> tuple[str, RetryState]:
        """실패한 차원별 modifier + retry_guidance를 원본 prompt 끝에 append.

        Args:
            original_prompt: 이전 시도에 사용한 prompt.
            retry_guidance:  EvaluationResult.retry_guidance (None 가능).
            failed_dims:     점수가 PASS_THRESHOLD 미만인 차원 이름 목록.
            state:           현재 RetryState.

        Returns:
            (새 prompt, attempt+1된 RetryState) 튜플.
        """
        parts: list[str] = []
        for dim in failed_dims:
            modifier = RETRY_MODIFIERS.get(dim)
            if modifier:
                parts.append(modifier)

        if retry_guidance:
            parts.append(retry_guidance)

        if parts:
            suffix = "\n".join(parts)
            new_prompt = f"{original_prompt}\n\n{suffix}"
        else:
            new_prompt = original_prompt

        return new_prompt, RetryState(node_id=state.node_id, attempt=state.attempt + 1)
