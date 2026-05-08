from __future__ import annotations

import openai

from style_workbench.adapters.base import ModelAdapter, ModelInput, ModelOutput
from style_workbench.core.pricing import cost_usd


class OpenAIAdapter(ModelAdapter):
    def __init__(self, client: openai.AsyncOpenAI | None = None) -> None:
        self._client = client or openai.AsyncOpenAI()

    async def generate(self, input: ModelInput) -> ModelOutput:
        messages: list[dict[str, str]] = []
        if input.system:
            messages.append({"role": "system", "content": input.system})
        messages.append({"role": "user", "content": input.prompt})

        resp = await self._client.chat.completions.create(
            model=input.model_id,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=input.max_tokens,
            temperature=input.temperature,
        )
        choice = resp.choices[0]
        text = choice.message.content or ""
        in_tok = resp.usage.prompt_tokens  # type: ignore[union-attr]
        out_tok = resp.usage.completion_tokens  # type: ignore[union-attr]
        return ModelOutput(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd(input.model_id, in_tok, out_tok),
        )

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        estimated_output = input.max_tokens // 2
        estimated_input = len(input.prompt.split()) * 4 // 3
        return cost_usd(model_id, estimated_input, estimated_output)
