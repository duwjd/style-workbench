from __future__ import annotations

import json
import re

from pydantic import BaseModel, TypeAdapter, model_validator


class EvalOutput(BaseModel):
    scores: dict[str, float]  # dimension -> 0.0~1.0
    rationale: dict[str, str]  # dimension -> 한 문장
    notable_issues: list[str]

    @model_validator(mode="after")
    def scores_in_range(self) -> EvalOutput:
        for k, v in self.scores.items():
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"Score {k}={v} out of [0.0, 1.0]")
        return self


_adapter: TypeAdapter[EvalOutput] = TypeAdapter(EvalOutput)


def parse_eval_output(raw_text: str) -> EvalOutput:
    """LLM 응답 텍스트에서 JSON을 추출하고 EvalOutput으로 파싱."""
    # ```json ... ``` 코드블록 또는 bare JSON 모두 지원
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    json_str = match.group(1).strip() if match else raw_text.strip()
    data = json.loads(json_str)
    return _adapter.validate_python(data)
