"""Runtime supervision primitives for the refactored application bootstrap."""

from __future__ import annotations

import asyncio

ServiceContainer = dict[str, object]


class RuntimeSupervisor:
    """Manage the lifecycle of background runtime tasks.

    Later extraction tasks will register WebSocket/account tasks here instead of
    storing them as legacy module-level globals.
    """

    def __init__(self, container: ServiceContainer) -> None:
        self._container: ServiceContainer = container
        self._tasks: list[asyncio.Task[object]] = []
        self._running: bool = False

    @property
    def running(self) -> bool:
        """Whether the supervisor is currently marked as running."""

        return self._running

    def register_task(self, task: asyncio.Task[object]) -> asyncio.Task[object]:
        """Track a background task for later coordinated shutdown."""

        self._tasks.append(task)
        return task

    async def start(self) -> None:
        """Start registered runtime services.

        Actual service startup is deferred to later cleanup tasks.
        """

        self._running = True

    async def stop(self) -> None:
        """Stop tracked runtime services gracefully."""

        self._running = False
        for task in self._tasks:
            _ = task.cancel()
        if self._tasks:
            _ = await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


__all__ = ["RuntimeSupervisor", "ServiceContainer"]
