"""In-process pub/sub for attempt progress, bridging the worker thread to SSE responses."""

import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, attempt_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[attempt_id].add(q)
        return q

    def unsubscribe(self, attempt_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(attempt_id)
        if subs:
            subs.discard(q)
            if not subs:
                del self._subs[attempt_id]

    def publish(self, attempt_id: int, event: dict) -> None:
        """Thread-safe: called from the worker thread."""
        if self._loop is None:
            return

        def deliver():
            for q in list(self._subs.get(attempt_id, ())):
                q.put_nowait(event)

        self._loop.call_soon_threadsafe(deliver)


bus = EventBus()
