"""PromptModifier Protocol and NoopPromptModifier (F01 §FR-8).

This module defines the interface between F01 Auto Evaluation Loop and
F02 Prompt Optimizer.  F01 calls modifier.modify() after each FAIL to
optionally obtain a mutated prompt version; F02 provides the real implementation.

Conventions:
  - Protocol lives in domain/prompt/ (adjacent to template.py and repo.py).
  - domain must NOT import from services / infra / adapters.
  - All methods are async to allow F02's LlmPromptModifier to call adapters.

Return contract:
  (new_prompt_text, new_prompt_version_id)
  - new_prompt_version_id is None  → caller keeps the previous prompt_version_id
    (no new version was created).
  - new_prompt_text is "" when new_prompt_version_id is None (NoopPromptModifier)
    → caller must use the existing prompt body unchanged.
"""

from __future__ import annotations

from typing import Any, Protocol


class PromptModifier(Protocol):
    """F02 interface — modify a prompt after an evaluation FAIL.

    F01 calls this once per retry iteration.  F02 provides LlmPromptModifier
    which creates a new PromptVersion and returns its id.  While F02 is absent
    the NoopPromptModifier is used, preserving the same prompt_version_id so
    that the next attempt re-runs with the identical prompt.
    """

    async def modify(
        self,
        prompt_version_id: str | None,
        retry_guidance: dict[str, Any],
        failed_dimensions: list[str],
    ) -> tuple[str, str | None]:
        """Return (new_prompt_text, new_prompt_version_id).

        Args:
            prompt_version_id:  The PromptVersion currently associated with the
                                node (None for inline-prompt nodes).
            retry_guidance:     Structured guidance dict from EvaluationResult
                                (e.g. {"instruction": "...", "confidence": 0.8}).
            failed_dimensions:  List of dimension names that scored below
                                PASS_THRESHOLD (e.g. ["composition", "lighting"]).

        Returns:
            (new_prompt_text, new_prompt_version_id) where:
              - new_prompt_text        is the modified prompt body (may be "").
              - new_prompt_version_id  is the newly created PromptVersion id,
                                       or None if the prompt was not changed.

        Caller contract:
            if new_prompt_version_id is None:
                use the existing prompt body and prompt_version_id unchanged.
            else:
                use new_prompt_text as the resolved prompt for the next attempt
                and record new_prompt_version_id in retry_attempts.
        """
        ...


class NoopPromptModifier:
    """Default modifier used while F02 Prompt Optimizer is not yet deployed.

    Returns ("", same_prompt_version_id) so the caller keeps the existing
    prompt body unmodified and records the same prompt_version_id for the
    next attempt.  When F02 is introduced, replace this with LlmPromptModifier.
    """

    async def modify(
        self,
        prompt_version_id: str | None,
        retry_guidance: dict[str, Any],
        failed_dimensions: list[str],
    ) -> tuple[str, str | None]:
        # new_prompt_version_id is None → caller uses the existing prompt body.
        return ("", prompt_version_id)
