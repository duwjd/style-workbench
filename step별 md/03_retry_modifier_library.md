# 3. 재시도 프롬프트 수정 라이브러리

Pre-eval 또는 Post-eval에서 FAIL이 나오면,
실패 항목에 해당하는 수정 문구를 원래 프롬프트에 **추가**합니다.
전체 프롬프트를 바꾸지 않습니다.


---

## Pre-eval 실패 시 프롬프트 추가 문구

### 공통

| 실패 항목 | 프롬프트에 추가할 문구 |
|-----------|----------------------|
| text_absence | `CRITICAL: Absolutely NO text, NO watermark, NO logo, NO letters, NO numbers anywhere in the image.` |
| resolution_quality | `Output must be high resolution, sharp details, no blur, no noise, no compression artifacts.` |
| composition | `Center the main subject. Follow rule of thirds. Leave appropriate margins.` |

### Type A (인물)

| 실패 항목 | 추가 문구 |
|-----------|----------|
| face_natural | `CRITICAL: The face must look completely natural. No distortion, no asymmetry, no uncanny valley effect. Eyes, nose, mouth must be anatomically correct.` |
| skin_tone | `Skin tone must be natural and realistic. No over-smoothing, no plastic look, no color cast on skin.` |
| background_clean | `Background must be clean and uncluttered. Remove any distracting elements. Smooth gradient or solid background preferred.` |

### Type B (합성)

| 실패 항목 | 추가 문구 |
|-----------|----------|
| identity_match | `CRITICAL: The person's face and the object's design must be EXACTLY preserved from the reference images. No modifications, no artistic interpretation.` |
| scale_natural | `The object size must be physically realistic relative to the person. Reference real-world proportions.` |
| lighting_match | `IMPORTANT: Both the person and the object must share the SAME lighting direction and color temperature. Single light source assumption. If the person has light from the left, the object must also have light from the left.` |
| shadow_consistent | `All shadows must point in the same direction. The shadow of the object must be consistent with the person's shadow.` |
| seam_clean | `CRITICAL: The boundary between the person and the composited object must be COMPLETELY invisible. No edge artifacts, no halo, no color bleeding at boundaries. Feather edges naturally.` |

### Type C (물건+효과)

| 실패 항목 | 추가 문구 |
|-----------|----------|
| object_preserved | `CRITICAL: The object must remain EXACTLY as the original — same shape, color, texture, design details. The effect surrounds the object but does NOT alter it.` |
| effect_physics | `The effect must obey basic physics: fire casts warm light and upward shadows, water creates reflections, explosions push outward. Light interactions between the effect and the object must be realistic.` |
| effect_intensity | `Adjust the effect intensity to be [stronger/weaker]. The effect should be [clearly visible but not overwhelming / more dramatic and prominent].` |

### Type D (스토리, 장면별)

| 실패 항목 | 추가 문구 |
|-----------|----------|
| color_tone (특정 장면) | `This scene's color temperature must match the adjacent scenes. Use warm/cool tone consistent with scene [N-1] and scene [N+1].` |


---

## Post-eval 실패 시 모션 프롬프트 추가 문구

### 공통

| 실패 항목 | 추가 문구 |
|-----------|----------|
| motion_artifact | `CRITICAL: Absolutely NO flickering, NO warping, NO glitching. Every frame must be clean and stable. Extremely smooth motion only.` |
| subject_preservation | `The subject must remain EXACTLY the same in every frame. No morphing, no melting, no shape changes throughout the entire video.` |
| motion_compliance | `STRICTLY: [지시한 모션] ONLY. Absolutely no [감지된 비허가 모션]. The camera must ONLY move in the specified axis.` |
| speed_consistency | `Camera movement must maintain constant speed throughout. No sudden acceleration or deceleration. Smooth linear motion.` |

### Type A

| 실패 항목 | 추가 문구 |
|-----------|----------|
| face_consistency | `CRITICAL: The person's face must be IDENTICAL in every single frame. No change in facial features, no morphing between expressions. Face identity must be perfectly preserved.` |

### Type B

| 실패 항목 | 추가 문구 |
|-----------|----------|
| composite_seam | `The composite boundary must remain invisible throughout all camera movement. No seam reveal at any angle or frame.` |
| object_stability | `The composited object must move naturally WITH the person. No floating, no sliding, no independent drift. Object is physically attached.` |

### Type C

| 실패 항목 | 추가 문구 |
|-----------|----------|
| effect_continuity | `The visual effect must be consistent from first frame to last. No sudden appearance or disappearance. Smooth continuous effect.` |
| object_motion_integrity | `The object must NOT deform inside the effect. Maintain exact original shape in every frame regardless of surrounding effects.` |


---

## 도구/모델 전환 판단 기준

아래 조건 중 하나라도 해당하면, 같은 도구/모델로 재시도하지 말고 전환합니다.

### 이미지 도구 전환 (경량도구 → 나노바나나)
- identity_match가 2회 연속 FAIL
- seam_clean이 2회 연속 FAIL
- 평가자가 "합성 품질의 근본적 한계"를 지적한 경우

### 이미지 도구 전환 (나노바나나 → 경량도구)
- 단순 보정만 필요한데 나노바나나가 과도하게 변형하는 경우
- 원본 충실도(identity_match)가 오히려 나노바나나에서 더 낮은 경우

### 영상 모델 전환 (Seedance ↔ Kling)
- motion_artifact가 2회 연속 FAIL
- face_consistency가 해당 모델에서 지속적으로 FAIL
- 평가자의 model_switch_recommended가 true인 경우

전환 후에도 재시도 횟수는 리셋하지 않습니다.
총 재시도 한도(Pre 3회 + Post 3회)를 초과하면 최선 결과물 + 실패 로그를 반환합니다.
