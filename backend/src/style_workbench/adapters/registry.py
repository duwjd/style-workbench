from __future__ import annotations

import contextlib

from style_workbench.adapters.base import ModelAdapter
from style_workbench.adapters.claude import ClaudeAdapter
from style_workbench.adapters.openai import OpenAIAdapter
from style_workbench.adapters.replicate import ReplicateAdapter
from style_workbench.core.errors import NotConfiguredError

_REGISTRY: dict[str, ModelAdapter] = {}


def _default_registry() -> dict[str, ModelAdapter]:
    adapters: dict[str, ModelAdapter] = {
        "anthropic": ClaudeAdapter(),
        "openai": OpenAIAdapter(),
    }
    with contextlib.suppress(NotConfiguredError):
        adapters["replicate"] = ReplicateAdapter()
    return adapters


def get_adapter(provider: str) -> ModelAdapter:
    """Return the ModelAdapter for the given provider string.

    Raises KeyError if provider is not registered.
    """
    if not _REGISTRY:
        _REGISTRY.update(_default_registry())
    try:
        return _REGISTRY[provider]
    except KeyError:
        raise KeyError(f"No adapter registered for provider '{provider}'") from None


def register(provider: str, adapter: ModelAdapter) -> None:
    """Register a custom adapter (useful for testing or Replicate extension)."""
    _REGISTRY[provider] = adapter


def clear_registry() -> None:
    """Reset registry to empty (test teardown helper)."""
    _REGISTRY.clear()
