"""NayDoeV1 Conductor - Central AI orchestrator for the NetHunterz stack."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class HardwareProfile(Enum):
    MINIMAL = "minimal"      # Embedded / Pineapple Pager
    STANDARD = "standard"    # Laptop / Raspberry Pi
    HIGH_PERFORMANCE = "high_performance"  # Server / Workstation
    CLUSTER = "cluster"      # Multi-node cluster


class Task:
    """Represents a single orchestrated task."""

    def __init__(
        self,
        task_id: str,
        name: str,
        coro: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 30.0,
    ) -> None:
        self.task_id = task_id
        self.name = name
        self.coro = coro
        self.args = args
        self.kwargs = kwargs or {}
        self.priority = priority
        self.timeout = timeout
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.result: Any = None
        self.error: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at


class NayDoeV1Conductor:
    """
    NayDoeV1 Central AI Conductor.

    Manages task distribution across all connected devices and AI subsystems.
    Dynamically allocates resources based on hardware capabilities, task priority,
    and real-time load metrics.
    """

    VERSION = "1.0.0"
    CODENAME = "NAYDOE"

    def __init__(
        self,
        hardware_profile: HardwareProfile = HardwareProfile.STANDARD,
        max_concurrent_tasks: int = 32,
        enable_blockchain_memory: bool = True,
    ) -> None:
        self.conductor_id = str(uuid.uuid4())
        self.hardware_profile = hardware_profile
        self.max_concurrent_tasks = max_concurrent_tasks
        self.enable_blockchain_memory = enable_blockchain_memory

        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: List[Task] = []
        self._registered_agents: Dict[str, Any] = {}
        self._running = False
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._metrics: Dict[str, Any] = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "uptime_start": time.time(),
        }

        logger.info(
            f"[NayDoeV1] Conductor {self.conductor_id[:8]} initialized "
            f"| Profile: {hardware_profile.value} "
            f"| Max concurrent: {max_concurrent_tasks}"
        )

    @classmethod
    def for_hardware(cls, hardware_profile: HardwareProfile) -> "NayDoeV1Conductor":
        """Factory: create conductor optimized for detected hardware."""
        concurrency_map = {
            HardwareProfile.MINIMAL: 4,
            HardwareProfile.STANDARD: 16,
            HardwareProfile.HIGH_PERFORMANCE: 64,
            HardwareProfile.CLUSTER: 256,
        }
        return cls(
            hardware_profile=hardware_profile,
            max_concurrent_tasks=concurrency_map[hardware_profile],
        )

    async def start(self) -> None:
        """Start the conductor event loop."""
        self._semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        self._running = True
        logger.info("[NayDoeV1] Conductor ONLINE")
        asyncio.create_task(self._dispatcher_loop())

    async def stop(self) -> None:
        """Gracefully stop the conductor."""
        self._running = False
        for task in self._active_tasks.values():
            task.cancel()
        await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
        logger.info("[NayDoeV1] Conductor OFFLINE")

    def register_agent(self, name: str, agent: Any) -> None:
        """Register a sub-agent (CHAiMERA, TWINBRAIN, etc.)."""
        self._registered_agents[name] = agent
        logger.debug(f"[NayDoeV1] Agent registered: {name}")

    async def submit(
        self,
        name: str,
        coro: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 30.0,
        **kwargs,
    ) -> str:
        """Submit a task for execution. Returns task_id."""
        task = Task(
            task_id=str(uuid.uuid4()),
            name=name,
            coro=coro,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
        )
        await self._task_queue.put((priority.value, time.time(), task))
        self._metrics["tasks_submitted"] += 1
        logger.debug(f"[NayDoeV1] Task queued: {name} [{task.task_id[:8]}]")
        return task.task_id

    async def _dispatcher_loop(self) -> None:
        """Main dispatcher loop - pulls tasks from queue and executes them."""
        while self._running:
            try:
                _, _, task = await asyncio.wait_for(
                    self._task_queue.get(), timeout=1.0
                )
                asyncio.create_task(self._execute_task(task))
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"[NayDoeV1] Dispatcher error: {e}")

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task with timeout and error handling."""
        async with self._semaphore:
            task.started_at = time.time()
            try:
                result = await asyncio.wait_for(
                    task.coro(*task.args, **task.kwargs),
                    timeout=task.timeout,
                )
                task.result = result
                task.completed_at = time.time()
                self._metrics["tasks_completed"] += 1
                logger.debug(
                    f"[NayDoeV1] Task complete: {task.name} "
                    f"[{task.elapsed:.2f}s]"
                )
            except asyncio.TimeoutError:
                task.error = "timeout"
                task.completed_at = time.time()
                self._metrics["tasks_failed"] += 1
                logger.warning(f"[NayDoeV1] Task timeout: {task.name}")
            except Exception as e:
                task.error = str(e)
                task.completed_at = time.time()
                self._metrics["tasks_failed"] += 1
                logger.error(f"[NayDoeV1] Task failed: {task.name} | {e}")
            finally:
                self._completed_tasks.append(task)

    def get_metrics(self) -> Dict[str, Any]:
        """Return conductor performance metrics."""
        uptime = time.time() - self._metrics["uptime_start"]
        return {
            **self._metrics,
            "uptime_seconds": uptime,
            "active_tasks": len(self._active_tasks),
            "queued_tasks": self._task_queue.qsize(),
            "registered_agents": list(self._registered_agents.keys()),
            "hardware_profile": self.hardware_profile.value,
            "conductor_id": self.conductor_id,
        }

    def get_status_report(self) -> str:
        """Return a formatted status report."""
        m = self.get_metrics()
        return (
            f"╔══ NayDoeV1 Conductor ══════════════════════╗\n"
            f"║ ID: {self.conductor_id[:16]}...         ║\n"
            f"║ Hardware: {m['hardware_profile']:<33}║\n"
            f"║ Uptime: {m['uptime_seconds']:.1f}s{' ' * 28}║\n"
            f"║ Tasks: {m['tasks_completed']} ok / "
            f"{m['tasks_failed']} fail / "
            f"{m['active_tasks']} active         ║\n"
            f"║ Agents: {', '.join(m['registered_agents']) or 'none':<35}║\n"
            f"╚════════════════════════════════════════════╝"
        )

    def _hash_state(self) -> str:
        """Compute a deterministic hash of current conductor state."""
        state = json.dumps(self.get_metrics(), sort_keys=True, default=str)
        return hashlib.sha256(state.encode()).hexdigest()
