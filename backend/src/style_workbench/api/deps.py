from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.adapters.claude import ClaudeAdapter
from style_workbench.core.config import settings
from style_workbench.domain.prompt.modifier import NoopPromptModifier
from style_workbench.engine.prompt_optimizer import LlmPromptModifier
from style_workbench.engine.run_events import RunEventBus
from style_workbench.infra.db.session import get_db
from style_workbench.infra.repositories.evaluation_repo import SqlAlchemyEvaluationRepository
from style_workbench.infra.repositories.prompt_optimization_repo import (
    SqlAlchemyPromptOptimizationRepo,
)
from style_workbench.infra.repositories.prompt_repo import (
    SqlAlchemyPromptAbComparisonRepo,
    SqlAlchemyPromptRepo,
    SqlAlchemyPromptUsageRepo,
    SqlAlchemyPromptVersionRepo,
)
from style_workbench.infra.repositories.retry_attempt_repo import SqlAlchemyRetryAttemptRepo
from style_workbench.infra.repositories.run_repo import SqlAlchemyRunRepository
from style_workbench.infra.repositories.style_repo import SqlAlchemyStyleRepository
from style_workbench.services.evaluation_service import EvaluationService
from style_workbench.services.prompt_service import PromptService
from style_workbench.services.run_service import RunService
from style_workbench.services.style_service import StyleService
from style_workbench.services.variant_service import VariantService

DbSession = Annotated[AsyncSession, Depends(get_db)]


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    """앱 lifespan 동안 단일 RunEventBus 인스턴스를 반환한다.

    Phase 1: in-process, 단일 워커. Phase 2에서 Redis pub/sub으로 교체 시
    이 함수만 수정하면 된다.
    """
    return RunEventBus()


def get_style_service(session: DbSession) -> StyleService:
    return StyleService(repo=SqlAlchemyStyleRepository(session))


def get_variant_service(session: DbSession) -> VariantService:
    return VariantService(repo=SqlAlchemyStyleRepository(session))


def get_evaluation_repo(session: DbSession) -> SqlAlchemyEvaluationRepository:
    return SqlAlchemyEvaluationRepository(session)


def get_evaluation_service(session: DbSession) -> EvaluationService:
    return EvaluationService(
        run_repo=SqlAlchemyRunRepository(session),
        eval_repo=SqlAlchemyEvaluationRepository(session),
        claude_adapter=ClaudeAdapter(),
    )


def get_prompt_service(session: DbSession) -> PromptService:
    """DI factory for PromptService (F05 Prompt Library).

    Wires the four repository implementations that share the same AsyncSession.
    PromptService.__init__ does not take a session argument — transaction commit
    is the caller's (route handler's) responsibility.
    """
    return PromptService(
        prompt_repo=SqlAlchemyPromptRepo(session),
        version_repo=SqlAlchemyPromptVersionRepo(session),
        usage_repo=SqlAlchemyPromptUsageRepo(session),
        ab_repo=SqlAlchemyPromptAbComparisonRepo(session),
    )


def get_prompt_optimization_repo(session: DbSession) -> SqlAlchemyPromptOptimizationRepo:
    """DI factory for SqlAlchemyPromptOptimizationRepo (F02)."""
    return SqlAlchemyPromptOptimizationRepo(session)


def get_prompt_optimizer(session: DbSession) -> LlmPromptModifier:
    """DI factory for LlmPromptModifier (F02 Prompt Optimizer).

    spec §4 FR-8: PROMPT_OPTIMIZER_ENABLED=false → NoopPromptModifier 로 fallback.
    이 함수에서는 항상 LlmPromptModifier 인스턴스를 반환한다.
    RunService 주입 시에만 PROMPT_OPTIMIZER_ENABLED 를 체크한다.
    """
    return LlmPromptModifier(
        claude=ClaudeAdapter(),
        prompt_service=get_prompt_service(session),
        optimization_repo=SqlAlchemyPromptOptimizationRepo(session),
        prompt_version_repo=SqlAlchemyPromptVersionRepo(session),
        prompt_repo=SqlAlchemyPromptRepo(session),
        model_id=settings.prompt_optimizer_model,
    )


def get_retry_attempt_repo(session: DbSession) -> SqlAlchemyRetryAttemptRepo:
    """DI factory for SqlAlchemyRetryAttemptRepo (F01 retry-attempts endpoint)."""
    return SqlAlchemyRetryAttemptRepo(session)


def get_run_service(
    session: DbSession,
    bus: RunEventBus = Depends(get_event_bus),
    eval_service: EvaluationService = Depends(get_evaluation_service),
) -> RunService:
    """DI factory for RunService.

    spec §4 FR-8: PROMPT_OPTIMIZER_ENABLED=true (default) → LlmPromptModifier 주입.
    PROMPT_OPTIMIZER_ENABLED=false → NoopPromptModifier fallback (AC-9 F01 회귀 보호).
    """
    if settings.prompt_optimizer_enabled:
        prompt_modifier: LlmPromptModifier | NoopPromptModifier = LlmPromptModifier(
            claude=ClaudeAdapter(),
            prompt_service=get_prompt_service(session),
            optimization_repo=SqlAlchemyPromptOptimizationRepo(session),
            prompt_version_repo=SqlAlchemyPromptVersionRepo(session),
            prompt_repo=SqlAlchemyPromptRepo(session),
            model_id=settings.prompt_optimizer_model,
        )
    else:
        prompt_modifier = NoopPromptModifier()

    return RunService(
        style_repo=SqlAlchemyStyleRepository(session),
        run_repo=SqlAlchemyRunRepository(session),
        session=session,
        eval_service=eval_service,
        event_bus=bus,
        retry_repo=SqlAlchemyRetryAttemptRepo(session),
        prompt_modifier=prompt_modifier,
        max_retry=3,
    )
