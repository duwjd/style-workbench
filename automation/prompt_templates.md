# 유형별 프롬프트 템플릿

## Type A (인물)

### Pre-processing 프롬프트 템플릿
```
[SUBJECT] {피사체 분석 결과 — 성별, 연령대, 포즈, 표정}
[ENVIRONMENT] {사용자 의도에 맞는 배경 — 미지정 시 "clean gradient background"}
[PALETTE] {사용자 지정 또는 "natural tones, warm color temperature"}
[LIGHTING] {이미지 분석에서 감지된 조명 방향 유지 또는 사용자 지정}
[CONSTRAINT] No text, no watermark, no logo. Preserve exact facial features.
[TOOL_NOTE] 보정 도구 사용 시: 과도한 보정 금지, 자연스러운 피부 유지
```

### 모션 프롬프트 템플릿
```
Slow gentle {zoom_in / tilt / pan} toward the face.
Keep the person centered throughout.
Smooth constant speed, no abrupt changes.
No {금지 모션 나열}.
Static background, no object movement.
```

---

## Type B (합성)

### Pre-processing 프롬프트 템플릿

나노바나나용:
```
[SUBJECT] Combine the person from Image 1 with the {물건명} from Image 2.
The person should be {interacting with / holding / wearing} the {물건명}.
[ENVIRONMENT] {사용자 의도에 맞는 환경}
[PALETTE] {사용자 지정 또는 이미지 분석 기반}
[LIGHTING] Match lighting direction between the person and the object.
Single light source from {분석된 조명 방향}.
Both elements must share the same color temperature.
[CONSTRAINT] EXACT preservation of person's face and object's design.
No text, no watermark.
Natural shadows where the object meets the person.
[TOOL_NOTE] 나노바나나: 두 이미지를 모두 업로드. 캐릭터 일관성 유지 강조.
```

### 모션 프롬프트 템플릿
```
Slow smooth camera movement that gradually reveals
the {물건명} the person is {holding/wearing}.
Keep both the person and the {물건명} in frame throughout.
No fast movements. Static scene, no object animation.
No {금지 모션 나열}.
```

---

## Type C (물건 + 효과)

### 효과별 환경 지시

| 효과 | 환경 프롬프트 추가 |
|------|-------------------|
| 폭발/explosion | dramatic explosion behind the object, debris flying outward, warm orange-red backlight |
| 불/fire | flames engulfing the surroundings, warm flickering light cast on object surface |
| 물/water | submerged in clear water, light caustics on object surface, subtle bubbles |
| 연기/smoke | dense atmospheric smoke surrounding the object, volumetric light rays |
| 반짝/sparkle | magical sparkle particles surrounding the object, point light reflections |

### Pre-processing 프롬프트 템플릿
```
[SUBJECT] {물건 설명} — must remain EXACTLY as original
[ENVIRONMENT] {효과별 환경 지시 삽입}
[PALETTE] {효과에 맞는 색감}
[LIGHTING] {효과에 의한 조명 변화 — 불이면 warm cast, 물이면 caustics}
[CONSTRAINT] Object shape/color/design must NOT change.
Effect interacts with object physically (shadows, reflections, light).
No text, no watermark.
[TOOL_NOTE] 물건 형태 보존이 핵심. 효과가 물건을 삼키지 않도록.
```

### 효과별 모션 프롬프트

| 효과 | 모션 |
|------|------|
| 폭발 | Quick zoom out to reveal full explosion, then slow settle. Dynamic camera shake optional. |
| 불 | Slow upward tilt following flames. Warm color intensifies. |
| 물 | Gentle ripple-like camera sway. Smooth horizontal drift. |
| 연기 | Slow zoom in through smoke. Gradual reveal of object. |
| 반짝 | Slow orbit around object. Catching light reflections. |
| 기본 | Slow smooth zoom in, center focus on object. |

---

## Type D (스토리)

### 스토리보드 구성 규칙

1. 장면 순서: 사용자 지정 우선. 미지정 시 업로드 순서.
2. 장면별 역할 할당:
   - 첫 장면: 도입 (establishing shot, 여유로운 페이스)
   - 중간 장면: 전개 (다양한 모션으로 변화)
   - 마지막 장면: 마무리 (점진적 감속)
3. 인접 장면 모션 충돌 방지:
   - 연속 줌인 금지 → 줌인 다음은 패닝 또는 틸트
   - 연속 같은 방향 패닝 금지

### 장면별 Pre-processing 프롬프트 (개별 적용)
```
[SUBJECT] Scene {N}: {장면 설명}
[ENVIRONMENT] {일관된 환경 톤 유지}
[PALETTE] {전체 스토리 톤에 맞춤 — 장면마다 동일}
[LIGHTING] {전체 일관 유지}
[CONSTRAINT] Color temperature must match other scenes in this story.
No text, no watermark.
[TOOL_NOTE] 동일 인물 등장 시: 나노바나나로 캐릭터 일관성 유지.
```

### 모션 순환 패턴 (단조로움 방지)
```
Scene 1: Slow zoom in, center focus (도입)
Scene 2: Gentle pan left to right (전개)
Scene 3: Slow tilt upward (전개)
Scene 4: Slight zoom out to reveal full scene (전환)
Scene 5+: 위 패턴 반복, 마지막 장면은 감속
```

### 트랜지션 유형
```
짝수→홀수: dissolve (0.5초)
홀수→짝수: cut
클라이맥스 전: wipe
```


---

## 확정 프리셋 예시

반복 사용되는 카테고리는 프리셋으로 저장합니다.

### 프리셋: jewelry_ad_v1

```
유형: Type C
이미지 도구: 나노바나나
영상 모델: Seedance

Pre-processing:
[SUBJECT] A high-end jewelry piece, exact match to reference image
[ENVIRONMENT] Centered inside an open-faced deep red velvet case
[PALETTE] Deep red, crimson, analogous warm tones only. No cool tones.
[LIGHTING] Single sharp pinpoint light from upper-right, dramatic highlights, deep shadows
[CONSTRAINT] No text, no typography, no watermark, no human elements
[TOOL_NOTE] 나노바나나에서 제품 형태 보존 최우선

Motion:
Slow smooth tilt from low angle to eye level.
Fixed pivot point. Center focus locked on the jewelry.
No zoom, no pan, no dolly movement.
Static scene — no object movement, case remains open.
```
