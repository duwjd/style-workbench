from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from style_workbench.core.ids import new_ulid
from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.prompts.shared.output_schema import parse_eval_output

INPUTS_DIR = Path(__file__).parent / "inputs"
EXPECTED_DIR = Path(__file__).parent / "expected"
SCORE_TOLERANCE = 0.05


@pytest.mark.parametrize("case", ["tone_match_pass"])
def test_text_eval_schema_valid(case: str) -> None:
    inp = json.loads((INPUTS_DIR / f"{case}.json").read_text())
    raw = json.dumps(inp["raw_llm_response"])
    out = parse_eval_output(raw)
    assert out.scores
    assert out.rationale
    assert isinstance(out.notable_issues, list)


@pytest.mark.parametrize("case", ["tone_match_pass"])
def test_text_eval_scores_within_tolerance(case: str) -> None:
    inp = json.loads((INPUTS_DIR / f"{case}.json").read_text())
    expected = json.loads((EXPECTED_DIR / f"{case}.json").read_text())
    raw = json.dumps(inp["raw_llm_response"])
    out = parse_eval_output(raw)

    for dim, exp_score in expected["expected_scores"].items():
        assert dim in out.scores, f"Missing dimension: {dim}"
        assert abs(out.scores[dim] - exp_score) <= SCORE_TOLERANCE, (
            f"{dim}: expected {exp_score}, got {out.scores[dim]}"
        )


@pytest.mark.parametrize("case", ["tone_match_pass"])
def test_text_eval_pass_threshold(case: str) -> None:
    inp = json.loads((INPUTS_DIR / f"{case}.json").read_text())
    expected = json.loads((EXPECTED_DIR / f"{case}.json").read_text())
    raw = json.dumps(inp["raw_llm_response"])
    out = parse_eval_output(raw)

    dims = [
        DimensionScore(name=k, score=v, rationale=out.rationale.get(k, ""))
        for k, v in out.scores.items()
    ]
    result = EvaluationResult(
        id=new_ulid(),
        node_execution_id="mock_ne",
        evaluator_model="claude-opus-4-6",
        dimensions=dims,
        notable_issues=out.notable_issues,
        retry_guidance=None,
        created_at=datetime.now(UTC),
    )
    assert result.overall_passed == expected["expected_overall_passed"]
