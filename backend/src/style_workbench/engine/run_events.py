from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

RunEventType = Literal[
    "node_started",
    "node_completed",
    "node_failed",
    "node_retry",
    "run_completed",
    "run_failed",
    "run_aborted",
    "run_budget_exceeded",
]


@dataclass(frozen=True)
class RunEvent:
    """Immutable value object representing a run lifecycle event."""

    run_id: str
    event_type: RunEventType
    payload: dict[str, object]


class RunEventBus:
    """In-process asyncio pub/sub for run lifecycle events.

    Phase 1 단순 구현: run_id별 asyncio.Queue 리스트로 subscriber 라우팅.
    Phase 2에서 Redis pub/sub으로 교체 가능하도록 인터페이스 일관성 유지.

    Notes:
        - worker 프로세스가 단 1개일 때만 정상 동작 (Phase 1 OK).
        - 여러 워커로 확장 시 Redis pub/sub으로 교체한다.
    """

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue[RunEvent | None]]] = {}

    async def publish(self, event: RunEvent) -> None:
        """해당 run_id를 구독 중인 모든 큐에 이벤트를 enqueue한다.

        best-effort: 발행 실패는 run 자체를 중단하지 않는다.
        """
        subscribers = self._queues.get(event.run_id, [])
        for q in list(subscribers):
            try:
                await q.put(event)
            except Exception:
                logger.exception(
                    "event_bus_publish_error",
                    run_id=event.run_id,
                    event_type=event.event_type,
                )

    async def subscribe(self, run_id: str) -> AsyncIterator[RunEvent]:
        """run_id에 대한 이벤트 스트림을 반환한다.

        구독 시작 시 새 Queue를 등록하고, 스트림 종료 시(정상/예외 모두)
        finally 블록에서 Queue를 제거한다.
        """
        queue: asyncio.Queue[RunEvent | None] = asyncio.Queue()
        self._queues.setdefault(run_id, []).append(queue)
        logger.debug("event_bus_subscribe", run_id=run_id)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    # sentinel: 더 이상 이벤트가 없음을 알린다
                    break
                yield event
        finally:
            self._remove_queue(run_id, queue)
            logger.debug("event_bus_unsubscribe", run_id=run_id)

    def close_run(self, run_id: str) -> None:
        """run_id의 모든 구독 큐에 sentinel(None)을 전송해 스트림을 닫는다.

        이 메서드는 동기 컨텍스트에서도 호출될 수 있으므로 asyncio.Queue.put_nowait을 사용한다.
        """
        for q in list(self._queues.get(run_id, [])):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                logger.warning("event_bus_close_queue_full", run_id=run_id)

    def _remove_queue(self, run_id: str, queue: asyncio.Queue[RunEvent | None]) -> None:
        subscribers = self._queues.get(run_id)
        if subscribers is None:
            return
        with contextlib.suppress(ValueError):
            subscribers.remove(queue)
        if not subscribers:
            self._queues.pop(run_id, None)
