from __future__ import annotations

from style_workbench.domain.style.variables import extract_variables, validate_variables


def test_extract_single_placeholder() -> None:
    assert extract_variables("Hello {name}!") == ["name"]


def test_extract_multiple_unique_order_preserved() -> None:
    result = extract_variables("{a} and {b} and {a} again")
    assert result == ["a", "b"]  # dedup, first-seen order


def test_extract_no_placeholders() -> None:
    assert extract_variables("no placeholders here") == []


def test_extract_ignores_numeric_start() -> None:
    # {1invalid} — 숫자로 시작하는 건 매칭 안 됨
    assert extract_variables("{1invalid} {valid}") == ["valid"]


def test_validate_variables_all_provided() -> None:
    assert validate_variables("{x} + {y}", {"x", "y"}) == []


def test_validate_variables_missing() -> None:
    missing = validate_variables("{x} + {y}", {"x"})
    assert missing == ["y"]


def test_validate_variables_empty_template() -> None:
    assert validate_variables("no vars", {"x"}) == []
