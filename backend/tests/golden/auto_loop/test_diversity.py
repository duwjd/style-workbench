"""Fixture diversity validation tests.

Ensures the 50 golden scenarios have sufficient variety in node types,
FAIL dimensions, and attempt distributions to meaningfully exercise the
AutoLoopOrchestrator retry mechanics.

These tests run independently of AC-1 and serve as a guard against
accidentally over-fitting the fixture distribution (e.g., 100% pass-at-0).
"""

from __future__ import annotations

import pytest

from tests.golden.auto_loop.scenarios import GOLDEN_SCENARIOS

# ---------------------------------------------------------------------------
# Minimum diversity thresholds
# ---------------------------------------------------------------------------

_MIN_SCENARIOS_PER_NODE_TYPE = 10
_MIN_FAIL_DIMENSIONS = 5
_MIN_SCENARIOS_WITH_RETRIES = 15  # pass_at_attempt >= 1 or None
_MIN_SCENARIOS_FAILING_ALL = 5  # pass_at_attempt == None


@pytest.mark.golden
def test_total_scenario_count() -> None:
    """Exactly 50 scenarios must be defined."""
    assert len(GOLDEN_SCENARIOS) == 50, f"Expected 50 golden scenarios, got {len(GOLDEN_SCENARIOS)}"


@pytest.mark.golden
def test_node_type_distribution_minimum() -> None:
    """Each node type must have at least 10 scenarios."""
    from collections import Counter

    counts: Counter[str] = Counter(s.node_type for s in GOLDEN_SCENARIOS)
    for node_type in ("text", "image", "video", "composition"):
        count = counts[node_type]
        assert count >= _MIN_SCENARIOS_PER_NODE_TYPE, (
            f"Node type '{node_type}' has only {count} scenarios "
            f"(minimum {_MIN_SCENARIOS_PER_NODE_TYPE})"
        )


@pytest.mark.golden
def test_fail_dimension_variety() -> None:
    """At least 5 distinct FAIL dimensions must appear across all scenarios."""
    all_dims: set[str] = set()
    for scenario in GOLDEN_SCENARIOS:
        all_dims.update(scenario.failed_dimensions)

    assert len(all_dims) >= _MIN_FAIL_DIMENSIONS, (
        f"Only {len(all_dims)} distinct FAIL dimensions found "
        f"(minimum {_MIN_FAIL_DIMENSIONS}): {sorted(all_dims)}"
    )


@pytest.mark.golden
def test_retry_scenario_minimum() -> None:
    """At least 15 scenarios require at least one retry attempt."""
    retry_count = sum(
        1 for s in GOLDEN_SCENARIOS if s.pass_at_attempt is None or s.pass_at_attempt >= 1
    )
    assert retry_count >= _MIN_SCENARIOS_WITH_RETRIES, (
        f"Only {retry_count} scenarios require retries (minimum {_MIN_SCENARIOS_WITH_RETRIES})"
    )


@pytest.mark.golden
def test_fail_all_scenario_minimum() -> None:
    """At least 5 scenarios exhaust all retries (pass_at_attempt == None)."""
    fail_all_count = sum(1 for s in GOLDEN_SCENARIOS if s.pass_at_attempt is None)
    assert fail_all_count >= _MIN_SCENARIOS_FAILING_ALL, (
        f"Only {fail_all_count} scenarios fail all attempts (minimum {_MIN_SCENARIOS_FAILING_ALL})"
    )


@pytest.mark.golden
def test_pass_at_attempt_distribution() -> None:
    """Verify the expected distribution across attempt levels.

    Expected (see scenarios.py module docstring):
      pass_at_attempt 0:    20 scenarios
      pass_at_attempt 1:    12 scenarios
      pass_at_attempt 2:     5 scenarios
      pass_at_attempt 3:     3 scenarios
      pass_at_attempt None: 10 scenarios
    """
    from collections import Counter

    counts: Counter[int | None] = Counter(s.pass_at_attempt for s in GOLDEN_SCENARIOS)

    assert counts[0] == 20, f"pass_at_attempt=0: expected 20, got {counts[0]}"
    assert counts[1] == 12, f"pass_at_attempt=1: expected 12, got {counts[1]}"
    assert counts[2] == 5, f"pass_at_attempt=2: expected 5, got {counts[2]}"
    assert counts[3] == 3, f"pass_at_attempt=3: expected 3, got {counts[3]}"
    assert counts[None] == 10, f"pass_at_attempt=None: expected 10, got {counts[None]}"


@pytest.mark.golden
def test_scenario_names_unique() -> None:
    """All 50 scenario names must be unique."""
    names = [s.name for s in GOLDEN_SCENARIOS]
    assert len(set(names)) == len(names), (
        f"Duplicate scenario names found: {[n for n in names if names.count(n) > 1]}"
    )


@pytest.mark.golden
def test_all_node_types_valid() -> None:
    """All scenario node_type values must be in the known set."""
    valid = {"text", "image", "video", "composition"}
    for scenario in GOLDEN_SCENARIOS:
        assert scenario.node_type in valid, (
            f"Scenario '{scenario.name}' has invalid node_type '{scenario.node_type}'"
        )


@pytest.mark.golden
def test_pass_scenarios_have_no_failed_dims() -> None:
    """Scenarios with pass_at_attempt==0 should declare no failed_dimensions."""
    for scenario in GOLDEN_SCENARIOS:
        if scenario.pass_at_attempt == 0:
            assert scenario.failed_dimensions == [], (
                f"Scenario '{scenario.name}' passes at attempt 0 "
                f"but has failed_dimensions: {scenario.failed_dimensions}"
            )


@pytest.mark.golden
def test_fail_scenarios_have_failed_dims() -> None:
    """Scenarios that do not pass at attempt 0 should declare at least one failed dimension."""
    for scenario in GOLDEN_SCENARIOS:
        if scenario.pass_at_attempt != 0:
            assert len(scenario.failed_dimensions) > 0, (
                f"Scenario '{scenario.name}' (pass_at_attempt={scenario.pass_at_attempt}) "
                f"declares no failed_dimensions — mock evaluator needs at least one."
            )
