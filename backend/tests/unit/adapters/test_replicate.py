from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from style_workbench.adapters.base import ModelInput
from style_workbench.adapters.replicate import ReplicateAdapter
from style_workbench.core.errors import NotConfiguredError, PredictionTimeoutError


def _make_prediction(
    status: str = "succeeded",
    output: object = None,
) -> MagicMock:
    pred = MagicMock()
    pred.status = status
    pred.output = output if output is not None else ["https://replicate.delivery/test.jpg"]
    pred.error = None
    pred.async_reload = AsyncMock()
    return pred


@pytest.fixture
def adapter() -> ReplicateAdapter:
    mock_client = MagicMock()
    prediction = _make_prediction()
    mock_client.predictions.async_create = AsyncMock(return_value=prediction)
    return ReplicateAdapter(client=mock_client)


async def test_generate_returns_artifact_url(adapter: ReplicateAdapter) -> None:
    out = await adapter.generate(
        ModelInput(model_id="kuaishou/kling-v2.5-turbo-pro", prompt="A sunset")
    )
    assert out.artifact_url == "https://replicate.delivery/test.jpg"


async def test_generate_prediction_lifecycle() -> None:
    mock_client = MagicMock()
    pred = _make_prediction(status="processing", output=["https://example.com/video.mp4"])

    call_count = 0

    async def reload_side_effect() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            pred.status = "succeeded"

    pred.async_reload = AsyncMock(side_effect=reload_side_effect)
    mock_client.predictions.async_create = AsyncMock(return_value=pred)

    adapter = ReplicateAdapter(client=mock_client)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        out = await adapter.generate(
            ModelInput(model_id="kuaishou/kling-v2.5-turbo-pro", prompt="A sunset")
        )
    assert out.artifact_url == "https://example.com/video.mp4"
    assert pred.async_reload.call_count >= 2


async def test_poll_timeout_raises() -> None:
    mock_client = MagicMock()
    pred = _make_prediction(status="processing")
    pred.async_reload = AsyncMock()
    adapter = ReplicateAdapter(client=mock_client)
    with pytest.raises(PredictionTimeoutError):
        await adapter._poll(pred, interval=0.001, timeout=0.0)


def test_not_configured_error() -> None:
    mock_settings = MagicMock()
    mock_settings.replicate_api_token = ""
    with (
        patch("style_workbench.adapters.replicate.settings", mock_settings),
        pytest.raises(NotConfiguredError),
    ):
        ReplicateAdapter()


def test_cost_estimate_positive(adapter: ReplicateAdapter) -> None:
    inp = ModelInput(model_id="kuaishou/kling-v2.5-turbo-pro", prompt="test")
    assert adapter.cost_estimate("kuaishou/kling-v2.5-turbo-pro", inp) >= 0.0
