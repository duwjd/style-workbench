# CLAUDE.md — External Model Adapters

> 이 디렉토리에서 작업할 때 가장 중요한 본능은 **"새 어댑터를 만들지 않는 것"**이다. 어댑터는 3개(Claude/OpenAI/Replicate)로 고정되어 있고, 이 3개 외 vendor를 추가하는 결정은 **ADR이 필요한 큰 변경**이다.

루트 `CLAUDE.md` §5 "외부 SDK 직접 호출 금지"를 가능하게 하는 곳이 여기다. 어댑터 인터페이스가 깔끔하지 않으면 services에서 우회하고 싶어진다.

---

## 1. 작업 범위

- **포함**: `adapters/base.py`, `adapters/claude.py`, `adapters/openai.py`, `adapters/replicate.py`, `adapters/registry.py`, `core/pricing.py`, `model_profiles` 시드(Alembic data migration), `tests/unit/adapters/`
- **제외**: 어댑터를 호출하는 services 코드 (`backend/CLAUDE.md`), prompt 자체 (`prompts/CLAUDE.md`)

---

## 2. 절대 규칙

1. **어댑터는 3개로 고정**: Claude / OpenAI / Replicate. 새 vendor 클래스 추가는 ADR 동의 없이 금지.
2. **단일 인터페이스 `ModelAdapter`**: `call(model_id: str, input: ModelInput) -> ModelOutput`. vendor별 차이는 어댑터 내부에서 흡수.
3. **모든 외부 호출에 retry + timeout + 비용 측정**: 응답 메타에 `usage`(input_tokens, output_tokens 또는 prediction_seconds)와 `cost_won`을 포함.
4. **응답 원문은 hash/요약만 로그**. 원문 저장은 `infra/storage/`로 위임.
5. **pricing.py 동기화**: 새 모델 추가 시 단가 누락하면 비용 계산이 0원으로 통과돼 가드레일이 무력화. 모델 등록과 단가 등록은 **같은 PR**.
6. **어댑터에서 budget 체크 금지**: 누적 비용은 `services/run_service.py`가 관리한다 (레이어 침범 금지).

---

## 3. 의사결정 트리 — 새 모델 요청이 들어왔을 때

이 순서로 판단한다. **대부분 (a)에서 끝난다.**

### (a) 이미지/영상 모델인가?
→ **99% Replicate로 처리.** `model_profiles` 시드 한 줄 + `pricing.py` 한 줄. **어댑터 코드 손대지 않음.**
- `provider="replicate"`, `replicate_model_id="<owner>/<model>"`
- Replicate에 없는 모델이면 → 정말 vendor 추가가 필요한지 사용자에게 확인. API 직접 호출이 가능한지 검토.

### (b) 텍스트 모델인가? (gpt 외)
- OpenAI 호환 API(chat completions 인터페이스 동일)인가?
  → OpenAIAdapter 그대로 쓰고 `provider="openai"`, base_url만 환경변수로 분기.
- 호환 안 됨 → vendor 추가 ADR 필요.

### (c) Claude 신모델인가?
- model_id만 추가, ClaudeAdapter는 보통 그대로.
- input/output 형식이 바뀌었으면(예: tool use 변경) ClaudeAdapter 본체 수정 + 단위 테스트 갱신.

### (d) 완전히 새로운 vendor인가?
**멈춰서 사용자에게 ADR 작성을 제안.** 어댑터 추가는 의존성/유지보수 비용 증가가 크다.

ADR 합의 후에만 다음 절차:
1. `adapters/<vendor>.py`에 `ModelAdapter` 상속 클래스
2. `adapters/registry.py`에 `provider → 클래스` 매핑
3. `tests/unit/adapters/test_<vendor>.py` (HTTP mock — `respx` 또는 `pytest-httpx`)
4. 의존성 추가는 `uv add <pkg>`

---

## 4. 모델 추가 표준 절차 (가장 흔한 케이스)

### 4.1 Replicate 모델 추가 (예: 새 영상 모델 `acme/superrealism-v2`)

**1) `model_profiles` 시드 (Alembic data migration):**
```python
{
  "id": "superrealism_v2",
  "provider": "replicate",
  "replicate_model_id": "acme/superrealism-v2",
  "type": "video",        # video | image | text
  "display_name": "SuperRealism v2",
  "input_schema": {...},  # 동적 폼 필드
  "default_params": {"duration": 5, "fps": 24},
}
```

