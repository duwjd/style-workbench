# CLAUDE.md — AI Prompts (Variant Generator / Step Evaluator)

> 이 디렉토리의 작업은 **모델 출력의 일관성과 신뢰도**에 직결된다. prompt 한 줄 잘못 쓰면 디자이너의 6시간이 24시간이 되거나, 운영에서 잘못된 Style이 승인된다. 보수적으로, 검증 가능한 방식으로만 작업한다.

루트 `CLAUDE.md` §5 절대 금지 사항이 여기서 가장 강하게 적용된다.

---

## 1. 자기확증편향 차단 — 4대 절대 규칙

이 4개는 **이 프로젝트의 존재 이유**다. 한 번이라도 깨지면 도구 자체의 신뢰가 무너진다.

1. **Variant Generator와 Step Evaluator는 같은 system prompt에 절대 섞지 않는다.** 같은 LLM 호출에 묶지도 않는다. 두 역할은 **별도 파일, 별도 호출, 별도 모델** (Sonnet vs Opus).
2. **Evaluator는 원본 prompt를 받지 않는다.** brief의 요약(목표, 톤, 핵심 키워드)만 받는다. "이 prompt의 의도대로 결과물이 나왔는가"가 아니라 **"이 결과물이 brief를 충족하는가"**를 평가한다. prompt 텍스트가 evaluator context에 새어 들어가면 자기 정당화 평가가 된다.
3. **통과/탈락 임계값 판정은 Python 코드.** Claude는 0.0~1.0 점수와 근거 텍스트만 산출한다. "PASS", "FAIL", "통과", "추천" 같은 판정 어휘를 evaluator가 직접 출력하지 않게 한다.
4. **Evaluator temperature는 0.0~0.2.** Variant Generator는 0.7~0.9 권장. 같은 입력에 평가가 흔들리면 신뢰가 무너진다.

---

## 2. Placeholder 보호 규칙

Style의 prompt에는 `{name}`, `{age}`, `{product}` 같은 변수가 들어간다. 운영 시 사용자 데이터로 치환된다.

- system prompt 안에서 LLM에게 `{...}`을 보여줄 때 모델이 임의로 치환/창작할 수 있다.
- prompt 모듈은 항상 다음 보호 문구를 포함한다:

```
사용자 prompt에는 `{변수명}` 형태의 placeholder가 포함될 수 있다.
너는 이 placeholder를 그대로 보존해야 하며, 절대 임의 값을 채워넣지 않는다.
치환은 후속 시스템이 담당한다.
```

- variant 생성 시 새 prompt에 placeholder를 만들 때 `{snake_case_name}` 형식만 허용.
- 실제 치환은 `domain/prompt/template.py`의 `safe_substitute(...)`로만. 직접 `.format()`/`.replace()` 금지.

---

## 3. 파일 구조

```
prompts/
├── variant_generator.py       # Sonnet system prompt + parser
├── evaluator_image.py         # Opus, image 단계
├── evaluator_video.py         # Opus, video 단계
├── evaluator_text.py          # Opus, text 단계
├── evaluator_composition.py   # Opus, composition 단계
└── shared/
    ├── format_brief.py        # brief → evaluator용 요약 변환 (원본 prompt 제거 보장)
    ├── output_schema.py       # JSON schema 강제용 Pydantic 모델
    └── safety.py              # placeholder 보호 문구 등 공통 안내
```

---

## 4. Variant Generator 작성 가이드

- 모델: `claude-sonnet-4-6`. **temperature 0.7~0.9.**
- 출력은 **반드시 JSON**, Pydantic schema로 검증. 자유 산문 금지.
- system prompt 구조 (이 순서로):
  1. 역할 선언 (디자이너의 Style 변주를 생성하는 어시스턴트)
  2. 입력 형식 (brief 구조)
  3. 출력 형식 (DAG schema — nodes, edges, variables)
  4. 제약 (placeholder 보호, 노드 타입 enum, 변수 참조 무결성)
  5. 좋은/나쁜 예시 1쌍
- **출력 JSON에 evaluator가 사용할 score 필드를 포함하지 않는다** (역할 분리).
- 변주 N개 요청 시 다양성 강제: "각 변주는 다른 카메라 무브, 다른 라이팅, 다른 무드를 가진다" 같은 명시적 다양성 제약 포함.

---

## 5. Evaluator 작성 가이드

각 노드 타입(image/video/text/composition)별로 별도 파일.

- 모델: `claude-opus-4-6` (Vision 필요). **temperature 0.0~0.2.**
- Input 구조 (반드시 이 순서):
  1. brief 요약 (`format_brief.summarize_for_evaluator`로 만든 것 — 원본 prompt 제거 보장)
  2. 평가 대상 미디어 (image/video URL 또는 텍스트)
  3. 평가 차원 정의 (`domain/evaluation/criteria.py`)
