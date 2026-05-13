"""Unit tests for pricing.py

Verifies:
1. All 8 Phase-1 seed models have a pricing entry (no silent 0-cost gap).
2. Regression — existing model prices are unchanged.
3. cost_usd / cost_usd_replicate / cost_usd_openai_image return non-zero values.
"""

from __future__ import annotations

import pytest

from style_workbench.core.pricing import (
    _OPENAI_IMAGE_PRICES,
    _PRICES,
    _REPLICATE_PRICES,
    cost_usd,
    cost_usd_openai_image,
    cost_usd_replicate,
)

# ---------------------------------------------------------------------------
# Canonical model sets — must stay in sync with the Phase-1 seed migration
# (alembic/versions/c3a1f9b2e045_seed_model_profiles_phase1.py).
# ---------------------------------------------------------------------------
SEEDED_TEXT_MODEL_IDS: set[str] = {
    "gpt-5.4",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
}

SEEDED_REPLICATE_MODEL_IDS: set[str] = {
    "google/nano-banana-pro",
    "kuaishou/kling-v2.5-turbo-pro",
    "bytedance/seedance-1.5-pro",
    "runway/gen3",
}

SEEDED_OPENAI_IMAGE_MODEL_IDS: set[str] = {
    "gpt-image-1",
}

ALL_SEEDED_MODEL_IDS: set[str] = (
    SEEDED_TEXT_MODEL_IDS | SEEDED_REPLICATE_MODEL_IDS | SEEDED_OPENAI_IMAGE_MODEL_IDS
)


# ---------------------------------------------------------------------------
# 1. Coverage: every seeded model has a pricing entry
# ---------------------------------------------------------------------------


def test_all_seeded_text_models_have_price() -> None:
    """Phase-1 text/anthropic/openai models must not fall back to 0-cost."""
    missing = SEEDED_TEXT_MODEL_IDS - set(_PRICES)
    assert not missing, (
        f"Missing token pricing for text models: {missing}. Add them to _PRICES in core/pricing.py."
    )


def test_all_seeded_replicate_models_have_price() -> None:
    """Phase-1 Replicate models must not fall back to 0-cost."""
    missing = SEEDED_REPLICATE_MODEL_IDS - set(_REPLICATE_PRICES)
    assert not missing, (
        f"Missing flat pricing for Replicate models: {missing}. "
        "Add them to _REPLICATE_PRICES in core/pricing.py."
    )


def test_all_seeded_openai_image_models_have_price() -> None:
    """Phase-1 OpenAI image models must not fall back to 0-cost."""
    missing = SEEDED_OPENAI_IMAGE_MODEL_IDS - set(_OPENAI_IMAGE_PRICES)
    assert not missing, (
        f"Missing flat pricing for OpenAI image models: {missing}. "
        "Add them to _OPENAI_IMAGE_PRICES in core/pricing.py."
    )


def test_total_seeded_model_count() -> None:
    """Exactly 8 models seeded in Phase 1."""
    assert len(ALL_SEEDED_MODEL_IDS) == 8, (
        "Expected exactly 8 Phase-1 seed models. Update SEEDED_* sets if the migration changed."
    )


# ---------------------------------------------------------------------------
# 2. Regression — known prices must not drift
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_id, expected_input, expected_output",
    [
        ("claude-opus-4-6", 15.0, 75.0),
        ("claude-sonnet-4-6", 3.0, 15.0),
        ("claude-haiku-4-5-20251001", 0.8, 4.0),
        ("gpt-4o", 2.5, 10.0),
        ("gpt-4o-mini", 0.15, 0.6),
        ("gpt-4.1", 2.0, 8.0),
        ("gpt-5.4", 7.5, 30.0),
    ],
)
def test_token_price_regression(
    model_id: str, expected_input: float, expected_output: float
) -> None:
    prices = _PRICES[model_id]
    assert prices["input"] == expected_input, (
        f"{model_id} input price changed: expected {expected_input}"
    )
    assert prices["output"] == expected_output, (
        f"{model_id} output price changed: expected {expected_output}"
    )


@pytest.mark.parametrize(
    "model_id, expected_cost",
    [
        ("kuaishou/kling-v2.5-turbo-pro", 0.14),
        ("bytedance/seedance-1.5-pro", 0.50),
        ("runway/gen3", 0.40),
        ("google/nano-banana-pro", 0.003),
    ],
)
def test_replicate_price_regression(model_id: str, expected_cost: float) -> None:
    assert _REPLICATE_PRICES[model_id] == expected_cost, (
        f"{model_id} Replicate price changed: expected {expected_cost}"
    )


def test_openai_image_price_regression() -> None:
    assert _OPENAI_IMAGE_PRICES["gpt-image-1"] == 0.011, (
        "gpt-image-1 OpenAI image price changed: expected 0.011"
    )


# ---------------------------------------------------------------------------
# 3. cost_usd / cost_usd_replicate / cost_usd_openai_image return non-zero
# ---------------------------------------------------------------------------


def test_cost_usd_nonzero_for_known_model() -> None:
    result = cost_usd("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
    assert result > 0.0


def test_cost_usd_returns_zero_for_unknown_model() -> None:
    # Unknown model must not raise; it silently returns 0.0 (caller handles missing).
    result = cost_usd("unknown-model-xyz", input_tokens=1000, output_tokens=500)
    assert result == 0.0


def test_cost_usd_replicate_nonzero_for_known_model() -> None:
    result = cost_usd_replicate("kuaishou/kling-v2.5-turbo-pro")
    assert result > 0.0


def test_cost_usd_replicate_zero_for_unknown() -> None:
    result = cost_usd_replicate("unknown/model")
    assert result == 0.0


def test_cost_usd_openai_image_nonzero_for_known_model() -> None:
    result = cost_usd_openai_image("gpt-image-1")
    assert result > 0.0


def test_cost_usd_openai_image_zero_for_unknown() -> None:
    result = cost_usd_openai_image("unknown-img-model")
    assert result == 0.0


# ---------------------------------------------------------------------------
# 4. Guard: new model added to pricing must also appear in seeded sets
#    (prevents pricing.py and migration from drifting in future PRs)
# ---------------------------------------------------------------------------


def test_no_extra_pricing_entries_without_seed_update() -> None:
    """
    This test intentionally does NOT block adding new models to pricing.py.
    It prints a warning if a model is priced but not in the seed sets,
    which would indicate the migration needs an update.

    We raise only if the mismatch count exceeds a known acceptable threshold
    (models like claude-opus-4-7, gpt-4.1 exist in pricing for legacy/pre-seed reasons).
    """
    priced_text = set(_PRICES)
    priced_replicate = set(_REPLICATE_PRICES)
    priced_openai_image = set(_OPENAI_IMAGE_PRICES)

    all_priced = priced_text | priced_replicate | priced_openai_image

    # These models exist in pricing for backward compatibility but are NOT
    # Phase-1 seed targets. Allowed exceptions.
    known_legacy = {
        "claude-opus-4-7",  # earlier model, kept for existing runs
        "claude-haiku-4-5-20251001",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
    }

    unaccounted = all_priced - ALL_SEEDED_MODEL_IDS - known_legacy
    assert not unaccounted, (
        f"Models in pricing.py but not in Phase-1 seed sets or known_legacy: {unaccounted}. "
        "Either add them to the seed migration or add to known_legacy in this test."
    )
