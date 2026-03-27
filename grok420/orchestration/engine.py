"""Grok 420x1000 Orchestration Engine — top-level orchestrator.

Integrates the :class:`ClusterManager`, :class:`DecisionEngine`, and the
NayDoev1 conductor to provide multiplexed, multi-cluster AI task execution
with parallel and serial chaining support.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from grok420.config import DecisionMode, OrchestrationConfig
from grok420.orchestration.cluster_manager import ClusterManager
from grok420.orchestration.decision_engine import (
    DecisionContext,
    DecisionEngine,
    DecisionResult,
)

logger = logging.getLogger(__name__)


class Grok420Engine:
    """Grok 420x1000 multi-cluster orchestration engine.

    Features
    --------
    * Parallel execution of redundant error-resilient workflows.
    * Serial AI chaining for causal multi-step task execution.
    * Cluster auto-discovery, health checks, and load balancing.
    * Multiplexed decision-making via :class:`DecisionEngine`.
    """

    def __init__(self, config: OrchestrationConfig | None = None) -> None:
        self._config = config or OrchestrationConfig()
        self._cluster = ClusterManager(self._config)
        self._decision_engine = DecisionEngine()
        self._semaphore: asyncio.Semaphore | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        await self._cluster.start()
        self._semaphore = asyncio.Semaphore(self._config.max_parallel_tasks)
        self._running = True
        logger.info(
            "Grok420Engine started: clusters=%d max_parallel=%d",
            self._config.cluster_count,
            self._config.max_parallel_tasks,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._cluster.stop()
        logger.info("Grok420Engine stopped")

    async def __aenter__(self) -> "Grok420Engine":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def run_parallel(
        self,
        tasks: list[Callable[[], Coroutine[Any, Any, Any]]],
    ) -> list[Any]:
        """Execute tasks in parallel with error-resilient redundancy.

        Each task is executed concurrently; failures are captured and
        returned as :class:`Exception` instances rather than propagated.
        """
        assert self._semaphore is not None

        async def _guarded(coro_fn: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
            async with self._semaphore:  # type: ignore[union-attr]
                try:
                    return await coro_fn()
                except Exception as exc:
                    logger.warning("Parallel task failed: %s", exc)
                    return exc

        return await asyncio.gather(*[_guarded(t) for t in tasks])

    async def run_serial(
        self,
        tasks: list[Callable[[Any], Coroutine[Any, Any, Any]]],
        initial_input: Any = None,
    ) -> Any:
        """Execute tasks in series — each receives the previous result.

        This implements causal multi-step AI chaining where the output of
        step *n* becomes the input to step *n+1*.
        """
        state = initial_input
        for i, task in enumerate(tasks):
            try:
                state = await task(state)
                logger.debug("Serial step %d completed; output_type=%s", i, type(state).__name__)
            except Exception as exc:
                logger.error("Serial step %d failed: %s", i, exc)
                raise
        return state

    # ------------------------------------------------------------------
    # Decision-making
    # ------------------------------------------------------------------

    async def make_decision(
        self,
        payload: dict[str, Any],
        mode: DecisionMode = DecisionMode.ADAPTIVE,
        priority: int = 5,
    ) -> DecisionResult:
        """Route a decision request through the decision engine."""
        ctx = DecisionContext(payload=payload, mode=mode, priority=priority)
        node = await self._cluster.pick_node()
        if node is not None:
            node.task_count += 1
        try:
            result = await self._decision_engine.decide(ctx)
        finally:
            if node is not None:
                node.task_count = max(0, node.task_count - 1)
        return result

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def cluster_manager(self) -> ClusterManager:
        return self._cluster

    @property
    def decision_engine(self) -> DecisionEngine:
        return self._decision_engine

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "clusters": self._cluster.get_cluster_status(),
            "decision_history_len": len(self._decision_engine.decision_history),
        }
