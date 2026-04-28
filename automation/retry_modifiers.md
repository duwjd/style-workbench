# 재시도 프롬프트 수정 라이브러리

FAIL 항목 → 프롬프트에 **추가**할 문구.
전체 프롬프트를 바꾸지 않습니다. 끝에 추가합니다.


## Pre-eval 실패 수정 문구

### text_absence FAIL
```
CRITICAL: Absolutely NO text, NO watermark, NO logo, NO letters, NO numbers anywhere in the image.
```

### resolution_quality FAIL
```
Output must be high resolution, sharp details, no blur, no noise, no compression artifacts.
```

### composition FAIL
```
Center the main subject. Follow rule of thirds. Leave appropriate margins on all sides.
```

### face_natural FAIL (Type A)
```
CRITICAL: The face must look completely natural. No distortion, no asymmetry, no uncanny valley effect. Eyes, nose, mouth must be anatomically correct and proportional.
```

### skin_tone FAIL (Type A)
```
Skin tone must be natural and realistic. No over-smoothing, no plastic look, no unnatural color cast on skin areas.
```

### identity_match FAIL (Type B)
```
CRITICAL: The person's face and the object's design must be EXACTLY preserved from the reference images. Zero modifications, zero artistic interpretation. This is a product photo, not creative art.
```

### scale_natural FAIL (Type B)
```
The object size must be physically realistic relative to the person. Reference real-world proportions exactly.
```

### lighting_match FAIL (Type B)
```
IMPORTANT: Both the person and the object must share the SAME lighting direction and color temperature. Single light source assumption. If the person has light from the left, the object must also have light from the left with identical intensity.
```

### shadow_consistent FAIL (Type B)
```
All shadows in the scene must point in the same direction. The object's shadow must be consistent with the person's shadow in angle, softness, and darkness.
```

### seam_clean FAIL (Type B)
```
CRITICAL: The boundary between the person and the composited object must be COMPLETELY invisible. No edge artifacts, no halo, no color bleeding at boundaries. Feather edges naturally to match surrounding texture.
```

### object_preserved FAIL (Type C)
```
CRITICAL: The object must remain EXACTLY as the original — same shape, same color, same texture, same design details. The effect surrounds the object but does NOT alter it in any way.
```

### effect_physics FAIL (Type C)
```
The effect must obey physics: fire casts warm light and upward shadows, water creates reflections and caustics, explosions have radial force. Light interactions between the effect and the object must be physically realistic.
```

### effect_intensity FAIL (Type C)
```
Adjust the effect to be clearly visible but not overwhelming. The object must remain the focal point. The effect enhances, not overpowers.
```

### color_tone FAIL (Type D)
```
This scene's color temperature must match the adjacent scenes exactly. Use the same white balance and color grading as the other scenes in this story.
```


## Post-eval 실패 수정 문구

### motion_artifact FAIL
```
CRITICAL: Absolutely NO flickering, NO warping, NO glitching, NO morphing between frames. Every single frame must be clean and stable. Ultra-smooth motion only.
```

### subject_preservation FAIL
```
The subject must remain EXACTLY the same shape in every frame. No morphing, no melting, no stretching, no shape changes of any kind throughout the entire video duration.
```

### motion_compliance FAIL
```
STRICTLY: {지시한 모션} ONLY. Absolutely NO {감지된 비허가 모션}. The camera must ONLY move along the specified axis with no deviation whatsoever.
```
예시: 줌인 지시인데 패닝 감지 →
```
STRICTLY: Zoom in ONLY. Absolutely NO panning, NO tilting, NO rotation. Forward motion on Z-axis only.
```

### speed_consistency FAIL
```
Camera movement must maintain perfectly constant speed throughout. No acceleration, no deceleration, no pauses. Smooth linear interpolation from start to end.
```

### face_consistency FAIL (Type A)
```
CRITICAL: The person's face must be IDENTICAL in every single frame. Zero change in facial features, zero morphing between expressions. Face identity must be pixel-level preserved.
```

### composite_seam FAIL (Type B)
```
The composite boundary must remain completely invisible throughout ALL camera movement at ALL angles. No seam, no edge, no boundary should ever be visible in any frame.
```

### object_stability FAIL (Type B)
```
The composited object must move as one rigid body with the person. No floating, no sliding, no drifting, no independent motion. The object is physically attached and moves only with the person's body.
```

### effect_continuity FAIL (Type C)
```
The visual effect must be temporally consistent from first frame to last. No flickering, no sudden appearance or disappearance. Smooth continuous effect throughout.
```


## 도구 전환 시 안내 문구

### 경량도구 → 나노바나나 전환
```
⚠️ 도구 전환 권고
현재 도구에서 {실패항목}이 2회 연속 FAIL.
나노바나나(Gemini)로 전환을 권장합니다.
나노바나나의 캐릭터 일관성 기능이 이 문제를 해결할 가능성이 높습니다.

[전환 시 주의] 프롬프트는 동일하게 유지하되,
나노바나나에서는 모든 참조 이미지를 함께 업로드하세요.
```

### 영상 모델 전환 (Seedance ↔ Kling)
```
⚠️ 모델 전환 권고
{현재모델}에서 {실패항목}이 2회 연속 FAIL.
{대안모델}로 전환을 권장합니다.

[전환 시 주의] 모션 프롬프트는 동일하게 유지합니다.
확정된 이미지도 동일하게 사용합니다.
모델만 변경합니다.
```
