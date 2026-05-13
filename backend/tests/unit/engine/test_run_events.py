from __future__ import annotations

import asyncio

import pytest

from style_workbench.engine.run_events import RunEvent, RunEventBus

# ---------------------------------------------------------------------------
# 기본 pub/sub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber() -> None:
    bus = RunEventBus()
    received: list[RunEvent] = []

    async def consumer() -> None:
        async for event in bus.subscribe("run-1"):
            received.append(event)

    task = asyncio.create_task(consumer())
    # 구독자가 큐를 등록할 시간을 준다
    await asyncio.sleep(0)

    event = RunEvent(run_id="run-1", event_type="node_started", payload={"node_id": "n1"})
    await bus.publish(event)
    bus.close_run("run-1")

    await asyncio.wait_for(task, timeout=2.0)
    assert received == [event]


@pytest.mark.asyncio
async def test_publish_delivers_multiple_events_in_order() -> None:
    bus = RunEventBus()
    received: list[RunEvent] = []

    async def consumer() -> None:
        async for event in bus.subscribe("run-2"):
            received.append(event)

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)

    events = [
        RunEvent(run_id="run-2", event_type="node_started", payload={"node_id": "n1"}),
        RunEvent(run_id="run-2", event_type="node_completed", payload={"node_id": "n1"}),
        RunEvent(run_id="run-2", event_type="run_completed", payload={}),
    ]
    for e in events:
        await bus.publish(e)
    bus.close_run("run-2")

    await asyncio.wait_for(task, timeout=2.0)
    assert received == events


@pytest.mark.asyncio
async def test_publish_to_multiple_subscribers() -> None:
    bus = RunEventBus()
    results: dict[str, list[RunEvent]] = {"a": [], "b": []}

    async def consumer(key: str) -> None:
        async for event in bus.subscribe("run-3"):
            results[key].append(event)

    task_a = asyncio.create_task(consumer("a"))
    task_b = asyncio.create_task(consumer("b"))
    await asyncio.sleep(0)

    event = RunEvent(run_id="run-3", event_type="node_started", payload={"node_id": "n1"})
    await bus.publish(event)
    bus.close_run("run-3")

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=2.0)
    assert results["a"] == [event]
    assert results["b"] == [event]


@pytest.mark.asyncio
async def test_publish_ignored_if_no_subscriber() -> None:
    """구독자가 없을 때 publish는 예외 없이 통과해야 한다."""
    bus = RunEventBus()
    event = RunEvent(run_id="run-unknown", event_type="run_completed", payload={})
    # 예외가 발생하지 않으면 성공
    await bus.publish(event)


# ---------------------------------------------------------------------------
# close_run / 구독 해제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_run_terminates_subscriber() -> None:
    bus = RunEventBus()
    finished = asyncio.Event()

    async def consumer() -> None:
        async for _ in bus.subscribe("run-4"):
            pass
        finished.set()

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)

    bus.close_run("run-4")
    await asyncio.wait_for(task, timeout=2.0)
    assert finished.is_set()


@pytest.mark.asyncio
async def test_queue_cleaned_up_after_subscribe_ends() -> None:
    bus = RunEventBus()

    async def consumer() -> None:
        async for _ in bus.subscribe("run-5"):
            pass

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)
    bus.close_run("run-5")
    await asyncio.wait_for(task, timeout=2.0)

    # run-5 관련 큐가 완전히 정리되어야 한다
    assert "run-5" not in bus._queues


# ---------------------------------------------------------------------------
# 다른 run_id 간 격리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_isolated_by_run_id() -> None:
    bus = RunEventBus()
    received_a: list[RunEvent] = []
    received_b: list[RunEvent] = []

    async def consumer_a() -> None:
        async for event in bus.subscribe("run-a"):
            received_a.append(event)

    async def consumer_b() -> None:
        async for event in bus.subscribe("run-b"):
            received_b.append(event)

    task_a = asyncio.create_task(consumer_a())
    task_b = asyncio.create_task(consumer_b())
    await asyncio.sleep(0)

    await bus.publish(RunEvent(run_id="run-a", event_type="run_completed", payload={}))
    bus.close_run("run-a")
    bus.close_run("run-b")

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=2.0)

    assert len(received_a) == 1
    assert received_b == []
