"""Unit tests for domain/prompt/validation.py (spec §4 FR-3, §10.1).

Rule: extract_placeholders(body) ⊆ {v.name for v in declared_variables}
"""

from __future__ import annotations

import pytest

from style_workbench.domain.prompt.entity import DeclaredVariable
from style_workbench.domain.prompt.validation import (
    PromptValidationError,
    validate_placeholders,
)

# ---------------------------------------------------------------------------
# Positive cases — should NOT raise
# ---------------------------------------------------------------------------


def test_no_placeholders_no_declared_variables() -> None:
    validate_placeholders("Static prompt with no variables.", [])


def test_no_placeholders_with_declared_variables() -> None:
    """Declared variables without matching placeholders are fine (they're optional context)."""
    vars_ = [DeclaredVariable(name="name"), DeclaredVariable(name="role")]
    validate_placeholders("No placeholders here.", vars_)


def test_all_placeholders_declared() -> None:
    vars_ = [DeclaredVariable(name="name"), DeclaredVariable(name="role")]
    validate_placeholders("Hello {name}, your role is {role}.", vars_)


def test_single_placeholder_single_declared() -> None:
    validate_placeholders("Say hello to {name}.", [DeclaredVariable(name="name")])


def test_repeated_placeholder_counted_once() -> None:
    """Same placeholder appearing twice — declared once is sufficient."""
    validate_placeholders("{name} is {name}.", [DeclaredVariable(name="name")])


def test_format_spec_not_matched() -> None:
    """{name:>10} is NOT a strict word-identifier — must not raise."""
    validate_placeholders("Aligned: {name:>10}", [])


def test_positional_index_matched_as_word_identifier() -> None:
    """PLACEHOLDER_PATTERN uses \\w+ which includes digits, so {0} IS matched as name '0'.
    Callers should declare it if they use it; the pattern is intentionally broad."""
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("Positional: {0}", [])
    assert "0" in exc_info.value.undeclared


def test_attribute_access_not_matched() -> None:
    """{a.b} contains a dot which is NOT a \\w character — not matched."""
    validate_placeholders("Attribute: {a.b}", [])


def test_double_brace_still_matches_inner_content() -> None:
    """{{not_a_placeholder}} — the outer {{ and }} reduce to literals at runtime,
    but PLACEHOLDER_PATTERN still finds 'not_a_placeholder' inside.
    Callers must declare or avoid this pattern; safe_substitute leaves it untouched."""
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("Escaped: {{not_a_placeholder}}", [])
    assert "not_a_placeholder" in exc_info.value.undeclared


def test_multiple_placeholders_all_declared() -> None:
    vars_ = [
        DeclaredVariable(name="subject"),
        DeclaredVariable(name="verb"),
        DeclaredVariable(name="object"),
    ]
    validate_placeholders("{subject} {verb} {object}.", vars_)


# ---------------------------------------------------------------------------
# Negative cases — should raise PromptValidationError
# ---------------------------------------------------------------------------


def test_single_undeclared_placeholder_raises() -> None:
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("Hello {name}.", [])
    assert "name" in exc_info.value.undeclared


def test_partial_undeclared_raises() -> None:
    """name is declared, role is not — should raise for role."""
    vars_ = [DeclaredVariable(name="name")]
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("Hi {name}, your role: {role}.", vars_)
    assert exc_info.value.undeclared == {"role"}


def test_multiple_undeclared_raises() -> None:
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("{a} {b} {c}", [])
    assert exc_info.value.undeclared == {"a", "b", "c"}


def test_error_message_lists_undeclared_names() -> None:
    vars_ = [DeclaredVariable(name="known")]
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("{known} and {unknown}", vars_)
    assert "unknown" in str(exc_info.value)


def test_error_contains_undeclared_attribute() -> None:
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("{x}", [])
    assert exc_info.value.undeclared == {"x"}


def test_declared_variable_required_flag_does_not_affect_validation() -> None:
    """required=False still counts as declared — validation only checks name membership."""
    vars_ = [DeclaredVariable(name="opt", required=False)]
    validate_placeholders("{opt}", vars_)  # must not raise


def test_declared_variable_with_role_counts_as_declared() -> None:
    vars_ = [DeclaredVariable(name="title", role="job_title", required=True)]
    validate_placeholders("Your title: {title}", vars_)  # must not raise


def test_undeclared_despite_role_match_raises() -> None:
    """A DeclaredVariable whose *role* matches the placeholder name is insufficient
    — only the *name* field is checked."""
    vars_ = [DeclaredVariable(name="other_name", role="name")]  # role='name', but name='other_name'
    with pytest.raises(PromptValidationError) as exc_info:
        validate_placeholders("{name}", vars_)
    assert "name" in exc_info.value.undeclared
