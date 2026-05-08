from __future__ import annotations

import anthropic
import httpx
import pytest

from style_workbench.adapters.base import ModelInput
from style_workbench.adapters.claude import ClaudeAdapter


def _make_transport(body: dict[str, object]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def _fake_response(text: str = "Hello!", in_tok: int = 10, out_tok: int = 5) -> dict[str, object]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-4-6",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
    }


@pytest.fixture
def adapter() -> ClaudeAdapter:
    transport = _make_transport(_fake_response("Hello from Claude", 12, 6))
    http_client = httpx.AsyncClient(transport=transport)
    client = anthropic.AsyncAnthropic(api_key="test-key", http_client=http_client)
    return ClaudeAdapter(client=client)


async def test_generate_returns_text(adapter: ClaudeAdapter) -> None:
    out = await adapter.generate(ModelInput(model_id="claude-sonnet-4-6", prompt="Hi"))
    assert out.text == "Hello from Claude"


async def test_generate_token_counts(adapter: ClaudeAdapter) -> None:
    out = await adapter.generate(ModelInput(model_id="claude-sonnet-4-6", prompt="Hi"))
    assert out.input_tokens == 12
    assert out.output_tokens == 6


async def test_generate_cost_usd(adapter: ClaudeAdapter) -> None:
    out = await adapter.generate(ModelInput(model_id="claude-sonnet-4-6", prompt="Hi"))
    # claude-sonnet-4-6: $3/M input, $15/M output
    # cost = (12*3 + 6*15) / 1_000_000
    expected = (12 * 3 + 6 * 15) / 1_000_000
    assert abs(out.cost_usd - expected) < 1e-10


def test_cost_estimate_positive() -> None:
    adapter = ClaudeAdapter.__new__(ClaudeAdapter)
    inp = ModelInput(model_id="claude-sonnet-4-6", prompt="hello world test prompt")
    estimate = adapter.cost_estimate("claude-sonnet-4-6", inp)
    assert estimate >= 0.0
