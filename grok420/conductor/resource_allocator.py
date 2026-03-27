"""Resource Allocator — distributes tasks across hardware-aware bot slots."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Any

from grok420.config import ConductorConfig, HardwareClass

logger = logging.getLogger(__name__)


@dataclass
class HardwareProfile:
    """Snapshot of available hardware resources."""

    cpu_cores: int = 1
    gpu_count: int = 0
    tpu_count: int = 0
    quantum_units: int = 0
    memory_gb: float = 1.0
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def total_compute_units(self) -> int:
        return (
            self.cpu_cores
            + self.gpu_count * 8
            + self.tpu_count * 16
            + self.quantum_units * 64
        )


@dataclass
class TaskSlot:
    """A single allocated task slot with hardware affinity."""

    slot_id: int
    hardware_class: HardwareClass
    inference_power: float
    assigned_at: float = field(default_factory=time.monotonic)
    completed_at: float | None = None
    error: str | None = None

    @property
    def latency_s(self) -> float | None:
        if self.completed_at is None:
            return None
        return self.completed_at - self.assigned_at


class ResourceAllocator:
    """Distributes tasks across available hardware based on conductor config.

    The allocator maintains a semaphore-bounded pool of task slots and
    attempts to honour the ``hardware_class`` and ``inference_power``
    settings when dispatching work.
    """

    def __init__(self, config: ConductorConfig) -> None:
        self._config = config
        self._hardware: HardwareProfile = HardwareProfile()
        self._slot_counter = 0
        self._active_slots: dict[int, TaskSlot] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise semaphore and probe hardware."""
        max_concurrent = max(1, int(self._config.max_bots * self._config.inference_power))
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._hardware = await self._probe_hardware()
        logger.info(
            "ResourceAllocator started: slots=%d hardware=%s",
            max_concurrent,
            self._hardware,
        )

    async def stop(self) -> None:
        """Gracefully drain active slots."""
        logger.info("ResourceAllocator stopping; active_slots=%d", len(self._active_slots))
        for slot in list(self._active_slots.values()):
            slot.error = "allocator_shutdown"
        self._active_slots.clear()

    # ------------------------------------------------------------------
    # Task dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        hardware_class: HardwareClass | None = None,
    ) -> Any:
        """Execute *coro_factory()* inside an allocated slot.

        Raises RuntimeError if the allocator has not been started.
        """
        if self._semaphore is None:
            raise RuntimeError("ResourceAllocator.start() must be called first")

        hw = hardware_class or self._config.hardware_class
        slot = await self._acquire_slot(hw)
        try:
            result = await coro_factory()
            slot.completed_at = time.monotonic()
            return result
        except Exception as exc:
            slot.error = str(exc)
            slot.completed_at = time.monotonic()
            logger.error("Slot %d failed: %s", slot.slot_id, exc)
            raise
        finally:
            await self._release_slot(slot.slot_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _acquire_slot(self, hw: HardwareClass) -> TaskSlot:
        assert self._semaphore is not None
        await self._semaphore.acquire()
        async with self._lock:
            self._slot_counter += 1
            slot = TaskSlot(
                slot_id=self._slot_counter,
                hardware_class=hw,
                inference_power=self._config.inference_power,
            )
            self._active_slots[slot.slot_id] = slot
            logger.debug("Acquired slot %d on %s", slot.slot_id, hw)
            return slot

    async def _release_slot(self, slot_id: int) -> None:
        assert self._semaphore is not None
        async with self._lock:
            self._active_slots.pop(slot_id, None)
        self._semaphore.release()
        logger.debug("Released slot %d", slot_id)

    async def _probe_hardware(self) -> HardwareProfile:
        """Best-effort hardware probe without hard dependencies."""
        import os

        cpu_cores = os.cpu_count() or 1
        memory_gb = 1.0
        try:
            import sys
            if sys.platform != "win32":
                import resource
                soft, _ = resource.getrlimit(resource.RLIMIT_AS)
                if soft > 0:
                    memory_gb = soft / (1024 ** 3)
        except Exception:
            pass

        # GPU detection (optional)
        gpu_count = 0
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                gpu_count = len([l for l in result.stdout.splitlines() if l.strip()])
        except Exception:
            pass

        return HardwareProfile(
            cpu_cores=cpu_cores,
            gpu_count=gpu_count,
            memory_gb=memory_gb,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def active_slot_count(self) -> int:
        return len(self._active_slots)

    @property
    def hardware_profile(self) -> HardwareProfile:
        return self._hardware

    def set_inference_power(self, power: float) -> None:
        """Dynamically adjust inference power (0.0–1.0)."""
        if not 0.0 <= power <= 1.0:
            raise ValueError(f"inference_power must be 0.0–1.0, got {power}")
        self._config.inference_power = power
        logger.info("Inference power updated to %.2f", power)

    def set_latency_vs_accuracy(self, ratio: float) -> None:
        """0.0 = pure latency, 1.0 = pure accuracy."""
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(f"ratio must be 0.0–1.0, got {ratio}")
        self._config.latency_vs_accuracy = ratio
        logger.info("Latency/accuracy ratio set to %.2f", ratio)
