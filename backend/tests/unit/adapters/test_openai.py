from __future__ import annotations

import httpx
import openai
import pytest

from style_workbench.adapters.base import ModelInput
from style_workbench.adapters.openai import OpenAIAdapter


def _make_transport(body: dict[str, object]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def _fake_response(
    text: str = "Hello from OpenAI",
    in_tok: int = 10,
    out_tok: int = 5,
) -> dict[str, object]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": in_tok,
            "completion_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
        },
    }


@pytest.fixture
def adapter() -> OpenAIAdapter:
    transport = _make_transport(_fake_response("Hello from OpenAI", 10, 5))
    http_client = httpx.AsyncClient(transport=transport)
    client = openai.AsyncOpenAI(api_key="test-key", http_client=http_client)
    return OpenAIAdapter(client=client)


async def test_generate_returns_text(adapter: OpenAIAdapter) -> None:
    out = await adapter.generate(ModelInput(model_id="gpt-4o", prompt="Hi"))
    assert out.text == "Hello from OpenAI"


async def test_generate_token_counts(adapter: OpenAIAdapter) -> None:
    out = await adapter.generate(ModelInput(model_id="gpt-4o", prompt="Hi"))
    assert out.input_tokens == 10
    assert out.output_tokens == 5


async def test_generate_cost_usd(adapter: OpenAIAdapter) -> None:
    out = await adapter.generate(ModelInput(model_id="gpt-4o", prompt="Hi"))
    # gpt-4o: $2.5/M input, $10/M output
    expected = (10 * 2.5 + 5 * 10.0) / 1_000_000
    assert abs(out.cost_usd - expected) < 1e-10


def test_cost_estimate_positive() -> None:
    adapter = OpenAIAdapter.__new__(OpenAIAdapter)
    inp = ModelInput(model_id="gpt-4o", prompt="hello world test prompt")
    estimate = adapter.cost_estimate("gpt-4o", inp)
    assert estimate >= 0.0
