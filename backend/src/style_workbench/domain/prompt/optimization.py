"""Domain entity for F02 Prompt Optimization records.

spec §5.1 prompt_optimizations 테이블에 1:1 매핑.

외부 의존성 0건 — domain layer 순수 코드 (CLAUDE.md §2.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass
class PromptOptimization:
    """F02 Prompt Optimizer 호출 1건의 결과 기록.

    spec §5.1 prompt_optimizations 테이블에 1:1 매핑.
    성공 여부와 무관하게 모든 F02 호출이 row 1건을 생성한다 (FR-6, AC-4).
    """

    id: str  # ULID
    prompt_id: str
    parent_version_id: str
    new_version_id: str | None  # None when succeeded=False
    retry_guidance: dict[str, Any]
    failed_dimensions: list[str]
    eval_evidence: dict[str, str] | None  # {evaluation_id, run_id, node_execution_id}
    change_summary: str | None
    cost_won: Decimal
    latency_ms: int | None
    succeeded: bool
    failure_reason: str | None  # succeeded=False 시 사유
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Repository Protocol (domain/prompt/repo.py 와 같은 패턴)
# ---------------------------------------------------------------------------


class PromptOptimizationRepo(Protocol):
    """F02 optimization 기록의 저장/조회 인터페이스.

    인터페이스(Protocol) 는 domain 레이어에, 구현(SQLAlchemy)은
    infra/repositories/prompt_optimization_repo.py 에 위치한다.
    """

    async def create(self, opt: PromptOptimization) -> PromptOptimization:
        """Insert a new PromptOptimization row and return it with DB-assigned timestamps."""
        ...

    async def list_for_prompt(
        self, prompt_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[PromptOptimization], int]:
        """Return (items, total) for the given prompt, ordered by created_at DESC.

        Used by GET /api/prompts/{id}/optimizations.
        """
        ...

    async def get(self, optimization_id: str) -> PromptOptimization | None:
        """Return a PromptOptimization by its id, or None if not found."""
        ...
