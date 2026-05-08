from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from style_workbench.adapters.base import ModelOutput
from style_workbench.services.evaluation_service import EvaluationService


def _make_mock_ne(
    node_type: str = "text_generation",
    artifact_url: str | None = None,
    text: str = "Sample text",
) -> MagicMock:
    ne = MagicMock()
    ne.node_type = node_type
    ne.artifact_url = artifact_url
    ne.raw_response = {"text": text}
    return ne


def _make_eval_response(scores: dict[str, float]) -> str:
    rationale = {k: "Some rationale" for k in scores}
    return json.dumps({"scores": scores, "rationale": rationale, "notable_issues": []})


@pytest.fixture
def eval_service_parts() -> tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock]:
    run_repo = AsyncMock()
    eval_repo = AsyncMock()
    claude = AsyncMock()
    svc = EvaluationService(run_repo=run_repo, eval_repo=eval_repo, claude_adapter=claude)
    return svc, run_repo, eval_repo, claude


@pytest.mark.asyncio
async def test_evaluate_text_pass(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    svc, run_repo, eval_repo, claude = eval_service_parts
    run_repo.get_node_execution.return_value = _make_mock_ne("text_generation", text="Good content")
    claude.generate.return_value = ModelOutput(
        text=_make_eval_response({"tone_match": 0.9, "length": 0.85, "forbidden_words": 1.0}),
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )

    result = await svc.evaluate("ne_test_id", "Business portrait brief")

    assert result.overall_passed is True
    assert result.node_execution_id == "ne_test_id"
    assert eval_repo.save.call_count == 1


@pytest.mark.asyncio
async def test_evaluate_text_fail_below_threshold(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    svc, run_repo, eval_repo, claude = eval_service_parts
    run_repo.get_node_execution.return_value = _make_mock_ne("text_generation")
    claude.generate.return_value = ModelOutput(
        text=_make_eval_response({"tone_match": 0.5, "length": 0.9, "forbidden_words": 1.0}),
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )

    result = await svc.evaluate("ne_fail_id")

    assert result.overall_passed is False
    assert "tone_match" in result.failed_dimensions
    assert result.retry_guidance is not None


@pytest.mark.asyncio
async def test_evaluate_image_passes_image_urls(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    svc, run_repo, eval_repo, claude = eval_service_parts
    run_repo.get_node_execution.return_value = _make_mock_ne(
        "image_generation", artifact_url="https://example.com/img.jpg"
    )
    claude.generate.return_value = ModelOutput(
        text=_make_eval_response(
            {"text_absence": 0.95, "resolution_quality": 0.88, "composition": 0.82}
        ),
        input_tokens=200,
        output_tokens=100,
        cost_usd=0.05,
    )

    result = await svc.evaluate("ne_img_id")

    # ClaudeAdapter에 image_urls가 전달됐는지 확인
    call_args = claude.generate.call_args[0][0]  # ModelInput
    assert len(call_args.image_urls) > 0
    assert call_args.image_urls[0] == "https://example.com/img.jpg"
    assert result.overall_passed is True


@pytest.mark.asyncio
async def test_eval_repo_save_called_once(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    svc, run_repo, eval_repo, claude = eval_service_parts
    run_repo.get_node_execution.return_value = _make_mock_ne("text_generation")
    claude.generate.return_value = ModelOutput(
        text=_make_eval_response({"tone_match": 0.8, "length": 0.8, "forbidden_words": 0.8}),
        input_tokens=50,
        output_tokens=30,
        cost_usd=0.005,
    )
    await svc.evaluate("ne_save_test")
    eval_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_not_found_raises(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    from style_workbench.core.errors import RunNotFoundError

    svc, run_repo, _eval_repo, _claude = eval_service_parts
    run_repo.get_node_execution.return_value = None

    with pytest.raises(RunNotFoundError):
        await svc.evaluate("nonexistent_ne_id")


@pytest.mark.asyncio
async def test_evaluate_video_no_frame_url(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    svc, run_repo, eval_repo, claude = eval_service_parts
    run_repo.get_node_execution.return_value = _make_mock_ne("video_generation", artifact_url=None)
    claude.generate.return_value = ModelOutput(
        text=_make_eval_response(
            {
                "motion_artifact": 0.8,
                "subject_preservation": 0.75,
                "motion_compliance": 0.72,
                "speed_consistency": 0.78,
            }
        ),
        input_tokens=150,
        output_tokens=80,
        cost_usd=0.02,
    )

    result = await svc.evaluate("ne_video_id")

    # frame_urls 없는 경우 image_urls=[] 로 전달되어야 함
    call_args = claude.generate.call_args[0][0]
    assert call_args.image_urls == []
    assert result.overall_passed is True


@pytest.mark.asyncio
async def test_evaluate_result_has_evaluator_model(
    eval_service_parts: tuple[EvaluationService, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    from style_workbench.prompts.evaluator_text import EVALUATOR_MODEL

    svc, run_repo, _eval_repo, claude = eval_service_parts
    run_repo.get_node_execution.return_value = _make_mock_ne("text_generation")
    claude.generate.return_value = ModelOutput(
        text=_make_eval_response({"tone_match": 0.8, "length": 0.8, "forbidden_words": 0.8}),
        input_tokens=50,
        output_tokens=30,
        cost_usd=0.005,
    )

    result = await svc.evaluate("ne_model_test")
    assert result.evaluator_model == EVALUATOR_MODEL
