# 4. 운영 플로우 SOP (Standard Operating Procedure)

## 준비물

| 도구 | 용도 | 비고 |
|------|------|------|
| Claude 대화창 #1 | Master Controller | 시스템 프롬프트: 01_master_controller.md |
| Claude 대화창 #2 | Evaluator (검수관) | 시스템 프롬프트: 02_evaluator_prompts.md |
| 나노바나나 / Gemini | 이미지 합성 (Type B/D) | https://aistudio.google.com 또는 nano-banana.ai |
| Seedance / Kling | 영상 생성 | 각 서비스 대시보드 |
| ffmpeg (로컬) | 프레임 추출 / 스티칭 | Type D에서 필요 |

핵심 원칙: Controller와 Evaluator는 반드시 별도 대화창에서 운영합니다.
같은 AI가 지시하고 평가하면 자기 확증 편향이 발생합니다.


---

## 실행 플로우

```
┌──────────────────────────────────────────────────────┐
│  운영자: 이미지 + 의도를 Controller에 입력            │
│         ↓                                            │
│  Controller: 유형 분류 + 프롬프트 생성                │
│         ↓                                            │
│  운영자: 생성된 프롬프트로 이미지 도구 실행            │
│         ↓                                            │
│  운영자: 결과 이미지를 Evaluator에 입력               │
│         ↓                                            │
│  Evaluator: PASS / FAIL 판정                         │
│         ↓                                            │
│     PASS → 모션 프롬프트로 영상 생성                  │
│     FAIL → 수정 문구 추가 후 이미지 도구 재실행       │
│         ↓                                            │
│  운영자: 영상 프레임 추출 → Evaluator에 입력          │
│         ↓                                            │
│  Evaluator: PASS / FAIL 판정                         │
│         ↓                                            │
│     PASS → 완료                                      │
│     FAIL → 모션 프롬프트 수정 후 영상 재생성          │
└──────────────────────────────────────────────────────┘
```


---

## 단계별 상세


### STEP 1. 입력 접수 (Controller)

```
[작업] Claude 대화창 #1에서:

1. 이미지 첨부 (1장~N장)
2. 의도 설명 입력

예시:
"이 사람이 이 시계를 차고 있는 광고 영상을 만들어주세요. 
 고급스럽고 드라마틱한 조명으로요."
(인물 사진 + 시계 사진 첨부)
```

Controller 출력물:
- 유형 판정 (Type B)
- 이미지 분석 결과
- Pre-processing 프롬프트
- 모션 프롬프트
- 평가 체크리스트


### STEP 2. 이미지 생성 (운영자 → 이미지 도구)

```
[작업] Controller가 출력한 Pre-processing 프롬프트를 해당 도구에 입력

도구 선택:
- Type A → 이미지 보정 도구 (또는 나노바나나)
- Type B → 나노바나나 (인물 + 물건 사진 함께 업로드)
- Type C → 나노바나나 또는 배경제거 → 합성
- Type D → 나노바나나 (장면별 개별 실행)

나노바나나 사용 시:
1. Google AI Studio 또는 nano-banana.ai 접속
2. 이미지 업로드
3. Controller가 생성한 [SUBJECT]~[CONSTRAINT] 프롬프트 입력
4. 결과 이미지 다운로드
```


### STEP 3. Pre-eval (Evaluator)

```
[작업] Claude 대화창 #2에서:

1. 결과 이미지 첨부
2. 원본 참조 이미지 첨부 (있으면)
3. 다음 정보 입력:
   - 유형: Type X
   - 적용된 프롬프트: (STEP 2에서 사용한 프롬프트 복붙)

Evaluator가 JSON으로 판정 결과 출력
```

**PASS인 경우** → STEP 4로

**FAIL인 경우:**

