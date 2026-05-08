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
