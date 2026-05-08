from __future__ import annotations

import asyncio
from typing import Any

from replicate.client import Client as ReplicateClient

from style_workbench.adapters.base import ModelAdapter, ModelInput, ModelOutput
from style_workbench.core.config import settings
from style_workbench.core.errors import NotConfiguredError, PredictionTimeoutError
from style_workbench.core.pricing import cost_usd_replicate

_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 300.0  # 5 minutes


class ReplicateAdapter(ModelAdapter):
    def __init__(self, client: ReplicateClient | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            token = settings.replicate_api_token
            if not token:
                raise NotConfiguredError("REPLICATE_API_TOKEN is not set")
            self._client = ReplicateClient(api_token=token)

    async def generate(self, input: ModelInput) -> ModelOutput:
        replicate_input: dict[str, Any] = {"prompt": input.prompt}
        prediction = await self._client.predictions.async_create(
            model=input.model_id,
            input=replicate_input,
        )
        completed = await self._poll(prediction)
        output = completed.output
        if isinstance(output, list):
            artifact_url = str(output[0]) if output else ""
        else:
            artifact_url = str(output) if output is not None else ""
        return ModelOutput(
            text="",
            input_tokens=0,
            output_tokens=0,
            cost_usd=cost_usd_replicate(input.model_id),
            artifact_url=artifact_url,
        )

    async def _poll(
        self,
        prediction: Any,
        interval: float = _POLL_INTERVAL,
        timeout: float = _POLL_TIMEOUT,
    ) -> Any:
        start = asyncio.get_running_loop().time()
        while True:
            await prediction.async_reload()
            status: str = prediction.status
            if status == "succeeded":
                return prediction
            if status in ("failed", "canceled"):
                error = getattr(prediction, "error", status)
                raise RuntimeError(f"Prediction {status}: {error}")
            if asyncio.get_running_loop().time() - start >= timeout:
                raise PredictionTimeoutError(f"Prediction did not complete within {timeout:.0f}s")
            await asyncio.sleep(interval)

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        return cost_usd_replicate(model_id)