- Output 구조 (강제):
  ```json
  {
    "scores": { "<dimension>": 0.0~1.0, ... },
    "rationale": { "<dimension>": "한 문장 근거", ... },
    "notable_issues": ["..."]
  }
  ```
- "PASS", "FAIL", "통과", "추천" 같은 판정 어휘를 evaluator 출력에 포함하지 않는다.
- 평가 차원은 노드 타입별:
  - **image**: 구도 / 색감 / 주제일치 / 아티팩트
  - **video**: 모션 자연스러움 / 시간일관성 / 주제일치 / 아티팩트
  - **text**: 톤일치 / 길이 / 금칙어
  - **composition**: 일관성 / 미적 균형 / brief 일치

---

## 6. Golden 테스트 (필수!)

prompt를 한 줄이라도 바꾸면 회귀 테스트를 갱신한다.

### 절차
1. `tests/golden/<scope>/inputs/<case>.json` — 고정 입력
2. `tests/golden/<scope>/expected/<case>.json` — 기대 출력 스냅샷
3. `pytest -k golden` 실행 — 점수 차이 > ±0.05면 fail
4. **고의로 변경한 경우**: expected 파일 갱신 + PR 설명에 "변경 의도, 점수 변동 폭, 사람 검수 결과" 명시
5. **고의가 아닌데 fail**: prompt 변경을 되돌리거나, 출력 안정성 강화 (temperature, schema 강제, few-shot 추가) 후 재시도

### 튜닝 시 주의
- prompt **한 부분만** 변경 (여러 변경 동시 금지 — 변동 원인 식별 불가).
- baseline 점수 기록 → 변경 → 재측정 → 차이 분석.
- PR 설명에 baseline vs after 표 첨부.

---

## 7. 작업 순서

### 7.1 새 evaluator 추가 (예: audio 노드용)
1. `domain/evaluation/criteria.py`에 차원 enum 추가
2. `prompts/evaluator_audio.py` 작성 — §5 가이드대로
3. `prompts/shared/output_schema.py`에 `AudioEvalOutput` Pydantic 추가
4. `tests/golden/eval_audio/`에 입력 fixture 3~5개 + expected 스냅샷
5. `services/evaluation_service.py`에 dispatch 추가는 backend-engineer에게 위임

### 7.2 Variant Generator 출력 schema 변경
1. `shared/output_schema.py`의 Pydantic 모델 갱신
2. system prompt의 출력 형식 섹션과 schema가 1:1 일치 확인
3. golden fixture 모두 갱신
4. `domain/style/validation.py`에서 새 필드 검증은 backend-engineer 위임

---

## 8. 자주 하는 실수

| 실수 | 결과 | 올바른 방식 |
|---|---|---|
| Generator system prompt에 "잘 되었는지 평가도 같이 해줘" | 자기확증편향 | Evaluator 호출은 별도 단계 |
| Evaluator에 원본 prompt 그대로 전달 | 평가가 prompt를 변호함 | `format_brief.summarize_for_evaluator`로 prompt 제거 |
| Evaluator temperature 0.7 | 같은 입력에 점수 ±0.2 변동 | 0.0~0.2 |
| `{name}`이 evaluator 출력에 채워져서 등장 | 평가 객체에 임의 데이터 주입 | placeholder 보호 문구 + JSON schema validate |
| prompt 바꾸고 golden 갱신 안함 | 다음 PR에서 fail 폭탄 | 같은 PR에서 expected 갱신 + 변동 폭 명시 |
| evaluator가 "PASS"라고 직접 출력 | 임계값 변경 시 prompt도 바꿔야 함 | 점수만 출력, Python에서 비교 |
| few-shot 무한정 늘리기 | 비용/지연 증가, 다양성 감소 | 분산 측정 후 필요 최소만 |

---

## 9. 작업 종료 체크리스트

- [ ] Generator/Evaluator system prompt에 상호 참조 없음 (`rg "evaluat" prompts/variant_generator.py` 빈 결과)
- [ ] Evaluator input 구성에서 원본 prompt가 제거됨 (`format_brief` 단일 진입점 사용)
- [ ] Evaluator temperature ≤ 0.2 (`rg "temperature" prompts/evaluator_*.py` 확인)
- [ ] Evaluator 출력에 판정 어휘 없음 (`rg -i "pass|fail|통과|추천" prompts/evaluator_*.py` 결과 검토)
- [ ] Pydantic 출력 schema 강제 — 모든 응답이 `TypeAdapter.validate_python` 통과
- [ ] Golden 회귀: ±0.05 이내, 또는 의도된 변경 명시
- [ ] 출력 보고서: 변경 파일 / baseline-after 점수 / 분리 검증 / 후속 필요(backend)
