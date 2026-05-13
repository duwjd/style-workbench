"""Unit tests for SqlAlchemyEvaluationRepository.

DB 연결 없이 AsyncMock session 으로 구현을 검증한다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.infra.repositories.evaluation_repo import (
    EvaluationRecord,
    SqlAlchemyEvaluationRepository,
)


def _make_orm_evaluation(
    id: str = "eval-1",
    node_execution_id: str = "ne-1",
    evaluator_model: str = "claude-opus-4-6",
    overall_result: str = "passed",
    dimensions: list[dict[str, Any]] | None = None,
    retry_guidance: dict[str, Any] | None = None,
    failed_dimensions: list[str] | None = None,
    human_verdict: str | None = None,
    human_comment: str | None = None,
) -> MagicMock:
    orm = MagicMock()
    orm.id = id
    orm.node_execution_id = node_execution_id
    orm.evaluator_model = evaluator_model
    orm.overall_result = overall_result
    orm.dimensions = dimensions or [{"name": "tone_match", "score": 0.9, "rationale": "Good"}]
    orm.retry_guidance = retry_guidance
    orm.failed_dimensions = failed_dimensions or []
    orm.human_verdict = human_verdict
    orm.human_comment = human_comment
    orm.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    return orm


def _make_result(
    id: str = "eval-1",
    node_execution_id: str = "ne-1",
    passed: bool = True,
) -> EvaluationResult:
    score = 0.9 if passed else 0.5
    return EvaluationResult(
        id=id,
        node_execution_id=node_execution_id,
        evaluator_model="claude-opus-4-6",
        dimensions=[DimensionScore(name="tone_match", score=score, rationale="ok")],
        notable_issues=[],
        retry_guidance=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> SqlAlchemyEvaluationRepository:
    return SqlAlchemyEvaluationRepository(mock_session)


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_adds_orm_and_flushes(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    result = _make_result()
    await repo.save(result)

    mock_session.add.assert_called_once()
    orm_added = mock_session.add.call_args[0][0]
    assert orm_added.id == "eval-1"
    assert orm_added.node_execution_id == "ne-1"
    assert orm_added.overall_result == "passed"
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_failed_result(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    result = _make_result(passed=False)
    await repo.save(result)

    orm_added = mock_session.add.call_args[0][0]
    assert orm_added.overall_result == "failed"


# ---------------------------------------------------------------------------
# FR-5: retry_guidance JSONB 저장/조회 회귀 (단계 2 신규)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_retry_guidance_jsonb_stored(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    """retry_guidance가 dict[str, Any]로 ORM에 전달되는지 검증 (JSONB 저장 회귀)."""
    guidance: dict[str, Any] = {"instruction": "fix composition", "confidence": 0.82}
    result = EvaluationResult(
        id="eval-guid-1",
        node_execution_id="ne-guid-1",
        evaluator_model="claude-opus-4-6",
        dimensions=[DimensionScore(name="composition", score=0.5, rationale="off-center")],
        notable_issues=[],
        retry_guidance=guidance,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    await repo.save(result)

    orm_added = mock_session.add.call_args[0][0]
    # retry_guidance must be a dict, not a string
    assert isinstance(orm_added.retry_guidance, dict)
    assert orm_added.retry_guidance["instruction"] == "fix composition"
    assert orm_added.retry_guidance["confidence"] == 0.82


@pytest.mark.asyncio
async def test_save_retry_guidance_null_when_passed(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    """PASS 시 retry_guidance는 None이어야 한다 (PASS 시 NULL)."""
    result = _make_result(passed=True)
    # _make_result uses None for retry_guidance by default
    await repo.save(result)

    orm_added = mock_session.add.call_args[0][0]
    assert orm_added.retry_guidance is None


# ---------------------------------------------------------------------------
# FR-5: failed_dimensions JSONB 저장/조회 회귀 (단계 2 신규)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_failed_dimensions_jsonb_stored(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    """failed_dimensions가 list[str]로 ORM에 전달되는지 검증 (JSONB 저장 회귀)."""
    result = EvaluationResult(
        id="eval-dim-1",
        node_execution_id="ne-dim-1",
        evaluator_model="claude-opus-4-6",
        dimensions=[
            DimensionScore(name="composition", score=0.4, rationale="poor"),
            DimensionScore(name="lighting", score=0.5, rationale="dim"),
        ],
        notable_issues=[],
        retry_guidance={"instruction": "fix lighting"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    await repo.save(result)

    orm_added = mock_session.add.call_args[0][0]
    # failed_dimensions is computed from entity.failed_dimensions property
    assert isinstance(orm_added.failed_dimensions, list)
    assert "composition" in orm_added.failed_dimensions
    assert "lighting" in orm_added.failed_dimensions


@pytest.mark.asyncio
async def test_list_by_run_record_has_failed_dimensions(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    """list_by_run 결과 EvaluationRecord에 failed_dimensions가 포함되는지 검증."""
    orm_eval = _make_orm_evaluation(
        overall_result="failed",
        failed_dimensions=["composition", "lighting"],
        retry_guidance={"instruction": "fix it"},
    )
    row = MagicMock()
    row.tuple.return_value = (orm_eval, "node-abc", "image_generation")
    mock_result = MagicMock()
    mock_result.all.return_value = [row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    records = await repo.list_by_run("run-1")

    assert len(records) == 1
    rec = records[0]
    assert rec.failed_dimensions == ["composition", "lighting"]
    assert isinstance(rec.retry_guidance, dict)
    assert rec.retry_guidance["instruction"] == "fix it"


# ---------------------------------------------------------------------------
# get_by_node_execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_node_execution_returns_entities(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    orm_eval = _make_orm_evaluation()
    # execute() 는 await 대상이지만 결과 객체의 .scalars(), .all() 은 동기 → MagicMock 사용
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [orm_eval]
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await repo.get_by_node_execution("ne-1")

    assert len(results) == 1
    assert results[0].id == "eval-1"
    assert results[0].node_execution_id == "ne-1"
    assert isinstance(results[0], EvaluationResult)


@pytest.mark.asyncio
async def test_get_by_node_execution_empty(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await repo.get_by_node_execution("ne-nonexistent")
    assert results == []


# ---------------------------------------------------------------------------
# list_by_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_by_run_returns_records(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    orm_eval = _make_orm_evaluation()
    # list_by_run 은 JOIN row tuple (Evaluation, node_id, node_type)
    row = MagicMock()
    row.tuple.return_value = (orm_eval, "node-abc", "text_generation")
    mock_result = MagicMock()
    mock_result.all.return_value = [row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    records = await repo.list_by_run("run-1")

    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, EvaluationRecord)
    assert rec.id == "eval-1"
    assert rec.node_id == "node-abc"
    assert rec.node_type == "text_generation"


@pytest.mark.asyncio
async def test_list_by_run_empty(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    records = await repo.list_by_run("run-no-evals")
    assert records == []


# ---------------------------------------------------------------------------
# update_human_verdict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_human_verdict_returns_record(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    orm_eval = _make_orm_evaluation()

    # First execute: SELECT Evaluation by id
    # Second execute (get_record_by_id): SELECT with JOIN
    row_for_record = MagicMock()
    row_for_record.tuple.return_value = (orm_eval, "node-abc", "text_generation")

    execute_results: list[Any] = []

    async def mock_execute_side_effect(stmt: Any) -> Any:
        result = MagicMock()
        if len(execute_results) == 0:
            # First call: SELECT Evaluation WHERE id = ?
            result.scalar_one_or_none.return_value = orm_eval
        else:
            # Second call: SELECT Evaluation JOIN NodeExecution WHERE id = ?
            result.first.return_value = row_for_record
        execute_results.append(True)
        return result

    mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

    record = await repo.update_human_verdict("eval-1", "approved", "Looks good")

    assert record is not None
    assert record.id == "eval-1"
    # orm 객체의 human_verdict 가 갱신됐는지 확인
    assert orm_eval.human_verdict == "approved"
    assert orm_eval.human_comment == "Looks good"
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_human_verdict_not_found_returns_none(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    record = await repo.update_human_verdict("nonexistent", "approved", None)
    assert record is None


# ---------------------------------------------------------------------------
# timezone 보정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_node_execution_naive_datetime_gets_utc(
    repo: SqlAlchemyEvaluationRepository,
    mock_session: AsyncMock,
) -> None:
    orm_eval = _make_orm_evaluation()
    orm_eval.created_at = datetime(2026, 1, 1)  # naive (no tzinfo)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [orm_eval]
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await repo.get_by_node_execution("ne-1")
    assert results[0].created_at.tzinfo is not None
