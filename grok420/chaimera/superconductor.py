"""Superconductor — optimises computational throughput per hardware unit."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from grok420.config import CHAiMERAConfig

logger = logging.getLogger(__name__)


@dataclass
class ThroughputMetrics:
    """Running throughput statistics for the superconductor."""

    tasks_submitted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_latency_s: float = 0.0
    peak_concurrency: int = 0

    @property
    def avg_latency_s(self) -> float:
        if self.tasks_completed == 0:
            return 0.0
        return self.total_latency_s / self.tasks_completed

    @property
    def throughput_per_second(self) -> float:
        if self.total_latency_s == 0:
            return 0.0
        return self.tasks_completed / self.total_latency_s


class Superconductor:
    """Orchestrates concurrent execution across CHAiMERA layers.

    The superconductor maintains a thread-pool-like asyncio semaphore
    pool and tracks throughput metrics for adaptive tuning.
    """

    def __init__(self, config: CHAiMERAConfig) -> None:
        self._config = config
        self._metrics = ThroughputMetrics()
        self._semaphore: asyncio.Semaphore | None = None
        self._current_concurrency = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._semaphore = asyncio.Semaphore(self._config.superconductor_threads)
        logger.info(
            "Superconductor started: threads=%d", self._config.superconductor_threads
        )

    async def stop(self) -> None:
        logger.info("Superconductor stopped; metrics=%s", self._metrics)

    async def execute(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Execute *coro_factory()* under the superconductor's concurrency cap."""
        if self._semaphore is None:
            raise RuntimeError("Superconductor not started")

        self._metrics.tasks_submitted += 1
        start = time.monotonic()

        async with self._semaphore:
            async with self._lock:
                self._current_concurrency += 1
                if self._current_concurrency > self._metrics.peak_concurrency:
                    self._metrics.peak_concurrency = self._current_concurrency

            try:
                result = await coro_factory()
                self._metrics.tasks_completed += 1
                self._metrics.total_latency_s += time.monotonic() - start
                return result
            except Exception as exc:
                self._metrics.tasks_failed += 1
                logger.error("Superconductor task failed: %s", exc)
                raise
            finally:
                async with self._lock:
                    self._current_concurrency -= 1

    @property
    def metrics(self) -> ThroughputMetrics:
        return self._metrics

    def set_thread_count(self, n: int) -> None:
        """Adjust concurrency cap at runtime."""
        if n < 1:
            raise ValueError("thread_count must be >= 1")
        self._config.superconductor_threads = n
        # Replace semaphore for next cycle
        self._semaphore = asyncio.Semaphore(n)
        logger.info("Superconductor thread count updated to %d", n)
