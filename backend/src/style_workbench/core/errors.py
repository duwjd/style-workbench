from __future__ import annotations


class StyleWorkbenchError(Exception):
    """Base for all domain errors."""


class DagCycleError(StyleWorkbenchError):
    """Raised when a DAG contains a directed cycle."""


class DagValidationError(StyleWorkbenchError):
    """Raised when a DAG fails structural validation."""


class NotConfiguredError(StyleWorkbenchError):
    """Raised when required configuration (e.g. an API token) is missing."""


class PredictionTimeoutError(StyleWorkbenchError):
    """Raised when a Replicate prediction exceeds the polling timeout."""


class RunAbortedError(StyleWorkbenchError):
    """Raised when a run is aborted due to budget overage or a node failure."""


class StyleNotFoundError(StyleWorkbenchError):
    """Raised when a Style with the given id does not exist."""


class VersionNotFoundError(StyleWorkbenchError):
    """Raised when a StyleVersion with the given id does not exist."""


class RunNotFoundError(StyleWorkbenchError):
    """Raised when a Run with the given id does not exist."""


class EvaluationNotFoundError(StyleWorkbenchError):
    """Raised when an Evaluation with the given id does not exist."""


class ConflictError(StyleWorkbenchError):
    """Raised when an operation conflicts with current resource state.

    Example: aborting a run that is already in a terminal state.
    """


# ---------------------------------------------------------------------------
# F05 Prompt Library errors
# ---------------------------------------------------------------------------


class PromptNotFoundError(StyleWorkbenchError):
    """Raised when a Prompt with the given id does not exist."""


class PromptVersionNotFoundError(StyleWorkbenchError):
    """Raised when a PromptVersion with the given id does not exist."""


class PromptUsageNotFoundError(StyleWorkbenchError):
    """Raised when a PromptUsage with the given id does not exist."""


class InvalidPromptStatusTransitionError(StyleWorkbenchError):
    """Raised when a requested lifecycle transition is not allowed.

    Example: approved → draft is not a permitted transition.
    """


class PromptDeprecatedError(StyleWorkbenchError):
    """Raised when a deprecated Prompt is used in a new Style node link.

    spec §4 FR-9: deprecated prompt cannot be linked to new nodes.
    """


class MissingDeclaredVariableError(StyleWorkbenchError):
    """Raised when body placeholders are not all covered by declared_variables.

    spec §4 FR-3 / §6.3: extract_placeholders(body) ⊄ declared_variables[].name.
    Mapped to HTTP 422 at the API layer.
    """


class PreconditionFailedError(StyleWorkbenchError):
    """Raised when an If-Match header is missing or does not match the current ETag.

    spec §6.4: optimistic locking for concurrent edits.
    Mapped to HTTP 412 at the API layer.
    """


# ---------------------------------------------------------------------------
# F05 단계 5: A/B comparison errors
# ---------------------------------------------------------------------------


class PromptAbComparisonNotFoundError(StyleWorkbenchError):
    """Raised when a PromptAbComparison with the given id does not exist."""


class PromptAbSameVersionError(StyleWorkbenchError):
    """Raised when from_version and to_version are identical.

    An A/B comparison with the same version for both sides has no informational
    value and is rejected (spec §10.2 시나리오 3 결정).
    Mapped to HTTP 422 at the API layer.
    """


class StyleVersionHasNoPromptNodeError(StyleWorkbenchError):
    """Raised when the given style_version_id has no node referencing the prompt.

    spec §4 FR-8: the style_version must have a node whose prompt_id matches
    the prompt being compared.  If none found → 422.
    """


# ---------------------------------------------------------------------------
# F02 Prompt Optimizer errors
# ---------------------------------------------------------------------------


class PromptOptimizerInvalidOutputError(StyleWorkbenchError):
    """Raised when LlmPromptModifier receives an invalid response from Claude.

    Causes:
      - Required placeholder(s) missing from new_body.
      - JSON parse failure.
      - Missing required fields in the JSON response.

    On this error, LlmPromptModifier saves a succeeded=false row in
    prompt_optimizations and returns Noop fallback ("", None) — F01 回귀 안전.
    HTTP 200 is returned (F02 call succeeded; LLM output was sub-standard).
    """


class PromptOptimizationNotFoundError(StyleWorkbenchError):
    """Raised when a PromptOptimization with the given id does not exist."""
