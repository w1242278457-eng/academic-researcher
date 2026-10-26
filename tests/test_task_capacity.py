import asyncio

import pytest

from backend.server.task_capacity import TaskCapacity


def test_capacity_limits_running_tasks():
    async def scenario():
        capacity = TaskCapacity(3)
        active = peak = 0

        async def work():
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0)
            finally:
                active -= 1

        await asyncio.gather(*(capacity.run(work) for _ in range(12)))
        assert peak == 3
        assert active == 0

    asyncio.run(scenario())


def test_cancellation_releases_capacity_to_queued_task():
    async def scenario():
        capacity = TaskCapacity(1)
        started = asyncio.Event()
        blocker = asyncio.Event()

        async def running():
            started.set()
            await blocker.wait()

        async def next_work():
            return 'next task entered'

        first = asyncio.create_task(capacity.run(running))
        await asyncio.wait_for(started.wait(), 1)
        queued = asyncio.create_task(capacity.run(next_work))
        await asyncio.sleep(0)
        assert not queued.done()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await asyncio.wait_for(queued, 1) == 'next task entered'

    asyncio.run(scenario())


def test_capacity_can_be_used_across_sequential_event_loops():
    capacity = TaskCapacity(1)

    async def run():
        async def work():
            await asyncio.sleep(0)
            return 1
        return await asyncio.gather(capacity.run(work), capacity.run(work))

    assert asyncio.run(run()) == [1, 1]
    assert asyncio.run(run()) == [1, 1]


def test_invalid_capacity_fails_early():
    with pytest.raises(ValueError):
        TaskCapacity(0)
