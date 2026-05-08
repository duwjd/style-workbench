from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class ModelInput(BaseModel):
    model_id: str
    prompt: str
    system: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    image_urls: list[str] = []


class ModelOutput(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    artifact_url: str | None = None


class ModelAdapter(ABC):
    @abstractmethod
    async def generate(self, input: ModelInput) -> ModelOutput: ...

    @abstractmethod
    def cost_estimate(self, model_id: str, input: ModelInput) -> float: ...
