from __future__ import annotations

import pytest

from style_workbench.domain.prompt.template import (
    TemplateError,
    extract_placeholders,
    safe_substitute,
)

# ---------------------------------------------------------------------------
# extract_placeholders
# ---------------------------------------------------------------------------


def test_extract_placeholders_simple() -> None:
    assert extract_placeholders("Hello {name}, you are {age} years old.") == {"name", "age"}


def test_extract_placeholders_empty() -> None:
    assert extract_placeholders("No placeholders here.") == set()


def test_extract_placeholders_deduplicates() -> None:
    assert extract_placeholders("{x} and {x} again") == {"x"}


def test_extract_placeholders_ignores_format_spec() -> None:
    # {name:>10} — format spec present, should NOT be matched
    assert extract_placeholders("{name:>10}") == set()


def test_extract_placeholders_matches_digit_keys() -> None:
    # {0} and {1} technically match \w+ (digits are word characters).
    # safe_substitute will look up "0"/"1" in the context dict — this is safe
    # because no Python attribute access or format-spec evaluation occurs.
    assert extract_placeholders("{0} and {1}") == {"0", "1"}


def test_extract_placeholders_ignores_attribute_access() -> None:
    assert extract_placeholders("{a.b} and {obj.__class__}") == set()


# ---------------------------------------------------------------------------
# safe_substitute — happy path
# ---------------------------------------------------------------------------


def test_safe_substitute_single_placeholder() -> None:
    result = safe_substitute("Hello {name}!", {"name": "World"})
    assert result == "Hello World!"


def test_safe_substitute_multiple_placeholders() -> None:
    result = safe_substitute("{greeting}, {target}!", {"greeting": "Hi", "target": "Alice"})
    assert result == "Hi, Alice!"


def test_safe_substitute_numeric_value() -> None:
    result = safe_substitute("Count: {n}", {"n": 42})
    assert result == "Count: 42"


def test_safe_substitute_no_placeholders() -> None:
    result = safe_substitute("Plain text.", {})
    assert result == "Plain text."


def test_safe_substitute_extra_keys_ignored() -> None:
    # Extra keys in context that are not in the template are silently ignored.
    result = safe_substitute("Hello {name}!", {"name": "Bob", "unused": "x"})
    assert result == "Hello Bob!"


# ---------------------------------------------------------------------------
# safe_substitute — missing placeholder handling
# ---------------------------------------------------------------------------


def test_safe_substitute_missing_raises_by_default() -> None:
    with pytest.raises(TemplateError, match="Missing placeholder value: 'name'"):
        safe_substitute("Hello {name}!", {})


def test_safe_substitute_allow_missing_leaves_placeholder() -> None:
    result = safe_substitute("Hello {name}!", {}, allow_missing=True)
    assert result == "Hello {name}!"


def test_safe_substitute_allow_missing_partial() -> None:
    result = safe_substitute("{a} and {b}", {"a": "yes"}, allow_missing=True)
    assert result == "yes and {b}"


# ---------------------------------------------------------------------------
# safe_substitute — format string injection defense
# ---------------------------------------------------------------------------


def test_safe_substitute_value_with_braces_is_literal() -> None:
    """User-supplied value containing { } must NOT trigger further substitution."""
    result = safe_substitute("Msg: {body}", {"body": "He said {hello}"})
    # The {hello} inside the value is NOT a placeholder — it is just literal text.
    assert result == "Msg: He said {hello}"


def test_safe_substitute_format_spec_in_template_not_substituted() -> None:
    """{name:>10} does not match our pattern, so it is left verbatim."""
    result = safe_substitute("Padded: {name:>10}", {"name": "x"}, allow_missing=True)
    assert result == "Padded: {name:>10}"


def test_safe_substitute_attribute_access_not_substituted() -> None:
    """{a.__class__} does not match \\w+ pattern and must be left untouched."""
    result = safe_substitute("Type: {a.__class__}", {}, allow_missing=True)
    assert result == "Type: {a.__class__}"


def test_safe_substitute_positional_treated_as_named_key() -> None:
    """``{0}`` matches \\w+ (digit is a word character) and is treated as the key ``"0"``.

    This is safe: safe_substitute does a plain dict lookup on ``"0"``, with no
    attribute access or format-spec evaluation.  The result depends on whether
    ``"0"`` is in the context.
    """
    # Key "0" absent → leave untouched when allow_missing=True
    result = safe_substitute("First: {0}", {}, allow_missing=True)
    assert result == "First: {0}"
    # Key "0" present → substituted
    result2 = safe_substitute("First: {0}", {"0": "item"})
    assert result2 == "First: item"


def test_safe_substitute_injection_vector_attribute_traversal() -> None:
    """Classic Python format-string injection {a.__class__.__bases__} is inert."""
    template = "leak: {obj.__class__.__bases__}"
    result = safe_substitute(template, {"obj": "innocent"}, allow_missing=True)
    # Neither {obj.__class__.__bases__} matches \\w+, so entirely untouched.
    assert result == template


def test_safe_substitute_colon_in_value_is_safe() -> None:
    """Value containing colon (common in URLs) should not affect output."""
    result = safe_substitute("URL: {url}", {"url": "https://example.com:8080/path"})
    assert result == "URL: https://example.com:8080/path"
