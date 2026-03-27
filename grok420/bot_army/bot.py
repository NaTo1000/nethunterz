"""Bot — individual worker unit in the Grok 420 bot army."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class BotStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    RECOVERING = "recovering"
    TERMINATED = "terminated"


@dataclass
class BotConfig:
    """Per-bot configuration."""

    hardware_class: str = "cpu"
    inference_concurrency: int = 1
    bandwidth_priority: float = 0.5  # 0.0 (low) – 1.0 (high)
    model_id: str | None = None
    max_retries: int = 3


class Bot:
    """A single bot worker that executes tasks assigned by the army.

    Features
    --------
    * Self-healing: failed tasks trigger automatic retry.
    * Per-bot concurrency via asyncio Semaphore.
    * Task queue for ordered execution.
    * Heartbeat emission for health monitoring.
    """

    def __init__(self, config: BotConfig | None = None) -> None:
        self.bot_id = str(uuid.uuid4())
        self._config = config or BotConfig()
        self._status = BotStatus.IDLE
        self._semaphore = asyncio.Semaphore(self._config.inference_concurrency)
        self._task_queue: asyncio.Queue[
            tuple[Callable[[], Coroutine[Any, Any, Any]], asyncio.Future[Any]]
        ] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._last_heartbeat = time.monotonic()
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._status = BotStatus.IDLE
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.debug("Bot %s started", self.bot_id)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._status = BotStatus.TERMINATED
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.debug("Bot %s stopped", self.bot_id)

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    async def submit(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Submit a task and await its result."""
        fut: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        await self._task_queue.put((coro_factory, fut))
        return await fut

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                coro_fn, fut = await asyncio.wait_for(
                    self._task_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                self._last_heartbeat = time.monotonic()
                continue

            self._status = BotStatus.RUNNING
            await self._execute_with_retry(coro_fn, fut)
            self._status = BotStatus.IDLE
            self._last_heartbeat = time.monotonic()

    async def _execute_with_retry(
        self,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        fut: asyncio.Future[Any],
    ) -> None:
        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                async with self._semaphore:
                    result = await coro_fn()
                self._tasks_completed += 1
                if not fut.done():
                    fut.set_result(result)
                return
            except Exception as exc:
                last_exc = exc
                self._status = BotStatus.RECOVERING
                logger.warning(
                    "Bot %s task attempt %d failed: %s", self.bot_id, attempt, exc
                )
                await asyncio.sleep(0.1 * (attempt + 1))

        self._tasks_failed += 1
        if not fut.done():
            fut.set_exception(last_exc or RuntimeError("task failed"))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def status(self) -> BotStatus:
        return self._status

    @property
    def is_healthy(self) -> bool:
        age = time.monotonic() - self._last_heartbeat
        return self._running and age < 30.0

    @property
    def tasks_completed(self) -> int:
        return self._tasks_completed

    @property
    def tasks_failed(self) -> int:
        return self._tasks_failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "status": self._status.value,
            "hardware_class": self._config.hardware_class,
            "inference_concurrency": self._config.inference_concurrency,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "is_healthy": self.is_healthy,
        }