```
1. Evaluator의 retry_guidance 확인
2. 03_retry_modifier_library.md에서 해당 실패 항목의 수정 문구 찾기
3. 원래 프롬프트 끝에 수정 문구 추가
4. STEP 2 재실행 (수정된 프롬프트로)

최대 3회 반복.
3회째에는 도구 전환 고려 (라이브러리의 전환 판단 기준 참조).
```


### STEP 4. 영상 생성 (운영자 → 영상 모델)

```
[작업] Controller가 출력한 모션 프롬프트로 영상 생성

1. Seedance 또는 Kling 접속
2. STEP 3에서 통과한 이미지를 업로드
3. 모션 프롬프트 입력
   
   주의: 색감/조명/구도 설명은 넣지 않음. 모션만.

4. 영상 생성 대기 → 결과 다운로드
```


### STEP 5. 프레임 추출 (운영자, 로컬)

```
[작업] ffmpeg으로 3개 프레임 추출

ffmpeg -i output.mp4 -vf "select='eq(n\,0)'" -vframes 1 frame_first.png
ffmpeg -i output.mp4 -vf "select='eq(n\,60)'" -vframes 1 frame_mid.png  
ffmpeg -i output.mp4 -sseof -0.1 -vframes 1 frame_last.png

또는 간편 방법:
- 영상 재생기에서 첫/중간/마지막 지점에서 스크린샷
```


### STEP 6. Post-eval (Evaluator)

```
[작업] Claude 대화창 #2에서:

1. 3개 프레임 이미지 첨부 (첫/중간/마지막 순서대로)
2. 다음 정보 입력:
   - 유형: Type X
   - 적용된 모션 프롬프트: (STEP 4에서 사용한 프롬프트 복붙)

Evaluator가 JSON으로 판정 결과 출력
```

**PASS인 경우:**
- Type A/B/C → 완료
- Type D → STEP 7 (스티칭)

**FAIL인 경우:**

```
1. Evaluator의 retry_guidance 확인
2. 수정 문구를 모션 프롬프트에 추가
3. STEP 4 재실행 (이미지는 그대로, 모션 프롬프트만 수정)

최대 3회 반복.
2회 연속 같은 항목 FAIL이면 영상 모델 전환.
```


### STEP 7. 스티칭 (Type D 전용)

```
[작업] 모든 장면 영상이 Post-eval 통과 후:

1. ffmpeg으로 연결:
   ffmpeg -f concat -safe 0 -i filelist.txt -c copy final.mp4

   filelist.txt:
   file 'scene_01.mp4'
   file 'scene_02.mp4'
   file 'scene_03.mp4'

2. 트랜지션이 필요하면:
   ffmpeg -i scene_01.mp4 -i scene_02.mp4 \
     -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=4.5" \
     output.mp4

3. 최종 영상을 Evaluator에서 cross-scene 평가
   → 02_evaluator_prompts.md의 "2-3. Cross-scene 평가 프롬프트" 사용
```


---

## 기록 템플릿

매 작업 완료 후 아래 항목을 기록합니다 (스프레드시트 권장).

| 항목 | 기록값 |
|------|--------|
| 날짜 | |
| 요청 ID | |
| 유형 | Type A / B / C / D |
| 이미지 도구 | 나노바나나 / 배경제거 / 보정 |
| 영상 모델 | Seedance / Kling |
| Pre-eval 시도 횟수 | |
| Pre-eval 실패 항목 | |
| Post-eval 시도 횟수 | |
| Post-eval 실패 항목 | |
| 도구 전환 여부 | Y/N, 전환 내용 |
| 총 API 호출 수 | |
| 추정 비용 (원) | |
| 최종 결과 | 성공 / 실패 |
| 비고 | 특이사항, 프롬프트 개선 아이디어 |

이 데이터가 축적되면:
- 유형별 평균 재시도 횟수 → 프롬프트 품질 지표
- 실패 항목 빈도 → 프롬프트 개선 우선순위
- 도구/모델별 통과율 → 최적 조합 도출
- 건당 비용 추이 → COGS 산출 근거