**2) `core/pricing.py`:**
```python
PRICING["superrealism_v2"] = PricingRule(
    provider="replicate",
    unit="second",
    won_per_unit=Decimal("180"),  # 1초당 ₩180
    min_charge_won=Decimal("0"),
    # 출처: https://replicate.com/acme/superrealism-v2 (2026-04-28 확인)
)
```

**3) (선택) FE의 ModelPicker 라벨/아이콘** → frontend-engineer에게 위임.

**4) 테스트**: 시드 로딩 검증 + pricing 계산 unit test 1개. ReplicateAdapter는 손대지 않음.

### 4.2 ClaudeAdapter 신모델 (예: claude-haiku-4-5)
1. `core/pricing.py`에 input/output 단가 추가
2. ClaudeAdapter는 그대로 — `model_id`만 호출 시점에 전달
3. golden 회귀는 prompt-engineer 영역(필요 시 위임)

---

## 5. ModelAdapter 인터페이스 표준 (변경 자제)

```python
# adapters/base.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any
from pydantic import BaseModel

class ModelInput(BaseModel):
    prompt: str | None = None
    messages: list[Message] | None = None     # chat 형식
    images: list[ImageRef] | None = None      # vision 입력
    params: dict[str, Any] = {}               # vendor 특화 (temperature, top_p 등)

class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    prediction_seconds: float | None = None   # Replicate

class ModelOutput(BaseModel):
    content: str
    raw: dict[str, Any]                       # vendor 원본 (디버그용)
    usage: Usage
    cost_won: Decimal
    finish_reason: str | None = None

class ModelAdapter(ABC):
    @abstractmethod
    async def call(self, model_id: str, input: ModelInput) -> ModelOutput: ...
```

이 인터페이스를 변경하면 services 전체에 영향이 간다. 변경 전:
1. `rg "ModelAdapter|ModelInput|ModelOutput" backend/src/style_workbench` 영향 범위 확인
2. backend-engineer와 협의
3. 마이그레이션 단계 분리 (deprecation → 신규 적용)

---

## 6. 안정성 패턴

### Retry
- 5xx, 429, 네트워크 에러 → 지수 백오프 3회 (예: 1s, 2s, 4s + jitter).
- 4xx (401, 400) → 즉시 실패. 재시도 무의미.
- Replicate `Idempotency-Key` 헤더로 재시도 시 중복 prediction 방지.

### Timeout
- 텍스트: 30s
- 이미지: 5min
- 비디오: 15min
- model_profiles의 `default_timeout_s` 필드로 override 가능.

### Polling vs Streaming
- **Replicate**: polling 1s 간격 (exponential 최대 5s).
- **Claude**: `messages.stream`으로 streaming 가능 — Variant Generator UX 개선에 유용.
- **OpenAI**: streaming 가능, 텍스트 단계에서 활용.

### 비용 측정
- 어댑터는 **자기 호출의 cost만** 반환.
- 누적 budget 체크는 `services/run_service.py`가 담당.
- pricing.py의 단가 출처(공식 단가표 URL)를 코드 코멘트에.

---

## 7. 자주 하는 실수

| 실수 | 결과 | 올바른 방식 |
|---|---|---|
| services에서 `import replicate` 직접 사용 | 레이어 침범 + 테스트 불가 | `adapters/replicate.py` 통과 |
| 새 vendor마다 어댑터 추가 | 어댑터 폭증, 유지비 증가 | Replicate 게이트웨이 통합 |
| `pricing.py` 누락한 채 모델 등록 | 비용 0원으로 가드레일 우회 | 같은 PR에서 등록 |
| 어댑터에서 budget 체크 | 레이어 침범, 테스트 어려움 | `services/run_service.py` |
| HTTP mock 없이 통합 테스트만 | vendor 다운 시 CI 깨짐 | unit은 mock, integration은 별도 마커 |
| 응답 raw를 그대로 `logger.info` | PII 누출 위험 | hash/요약만 |

---

## 8. 작업 종료 체크리스트

- [ ] 새 어댑터 클래스를 추가하지 않았다 (또는 ADR 동의 받음)
- [ ] `model_profiles` 시드와 `pricing.py` 등록이 같은 PR에 있다
- [ ] pricing.py 단가에 출처 코멘트 포함
- [ ] HTTP mock 단위 테스트 추가 (있던 경우 갱신)
- [ ] retry/timeout/cost 메타가 응답에 포함되는지 확인
- [ ] services/api에서 vendor SDK 직접 import 0건 (`rg "from (anthropic|openai|replicate) import" backend/src/style_workbench/{api,services}`)
- [ ] 출력 보고서: 변경 파일 / 단가 / 어댑터 영향 / 후속 필요(frontend ModelPicker)
