"""Prompt body validation (spec §4 FR-3).

Rule: extract_placeholders(body) ⊆ {v.name for v in declared_variables}

Any placeholder that appears in the body but is NOT listed in declared_variables
raises PromptValidationError (mapped to HTTP 422 at the API layer via core/errors.py).

This module has NO external dependencies.  It only imports:
- domain/prompt/template.py  (safe, pure string processing)
- domain/prompt/entity.py    (pure dataclasses)

No core/infra/services imports are allowed here.
"""

from __future__ import annotations

from style_workbench.domain.prompt.entity import DeclaredVariable
from style_workbench.domain.prompt.template import extract_placeholders


class PromptValidationError(Exception):
    """Raised when a prompt body contains undeclared placeholders.

    Kept as a plain Exception (not importing StyleWorkbenchError) so that
    domain/prompt/validation.py remains free of cross-layer imports.
    Registration in core/errors.py maps this to HTTP 422.
    """

    def __init__(self, undeclared: set[str]) -> None:
        self.undeclared = undeclared
        names = ", ".join(sorted(undeclared))
        super().__init__(
            f"Prompt body contains placeholder(s) not declared in declared_variables: {names}"
        )


def validate_placeholders(
    body: str,
    declared_variables: list[DeclaredVariable],
) -> None:
    """Assert that every placeholder in *body* is listed in *declared_variables*.

    Args:
        body:                 The prompt body text.
        declared_variables:   The list of DeclaredVariable instances for this version.

    Raises:
        PromptValidationError: If any placeholder in body is absent from
                               declared_variables[].name.

    Example::

        validate_placeholders(
            "Hello {name}, your role is {role}.",
            [DeclaredVariable(name="name"), DeclaredVariable(name="role")],
        )  # passes

        validate_placeholders(
            "Hello {name}, your title is {title}.",
            [DeclaredVariable(name="name")],
        )  # raises PromptValidationError({'title'})
    """
    found = extract_placeholders(body)
    declared_names = {v.name for v in declared_variables}
    undeclared = found - declared_names
    if undeclared:
        raise PromptValidationError(undeclared)
