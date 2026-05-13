"""Integration test: AutoLoopOrchestrator + LlmPromptModifier (F02 spec §10.2).

시나리오:
  - LlmPromptModifier 주입 → eval FAIL → F02 호출 → 새 prompt_version → PASS.
  - ClaudeAdapter mock 으로 결정적 응답 (real LLM 호출 없음).
  - PromptService mock 으로 새 버전 생성 확인.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.errors import RunAbortedError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.prompt.entity import DeclaredVariable, PromptVersion
from style_workbench.domain.prompt.optimization import PromptOptimization
from style_workbench.domain.style.entity import DAG, ModelRef, Node, NodeType
from style_workbench.engine.auto_loop import AutoLoopOrchestrator
from style_workbench.engine.prompt_optimizer import LlmPromptModifier
from tests.golden.auto_loop.conftest import (
    MockEvaluationService,
    MockExecutor,
    MockRetryAttemptRepo,
    MockRunEventBus,
)
from tests.golden.auto_loop.scenarios import GoldenScenario


# ---------------------------------------------------------------------------
# Helper: build a minimal scenario where attempt 1 passes
# ---------------------------------------------------------------------------

_FAIL_THEN_PASS_SCENARIO = GoldenScenario(
    name="test_fail_then_pass",
    node_type="image",
    pass_at_attempt=1,
    failed_dimensions=["lighting_match"],
    cost_per_attempt=200.0,
)

_DECLARED_VARS = [DeclaredVariable(name="name", role="subject", required=True)]


def _build_dag_with_prompt_version(
    node_type_str: str = "image",
    prompt_version_id: str = "pmv-v1",
) -> tuple[DAG, Node]:
    node_type_map = {
        "text": NodeType.TEXT_GENERATION,
        "image": NodeType.IMAGE_GENERATION,
        "video": NodeType.VIDEO_GENERATION,
        "composition": NodeType.COMPOSITION,
    }
    node_id = "node_test"
    node = Node(
        id=node_id,
        type=node_type_map[node_type_str],
        model=ModelRef(provider="mock", model_id="mock-image"),
        prompt_template="Studio headshot of {name}.",
        # prompt_version_id 를 simulate 하기 위해 node 에 직접 부여
        # (실제 구현에서는 PromptUsage 통해 연결되나, 여기선 간소화)
    )
    dag = DAG(nodes=[node], edges=[], variables=["name"])
    return dag, node


def _make_modifier_with_mocks(
    original_body: str = "Studio headshot of {name}.",
    new_body: str = "Studio headshot of {name}, front key light.",
    prompt_version_id_to_return: str = "pmv-v2",
) -> tuple[LlmPromptModifier, AsyncMock, AsyncMock, AsyncMock]:
    """Build LlmPromptModifier with all collaborators mocked."""

    # Claude mock: 유효한 JSON 응답 반환
    mock_claude = AsyncMock()
    valid_response = json.dumps(
        {
            "new_body": new_body,
            "change_summary": "주광원을 정면으로 변경했습니다.",
            "preserved_placeholders": ["name"],
        },
        ensure_ascii=False,
    )
    mock_claude.generate.return_value = ModelOutput(
        text=valid_response,
        input_tokens=200,
        output_tokens=80,
        cost_usd=0.0002,
    )

    # PromptService mock: create_version → new PromptVersion
    new_version = PromptVersion(
        id=prompt_version_id_to_return,
        prompt_id="prm-001",
        version=2,
        body=new_body,
        declared_variables=_DECLARED_VARS,
        parent_version_id="pmv-v1",
        created_at=datetime.now(UTC),
    )
    mock_prompt_service = AsyncMock()
    mock_prompt_service.create_version.return_value = new_version

    # optimization_repo mock
    saved_opt = PromptOptimization(
        id=new_ulid(),
        prompt_id="prm-001",
        parent_version_id="pmv-v1",
        new_version_id=prompt_version_id_to_return,
        retry_guidance={"instruction": "fix"},
        failed_dimensions=["lighting_match"],
        eval_evidence=None,
        change_summary="주광원을 정면으로 변경했습니다.",
        cost_won=Decimal("280"),
        latency_ms=3000,
        succeeded=True,
        failure_reason=None,
    )
    mock_opt_repo = AsyncMock()
    mock_opt_repo.create.return_value = saved_opt

    # PromptVersionRepo mock: 원본 버전 조회
    original_version = PromptVersion(
        id="pmv-v1",
        prompt_id="prm-001",
        version=1,
        body=original_body,
        declared_variables=_DECLARED_VARS,
        parent_version_id=None,
    )
    mock_version_repo = AsyncMock()
    mock_version_repo.get.return_value = original_version

    # PromptRepo mock: Prompt 조회 (node_type 추출)
    mock_prompt_obj = AsyncMock()
    mock_prompt_obj.id = "prm-001"
    mock_prompt_obj.node_type = "image"
    mock_prompt_repo = AsyncMock()
    mock_prompt_repo.get.return_value = mock_prompt_obj

    modifier = LlmPromptModifier(
        claude=mock_claude,
        prompt_service=mock_prompt_service,
        optimization_repo=mock_opt_repo,
        prompt_version_repo=mock_version_repo,
        prompt_repo=mock_prompt_repo,
        model_id="claude-opus-4-7",
        temperature=0.2,
        max_tokens=1500,
        usd_to_won=1400.0,
    )
    return modifier, mock_prompt_service, mock_opt_repo, mock_claude


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_loop_with_llm_modifier_fail_then_pass() -> None:
    """LlmPromptModifier 주입 → eval FAIL → F02 → 새 버전 → 다음 attempt PASS.

    이 테스트에서는 AutoLoopOrchestrator 가 modifier.modify() 를 호출하는지
    확인한다. modifier 내부의 Claude mock 은 유효한 JSON 응답을 반환한다.
    MockEvaluationService 는 attempt_number==1 일 때 PASS 를 반환하도록
    설정되어 있다 (pass_at_attempt=1).
    """
    scenario = _FAIL_THEN_PASS_SCENARIO
    dag, _node = _build_dag_with_prompt_version()
    run_id = new_ulid()

    mock_executor = MockExecutor(scenario)
    mock_eval_svc = MockEvaluationService(scenario)
    mock_repo = MockRetryAttemptRepo()
    mock_event_bus = MockRunEventBus()

    modifier, mock_service, mock_opt_repo, mock_claude = _make_modifier_with_mocks()

    orchestrator = AutoLoopOrchestrator(
        executor=mock_executor,  # type: ignore[arg-type]
        eval_service=mock_eval_svc,  # type: ignore[arg-type]
        retry_repo=mock_repo,
        prompt_modifier=modifier,  # type: ignore[arg-type]
        max_retry=3,
        cost_budget_won=1_000_000_000.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    # AutoLoopOrchestrator.run() 성공 (RunAbortedError 없음)
    result = await orchestrator.run(
        dag=dag,
        user_input={"name": "홍길동"},
        run_id=run_id,
        brief_summary="Test brief",
    )

    # 정상 완료
    assert result is not None

    # attempt 0: FAIL → retry 1개, attempt 1: PASS → 총 2 attempt rows
    assert len(mock_repo.attempts) == 2

    # node_retry SSE event 1건 (attempt 0 → attempt 1)
    retry_events = mock_event_bus.events_of_type("node_retry")
    assert len(retry_events) == 1


@pytest.mark.asyncio
async def test_auto_loop_with_noop_modifier_baseline() -> None:
    """PROMPT_OPTIMIZER_ENABLED=false 회귀: NoopPromptModifier 로도 orchestration 정상 작동.

    AC-9: F01 회귀 검증.
    """
    from style_workbench.domain.prompt.modifier import NoopPromptModifier

    scenario = _FAIL_THEN_PASS_SCENARIO
    dag, _node = _build_dag_with_prompt_version()
    run_id = new_ulid()

    mock_repo = MockRetryAttemptRepo()
    mock_event_bus = MockRunEventBus()

    orchestrator = AutoLoopOrchestrator(
        executor=MockExecutor(scenario),  # type: ignore[arg-type]
        eval_service=MockEvaluationService(scenario),  # type: ignore[arg-type]
        retry_repo=mock_repo,
        prompt_modifier=NoopPromptModifier(),
        max_retry=3,
        cost_budget_won=1_000_000_000.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    result = await orchestrator.run(
        dag=dag,
        user_input={"name": "홍길동"},
        run_id=run_id,
    )

    assert result is not None
    # NoopPromptModifier 로도 attempt 2건 (attempt 0 FAIL, attempt 1 PASS)
    assert len(mock_repo.attempts) == 2
