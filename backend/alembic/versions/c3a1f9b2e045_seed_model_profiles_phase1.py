"""seed model profiles phase1

Revision ID: c3a1f9b2e045
Revises: 8c488e4c8daa
Create Date: 2026-05-08 00:00:00.000000

"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3a1f9b2e045"
down_revision: str | None = "8c488e4c8daa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed ULIDs — must not change across re-runs (idempotency).
# Generated once via: uv run python -c "from ulid import ULID; print(ULID())"
_SEED_TAG = "seed_phase1"

_MODELS: list[dict] = [
    # ------------------------------------------------------------------ text
    {
        "id": "01KR2NMPM787769BR68CWNYDDF",
        "name": "GPT-5.4",
        "type": "text",
        "provider": "openai",
        "profile": json.dumps(
            {
                "model_id": "gpt-5.4",
                # Source: https://openai.com/api/pricing (2026-05-08 확인)
                "context_window": 128000,
                "max_output_tokens": 16384,
                "supports_vision": False,
                "supports_streaming": True,
                "pricing_unit": "tokens",
                "input_price_per_1m_usd": 7.5,
                "output_price_per_1m_usd": 30.0,
            }
        ),
        "imported_from": _SEED_TAG,
    },
    {
        "id": "01KR2NMPM787769BR68CWNYDDG",
        "name": "Claude Sonnet 4.6",
        "type": "text",
        "provider": "anthropic",
        "profile": json.dumps(
            {
                "model_id": "claude-sonnet-4-6",
                # Source: https://www.anthropic.com/pricing (2026-04-29 확인)
                "context_window": 200000,
                "max_output_tokens": 8192,
                "supports_vision": False,
                "supports_streaming": True,
                "role": "variant_generator",
                "pricing_unit": "tokens",
                "input_price_per_1m_usd": 3.0,
                "output_price_per_1m_usd": 15.0,
            }
        ),
        "imported_from": _SEED_TAG,
    },
    {
        "id": "01KR2NMPM787769BR68CWNYDDH",
        "name": "Claude Opus 4.6",
        "type": "text",
        "provider": "anthropic",
        "profile": json.dumps(
            {
                "model_id": "claude-opus-4-6",
                # Source: https://www.anthropic.com/pricing (2026-04-30 확인)
                "context_window": 200000,
                "max_output_tokens": 8192,
                "supports_vision": True,
                "supports_streaming": True,
                "role": "step_evaluator",
                "pricing_unit": "tokens",
                "input_price_per_1m_usd": 15.0,
                "output_price_per_1m_usd": 75.0,
            }
        ),
        "imported_from": _SEED_TAG,
    },
    # ----------------------------------------------------------------- image
    {
        "id": "01KR2NMPM787769BR68CWNYDDJ",
        "name": "Nano Banana Pro",
        "type": "image",
        "provider": "replicate",
        "profile": json.dumps(
            {
                "model_id": "google/nano-banana-pro",
                # Source: https://replicate.com/google/nano-banana-pro (2026-04-29 확인)
                "supports_vision": False,
                "pricing_unit": "prediction",
                "cost_per_prediction_usd": 0.003,
                "output_format": "image",
                "default_params": {
                    "width": 1024,
                    "height": 1024,
                },
            }
        ),
        "imported_from": _SEED_TAG,
    },
    {
        "id": "01KR2NMPM787769BR68CWNYDDP",
        "name": "GPT-Image-1",
        "type": "image",
        "provider": "openai",
        "profile": json.dumps(
            {
                "model_id": "gpt-image-1",
                # Source: https://openai.com/api/pricing (2026-05-08 확인)
                "supports_vision": False,
                "pricing_unit": "image",
                # Low quality 1024x1024 = $0.011, high quality = $0.040
                # Using standard quality as baseline
                "cost_per_image_usd": 0.011,
                "output_format": "image",
                "default_params": {
                    "size": "1024x1024",
                    "quality": "standard",
                },
            }
        ),
        "imported_from": _SEED_TAG,
    },
    # ----------------------------------------------------------------- video
    {
        "id": "01KR2NMPM787769BR68CWNYDDK",
        "name": "Kling v2.5 Turbo Pro",
        "type": "video",
        "provider": "replicate",
        "profile": json.dumps(
            {
                "model_id": "kuaishou/kling-v2.5-turbo-pro",
                # Source: https://replicate.com/kuaishou/kling-v2.5-turbo-pro (2026-04-29 확인)
                "supports_vision": False,
                "pricing_unit": "prediction",
                "cost_per_prediction_usd": 0.14,
                "output_format": "video",
                "default_params": {
                    "duration": 5,
                    "fps": 24,
                },
            }
        ),
        "imported_from": _SEED_TAG,
    },
    {
        "id": "01KR2NMPM787769BR68CWNYDDM",
        "name": "Seedance 1.5 Pro",
        "type": "video",
        "provider": "replicate",
        "profile": json.dumps(
            {
                "model_id": "bytedance/seedance-1.5-pro",
                # Source: https://replicate.com/bytedance/seedance-1.5-pro (2026-04-29 확인)
                "supports_vision": False,
                "pricing_unit": "prediction",
                "cost_per_prediction_usd": 0.50,
                "output_format": "video",
                "default_params": {
                    "duration": 5,
                    "fps": 24,
                },
            }
        ),
        "imported_from": _SEED_TAG,
    },
    {
        "id": "01KR2NMPM787769BR68CWNYDDN",
        "name": "Runway Gen3",
        "type": "video",
        "provider": "replicate",
        "profile": json.dumps(
            {
                "model_id": "runway/gen3",
                # Source: https://replicate.com/runway/gen3 (2026-04-29 확인)
                "supports_vision": False,
                "pricing_unit": "prediction",
                "cost_per_prediction_usd": 0.40,
                "output_format": "video",
                "default_params": {
                    "duration": 5,
                    "fps": 24,
                },
            }
        ),
        "imported_from": _SEED_TAG,
    },
]

# model_id values extracted from profile for downgrade DELETE
_SEEDED_MODEL_IDS: list[str] = [
    "gpt-5.4",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "google/nano-banana-pro",
    "gpt-image-1",
    "kuaishou/kling-v2.5-turbo-pro",
    "bytedance/seedance-1.5-pro",
    "runway/gen3",
]


def upgrade() -> None:
    conn = op.get_bind()
    for row in _MODELS:
        # ON CONFLICT (id) DO NOTHING — safe to re-run if migration is applied
        # to a DB that already has partial data from a previous failed run.
        conn.execute(
            sa.text(
                "INSERT INTO model_profiles (id, name, type, provider, profile, imported_from)"
                " VALUES (:id, :name, :type, :provider, CAST(:profile AS jsonb), :imported_from)"
                " ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "provider": row["provider"],
                "profile": row["profile"],
                "imported_from": row["imported_from"],
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Delete by ULID primary keys (stable, won't accidentally delete user-added rows)
    ids = [row["id"] for row in _MODELS]
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": id_ for i, id_ in enumerate(ids)}
    conn.execute(
        sa.text(f"DELETE FROM model_profiles WHERE id IN ({placeholders})"),
        params,
    )
