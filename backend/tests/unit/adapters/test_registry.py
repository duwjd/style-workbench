from __future__ import annotations

import pytest

from style_workbench.adapters import registry as reg
from style_workbench.adapters.base import ModelAdapter, ModelInput, ModelOutput


class _FakeAdapter(ModelAdapter):
    async def generate(self, input: ModelInput) -> ModelOutput:
        return ModelOutput(text="ok", input_tokens=1, output_tokens=1, cost_usd=0.0)

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        return 0.0


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    reg.clear_registry()
    yield
    reg.clear_registry()


def test_register_and_get() -> None:
    reg.register("fake", _FakeAdapter())
    adapter = reg.get_adapter("fake")
    assert isinstance(adapter, _FakeAdapter)


def test_get_unknown_provider_raises() -> None:
    # Pre-populate with a fake adapter so lazy init (which requires API keys)
    # is not triggered when the registry is empty.
    reg.register("other", _FakeAdapter())
    with pytest.raises(KeyError, match="fake_unknown"):
        reg.get_adapter("fake_unknown")


def test_default_registry_has_anthropic_and_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    from style_workbench.adapters.claude import ClaudeAdapter
    from style_workbench.adapters.openai import OpenAIAdapter

    # SDK clients read API keys from env at construction time — provide stubs.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    assert isinstance(reg.get_adapter("anthropic"), ClaudeAdapter)
    assert isinstance(reg.get_adapter("openai"), OpenAIAdapter)
