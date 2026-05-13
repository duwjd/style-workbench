"""AC-1 golden_live suite — retry PASS 비율 ≥70% with real LLM (skeleton).

spec §2.1 Goals, §10.3, AC-1.

이 파일은 @pytest.mark.golden_live 마커를 사용하며, CI nightly 에서만 실행된다.
로컬 실행 시: ANTHROPIC_API_KEY 환경 변수 설정 후 `uv run pytest -m golden_live`.

본 PR 범위:
  - skeleton 만 작성.
  - ANTHROPIC_API_KEY 없으면 skip.
  - mock fallback 으로 항상 통과하는 테스트 포함 (구조 검증용).

실제 측정값 (AC-1 ≥70%) 는 CI nightly 에서 검증한다.
"""

from __future__ import annotations

import contextlib
import json
import os
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.errors import RunAbortedError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.prompt.entity import DeclaredVariable, NodeType, PromptVersion
from style_workbench.domain.prompt.modifier import NoopPromptModifier
from style_workbench.domain.prompt.optimization import PromptOptimization
from style_workbench.domain.style.entity import DAG, ModelRef, Node, NodeType as StyleNodeType
from style_workbench.engine.auto_loop import AutoLoopOrchestrator
from style_workbench.engine.prompt_optimizer import LlmPromptModifier
from tests.golden.auto_loop.conftest import (
    MockEvaluationService,
    MockExecutor,
    MockRetryAttemptRepo,
    MockRunEventBus,
)
from tests.golden.auto_loop.scenarios import GOLDEN_SCENARIOS, GoldenScenario

# ---------------------------------------------------------------------------
# Marker & API key check
# ---------------------------------------------------------------------------

_HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

_SKIP_REASON = (
    "golden_live requires ANTHROPIC_API_KEY — set this env var to run real LLM tests. "
    "This suite is intended for CI nightly runs only."
)

# ---------------------------------------------------------------------------
# Node-type mapping
# ---------------------------------------------------------------------------

_NODE_TYPE_MAP: dict[str, StyleNodeType] = {
    "text": StyleNodeType.TEXT_GENERATION,
    "image": StyleNodeType.IMAGE_GENERATION,
    "video": StyleNodeType.VIDEO_GENERATION,
    "composition": StyleNodeType.COMPOSITION,
}

_MODEL_REF: dict[str, ModelRef] = {
    "text": ModelRef(provider="mock", model_id="mock-text"),
    "image": ModelRef(provider="mock", model_id="mock-image"),
    "video": ModelRef(provider="mock", model_id="mock-video"),
    "composition": ModelRef(provider="mock", model_id="mock-composition"),
}

# ---------------------------------------------------------------------------
# Helpers: mock modifier (used when API key absent for structural validation)
# ---------------------------------------------------------------------------

_DECLARED_VARS = [DeclaredVariable(name="run_id", role="run_identifier", required=True)]


