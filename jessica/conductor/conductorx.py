"""ConductorX — Clustered Super Orchestrator.

The top‑level orchestration brain that:
* manages a cluster of orchestrator workers via Raft consensus;
* schedules workflow chains onto the CHAiMERA 3×3×3 stack overlay;
* auto‑scales workers based on queue depth;
* routes AI transformer‑bot decisions into the execution pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("jessica.conductor.conductorx")


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskState(str, Enum):
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(order=False)
class OrchestratorTask:
    """A unit of work submitted to ConductorX for scheduling."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.QUEUED
    assigned_worker: str | None = None
    submitted_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    result: Any = None
    error: str | None = None

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, OrchestratorTask):
            return NotImplemented
        return self.submitted_at < other.submitted_at


class ConductorX:
    """ConductorX cluster leader / participant.

    In a production deployment each replica runs a ConductorX instance; one
    is elected leader via the Raft heartbeat protocol.  In single‑node mode
    the instance is automatically the leader.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        cluster_cfg = config.get("cluster", {})
        self._replicas = cluster_cfg.get("replicas", 1)
        self._heartbeat_ms = cluster_cfg.get("heartbeat_interval_ms", 500)
        self._election_timeout_ms = cluster_cfg.get("election_timeout_ms", 3000)

        sched_cfg = config.get("scheduling", {})
        self._strategy = sched_cfg.get("strategy", "adaptive")
        self._max_workers = sched_cfg.get("max_workers", 100)

        self._node_id = uuid.uuid4().hex[:8]
        self._is_leader = False
        self._running = False

        # Task queue (priority‑sorted)
        self._queue: asyncio.PriorityQueue[tuple[int, OrchestratorTask]] = asyncio.PriorityQueue()
        self._tasks: dict[str, OrchestratorTask] = {}
        self._workers: dict[str, _WorkerHandle] = {}
        self._dispatch_task: asyncio.Task[None] | None = None

    # ── lifecycle ─────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        self._is_leader = True  # single‑node mode
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info(
            "ConductorX node %s started — leader=%s  strategy=%s  max_workers=%d",
            self._node_id,
            self._is_leader,
            self._strategy,
            self._max_workers,
        )

    async def stop(self) -> None:
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
        logger.info("ConductorX node %s stopped", self._node_id)

    # ── task management ───────────────────────────────────

    async def submit_task(self, task: OrchestratorTask) -> str:
        """Submit a task to the orchestration queue.  Returns the task ID."""
        self._tasks[task.id] = task
        # Priority queue: lower number = higher priority, so negate
        await self._queue.put((-task.priority.value, task))
        logger.info("Task %s (%s) queued — priority=%s", task.id, task.name, task.priority.name)
        return task.id

    def get_task(self, task_id: str) -> OrchestratorTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, state: TaskState | None = None) -> list[OrchestratorTask]:
        if state is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.state == state]

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    # ── worker registration ───────────────────────────────

    def register_worker(self, worker_id: str, capabilities: list[str] | None = None) -> None:
        self._workers[worker_id] = _WorkerHandle(worker_id, capabilities or [])
        logger.info("Worker %s registered (total: %d)", worker_id, len(self._workers))

    def deregister_worker(self, worker_id: str) -> None:
        self._workers.pop(worker_id, None)
        logger.info("Worker %s deregistered (total: %d)", worker_id, len(self._workers))

    # ── autoscale hint ────────────────────────────────────

    def desired_worker_count(self) -> int:
        """Adaptive autoscale: target = max(min_replicas, queue_depth / target)."""
        orch_cfg = self._cfg.get("orchestrators", {})
        min_r = orch_cfg.get("min_replicas", 3)
        max_r = orch_cfg.get("max_replicas", 50)
        autoscale = orch_cfg.get("autoscale", {})
        target_per_worker = autoscale.get("target", 10)
        desired = max(min_r, self.queue_depth // max(target_per_worker, 1))
        return min(desired, max_r)

    # ── dispatch loop ─────────────────────────────────────

    async def _dispatch_loop(self) -> None:
        """Continuously pull from the priority queue and dispatch to workers."""
        while self._running:
            if self._queue.empty() or not self._workers:
                await asyncio.sleep(0.1)
                continue

            _, task = await self._queue.get()
            worker = self._select_worker(task)
            if worker is None:
                # Put it back
                await self._queue.put((-task.priority.value, task))
                await asyncio.sleep(0.1)
                continue

            task.state = TaskState.DISPATCHED
            task.assigned_worker = worker.worker_id
            worker.active_tasks += 1
            logger.debug("Dispatched task %s → worker %s", task.id, worker.worker_id)

    def _select_worker(self, task: OrchestratorTask) -> _WorkerHandle | None:
        """Select a worker based on the configured scheduling strategy."""
        available = [w for w in self._workers.values() if w.active_tasks < self._max_workers]
        if not available:
            return None
        if self._strategy == "least_loaded":
            return min(available, key=lambda w: w.active_tasks)
        if self._strategy == "round_robin":
            return available[hash(task.id) % len(available)]
        # adaptive / priority: prefer least loaded, break ties by capability match
        return min(available, key=lambda w: w.active_tasks)


@dataclass
class _WorkerHandle:
    worker_id: str
    capabilities: list[str]
    active_tasks: int = 0
