"""Per-process, per-event-loop admission control for expensive research tasks."""
import asyncio
import weakref

class TaskCapacity:
    def __init__(self, limit=5):
        if limit < 1:
            raise ValueError('limit must be positive')
        self.limit = limit
        self._semaphores = weakref.WeakKeyDictionary()

    def _semaphore(self):
        loop = asyncio.get_running_loop()
        if loop not in self._semaphores:
            self._semaphores[loop] = asyncio.Semaphore(self.limit)
        return self._semaphores[loop]

    async def run(self, factory):
        async with self._semaphore():
            return await factory()