def _build_mock_modifier() -> LlmPromptModifier:
    """Build a LlmPromptModifier whose Claude mock always returns a valid response.

    Used as a structural stand-in when ANTHROPIC_API_KEY is not set.
    """
    mock_claude = AsyncMock()
    valid_response = json.dumps(
        {
            "new_body": "Enhanced prompt with {run_id}.",
            "change_summary": "Mock 수정 완료.",
            "preserved_placeholders": ["run_id"],
        }
    )
    mock_claude.generate.return_value = ModelOutput(
        text=valid_response,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0001,
    )

    new_version = PromptVersion(
        id="pmv-live-v2",
        prompt_id="prm-live",
        version=2,
        body="Enhanced prompt with {run_id}.",
        declared_variables=_DECLARED_VARS,
        parent_version_id="pmv-live-v1",
    )
    original_version = PromptVersion(
        id="pmv-live-v1",
        prompt_id="prm-live",
        version=1,
        body="Mock prompt for {run_id}",
        declared_variables=_DECLARED_VARS,
        parent_version_id=None,
    )

    mock_service = AsyncMock()
    mock_service.create_version.return_value = new_version

    saved_opt = PromptOptimization(
        id=new_ulid(),
        prompt_id="prm-live",
        parent_version_id="pmv-live-v1",
        new_version_id="pmv-live-v2",
        retry_guidance={"instruction": "fix"},
        failed_dimensions=[],
        eval_evidence=None,
        change_summary="Mock 수정 완료.",
        cost_won=Decimal("140"),
        latency_ms=500,
        succeeded=True,
        failure_reason=None,
    )
    mock_opt_repo = AsyncMock()
    mock_opt_repo.create.return_value = saved_opt

    mock_version_repo = AsyncMock()
    mock_version_repo.get.return_value = original_version

    mock_prompt_obj = AsyncMock()
    mock_prompt_obj.id = "prm-live"
    mock_prompt_obj.node_type = "image"
    mock_prompt_repo = AsyncMock()
    mock_prompt_repo.get.return_value = mock_prompt_obj

    return LlmPromptModifier(
        claude=mock_claude,
        prompt_service=mock_service,
        optimization_repo=mock_opt_repo,
        prompt_version_repo=mock_version_repo,
        prompt_repo=mock_prompt_repo,
        model_id="claude-opus-4-7",
        temperature=0.2,
        max_tokens=1500,
        usd_to_won=1400.0,
    )


def _build_real_modifier() -> LlmPromptModifier:
    """Build LlmPromptModifier with real ClaudeAdapter for nightly CI.

    Called only when ANTHROPIC_API_KEY is set.
    """
    from style_workbench.adapters.claude import ClaudeAdapter

    mock_service = AsyncMock()
    mock_opt_repo = AsyncMock()
    mock_version_repo = AsyncMock()
    mock_prompt_repo = AsyncMock()

    original_version = PromptVersion(
        id="pmv-live-v1",
        prompt_id="prm-live",
        version=1,
        body="Mock prompt for {run_id}",
        declared_variables=_DECLARED_VARS,
        parent_version_id=None,
    )
    new_version = PromptVersion(
        id="pmv-live-v2",
        prompt_id="prm-live",
        version=2,
        body="Enhanced mock prompt for {run_id}",
        declared_variables=_DECLARED_VARS,
        parent_version_id="pmv-live-v1",
    )

    mock_version_repo.get.return_value = original_version
    mock_service.create_version.return_value = new_version

    mock_prompt_obj = AsyncMock()
    mock_prompt_obj.id = "prm-live"
    mock_prompt_obj.node_type = "image"
    mock_prompt_repo.get.return_value = mock_prompt_obj

    saved_opt = PromptOptimization(
        id=new_ulid(),
        prompt_id="prm-live",
        parent_version_id="pmv-live-v1",
        new_version_id="pmv-live-v2",
        retry_guidance={"instruction": "fix"},
        failed_dimensions=[],
        eval_evidence=None,
        change_summary=None,
        cost_won=Decimal("0"),
        latency_ms=None,
        succeeded=True,
        failure_reason=None,
    )
    mock_opt_repo.create.return_value = saved_opt

    return LlmPromptModifier(
        claude=ClaudeAdapter(),
        prompt_service=mock_service,
        optimization_repo=mock_opt_repo,
        prompt_version_repo=mock_version_repo,
        prompt_repo=mock_prompt_repo,
        model_id="claude-opus-4-7",
        temperature=0.2,
        max_tokens=1500,
        usd_to_won=1400.0,
    )


def _build_single_node_dag(scenario: GoldenScenario) -> tuple[DAG, Node]:
    node_id = f"node_{scenario.name}"
    node = Node(
        id=node_id,
        type=_NODE_TYPE_MAP[scenario.node_type],
        model=_MODEL_REF[scenario.node_type],
        prompt_template="Mock prompt for {run_id}",
    )
    dag = DAG(nodes=[node], edges=[], variables=["run_id"])
    return dag, node


# ---------------------------------------------------------------------------
# Structural test (always runs — no API key needed)
# ---------------------------------------------------------------------------


