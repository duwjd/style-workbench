from __future__ import annotations

from typing import cast

import anthropic
from anthropic.types import ContentBlockParam, MessageParam, TextBlock

from style_workbench.adapters.base import ModelAdapter, ModelInput, ModelOutput
from style_workbench.core.pricing import cost_usd


class ClaudeAdapter(ModelAdapter):
    def __init__(self, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._client = client or anthropic.AsyncAnthropic()

    async def generate(self, input: ModelInput) -> ModelOutput:
        if input.image_urls:
            content: list[ContentBlockParam] = []
            for url in input.image_urls:
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "url", "url": url},
                    }
                )
            content.append({"type": "text", "text": input.prompt})
            messages: list[MessageParam] = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": input.prompt}]

        if input.system:
            msg = await self._client.messages.create(
                model=input.model_id,
                max_tokens=input.max_tokens,
                messages=messages,
                system=input.system,
            )
        else:
            msg = await self._client.messages.create(
                model=input.model_id,
                max_tokens=input.max_tokens,
                messages=messages,
            )

        text_block = cast(TextBlock, msg.content[0])
        in_tok = msg.usage.input_tokens
        out_tok = msg.usage.output_tokens
        return ModelOutput(
            text=text_block.text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd(input.model_id, in_tok, out_tok),
        )

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        estimated_output = input.max_tokens // 2
        estimated_input = len(input.prompt.split()) * 4 // 3
        return cost_usd(model_id, estimated_input, estimated_output)
