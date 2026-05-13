from __future__ import annotations

# price per 1M tokens in USD
# Sources:
#   Claude models: https://www.anthropic.com/pricing (confirmed 2026-04-29)
#   OpenAI models:  https://openai.com/api/pricing    (confirmed 2026-04-29)
_PRICES: dict[str, dict[str, float]] = {
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    # https://www.anthropic.com/pricing (2026-04-30 확인)
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.8, "output": 4.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    # https://openai.com/api/pricing (2026-05-08 확인)
    "gpt-5.4": {"input": 7.5, "output": 30.0},
}


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    prices = _PRICES.get(model_id, {"input": 0.0, "output": 0.0})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


# Flat per-prediction cost for Replicate models (USD).
# Sources: https://replicate.com (confirmed 2026-04-29)
_REPLICATE_PRICES: dict[str, float] = {
    "kuaishou/kling-v2.5-turbo-pro": 0.14,
    "bytedance/seedance-1.5-pro": 0.50,
    "runway/gen3": 0.40,
    "google/nano-banana-pro": 0.003,
}


def cost_usd_replicate(model_id: str) -> float:
    return _REPLICATE_PRICES.get(model_id, 0.0)


# Flat per-image cost for OpenAI image generation models (USD).
# Standard quality 1024x1024 baseline.
# Sources: https://openai.com/api/pricing (confirmed 2026-05-08)
_OPENAI_IMAGE_PRICES: dict[str, float] = {
    "gpt-image-1": 0.011,  # standard quality, 1024x1024
}


def cost_usd_openai_image(model_id: str) -> float:
    return _OPENAI_IMAGE_PRICES.get(model_id, 0.0)