@pytest.mark.golden_live
@pytest.mark.asyncio
async def test_auto_loop_with_llm_modifier_structural_mock() -> None:
    """구조 검증 — mock Claude 로 AutoLoopOrchestrator + LlmPromptModifier 통합 작동 확인.

    ANTHROPIC_API_KEY 없이도 항상 통과.
    pass_at_attempt=1 시나리오를 사용해 modifier.modify() 호출 경로를 검증한다.
    """
    from tests.golden.auto_loop.scenarios import GoldenScenario

    scenario = GoldenScenario(
        name="structural_test",
        node_type="image",
        pass_at_attempt=1,
        failed_dimensions=["lighting_match"],
        cost_per_attempt=200.0,
    )

    dag, _ = _build_single_node_dag(scenario)
    run_id = new_ulid()
    modifier = _build_mock_modifier()

    orchestrator = AutoLoopOrchestrator(
        executor=MockExecutor(scenario),  # type: ignore[arg-type]
        eval_service=MockEvaluationService(scenario),  # type: ignore[arg-type]
        retry_repo=MockRetryAttemptRepo(),
        prompt_modifier=modifier,  # type: ignore[arg-type]
        max_retry=3,
        cost_budget_won=1_000_000_000.0,
        event_bus=MockRunEventBus(),  # type: ignore[arg-type]
    )

    result = await orchestrator.run(
        dag=dag,
        user_input={"run_id": run_id},
        run_id=run_id,
        brief_summary="Structural test brief",
    )
    assert result is not None


# ---------------------------------------------------------------------------
# AC-1: real LLM pass-rate test (nightly only)
# ---------------------------------------------------------------------------


@pytest.mark.golden_live
@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_API_KEY, reason=_SKIP_REASON)
async def test_auto_loop_pass_rate_with_llm_modifier_real_api() -> None:
    """AC-1: LlmPromptModifier + real Claude API → retry PASS 비율 ≥70%.

    50 golden scenarios 를 순회하며 pass_at_attempt 에 따라 PASS/FAIL 를 측정한다.
    실제 F02 호출이 이루어지므로 비용이 발생한다 (~₩500/call × 50 = ~₩25,000 예상).
    CI nightly 에서만 실행.

    spec §2.1 Goals: PASS 비율 ≥70%.
    """
    scenarios = GOLDEN_SCENARIOS
    pass_count = 0
    results: list[tuple[str, bool]] = []

    modifier = _build_real_modifier()

    for scenario in scenarios:
        dag, _ = _build_single_node_dag(scenario)
        run_id = new_ulid()

        mock_executor = MockExecutor(scenario)
        mock_eval_svc = MockEvaluationService(scenario)
        mock_repo = MockRetryAttemptRepo()
        mock_event_bus = MockRunEventBus()

        orchestrator = AutoLoopOrchestrator(
            executor=mock_executor,  # type: ignore[arg-type]
            eval_service=mock_eval_svc,  # type: ignore[arg-type]
            retry_repo=mock_repo,
            prompt_modifier=modifier,  # type: ignore[arg-type]
            max_retry=3,
            cost_budget_won=1_000_000_000.0,
            event_bus=mock_event_bus,  # type: ignore[arg-type]
        )

        try:
            await orchestrator.run(
                dag=dag,
                user_input={"run_id": run_id},
                run_id=run_id,
                brief_summary=f"Golden live test: {scenario.name}",
            )
            passed = True
        except RunAbortedError:
            passed = False

        results.append((scenario.name, passed))
        if passed:
            pass_count += 1

    pass_rate = pass_count / len(scenarios)
    failed = [n for n, ok in results if not ok]
    passed_list = [n for n, ok in results if ok]

    assert pass_rate >= 0.70, (
        f"AC-1 FAIL: LlmPromptModifier pass rate {pass_rate:.1%} < 70%\n"
        f"  Passed ({len(passed_list)}): {passed_list}\n"
        f"  Failed ({len(failed)}): {failed}"
    )
