"""NayDoev1 Conductor — central AI orchestrator for the Grok 420 system.

The conductor owns the entire lifecycle of bot workers, manages the
handshake protocol, and provides the top-level parameter adjustment
interface consumed by the orchestration engine and CHAiMERA chain.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from grok420.config import ConductorConfig, HardwareClass
from grok420.conductor.resource_allocator import ResourceAllocator

logger = logging.getLogger(__name__)

_HANDSHAKE_SECRET = os.environ.get(
    "GROK420_HANDSHAKE_SECRET", "grok420-default-secret-change-me"
).encode()


class BotState(str, Enum):
    PENDING = "pending"
    HANDSHAKING = "handshaking"
    ACTIVE = "active"
    DRAINING = "draining"
    DEAD = "dead"


@dataclass
class BotDescriptor:
    """Metadata for a single bot managed by the conductor."""

    bot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hardware_class: HardwareClass = HardwareClass.CPU
    state: BotState = BotState.PENDING
    registered_at: float = field(default_factory=time.monotonic)
    last_heartbeat: float = field(default_factory=time.monotonic)
    tasks_completed: int = 0
    tasks_failed: int = 0
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)

    def heartbeat(self) -> None:
        self.last_heartbeat = time.monotonic()

    @property
    def is_healthy(self) -> bool:
        age = time.monotonic() - self.last_heartbeat
        return self.state == BotState.ACTIVE and age < 30.0


class NayDoev1Conductor:
    """Central AI conductor that orchestrates all components across clusters.

    Responsibilities
    ----------------
    * Register / deregister bots via the handshake protocol.
    * Allocate hardware resources through :class:`ResourceAllocator`.
    * Expose parameter-adjustment methods for runtime tuning.
    * Perform periodic health checks and auto-scale bot count.
    """

    def __init__(self, config: ConductorConfig | None = None) -> None:
        self._config = config or ConductorConfig()
        self._allocator = ResourceAllocator(self._config)
        self._bots: dict[str, BotDescriptor] = {}
        self._lock = asyncio.Lock()
        self._health_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the conductor and background health monitor."""
        if self._running:
            return
        await self._allocator.start()
        self._running = True
        self._health_task = asyncio.create_task(self._health_loop())
        logger.info("NayDoev1Conductor started (max_bots=%d)", self._config.max_bots)

    async def stop(self) -> None:
        """Gracefully stop the conductor."""
        if not self._running:
            return
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        await self._allocator.stop()
        async with self._lock:
            for bot in self._bots.values():
                bot.state = BotState.DEAD
        logger.info("NayDoev1Conductor stopped")

    async def __aenter__(self) -> "NayDoev1Conductor":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Handshake protocol
    # ------------------------------------------------------------------

    def _compute_hmac(self, bot_id: str, nonce: str) -> str:
        """Compute HMAC-SHA256 token for the given bot_id + nonce."""
        message = f"{bot_id}:{nonce}".encode()
        return hmac.new(_HANDSHAKE_SECRET, message, hashlib.sha256).hexdigest()

    async def register_bot(
        self, hardware_class: HardwareClass = HardwareClass.CPU
    ) -> tuple[str, str]:
        """Register a new bot and return (bot_id, auth_token).

        The bot must present the returned *auth_token* when confirming
        handshake via :meth:`confirm_handshake`.
        """
        async with self._lock:
            if len(self._bots) >= self._config.max_bots:
                raise RuntimeError(
                    f"Bot limit reached ({self._config.max_bots}). "
                    "Increase max_bots or free existing bots."
                )
            bot = BotDescriptor(hardware_class=hardware_class)
            bot.state = BotState.HANDSHAKING
            self._bots[bot.bot_id] = bot

        token = self._compute_hmac(bot.bot_id, bot.nonce)
        logger.debug("Bot registered: %s (hw=%s)", bot.bot_id, hardware_class)
        return bot.bot_id, token

    async def confirm_handshake(self, bot_id: str, token: str) -> bool:
        """Validate the handshake token and promote bot to ACTIVE state."""
        async with self._lock:
            bot = self._bots.get(bot_id)
            if bot is None:
                logger.warning("confirm_handshake: unknown bot %s", bot_id)
                return False
            if bot.state != BotState.HANDSHAKING:
                logger.warning(
                    "confirm_handshake: bot %s in wrong state %s", bot_id, bot.state
                )
                return False

        expected = self._compute_hmac(bot_id, bot.nonce)
        if not hmac.compare_digest(expected, token):
            logger.error("Handshake HMAC mismatch for bot %s", bot_id)
            async with self._lock:
                bot.state = BotState.DEAD
            return False

        async with self._lock:
            bot.state = BotState.ACTIVE
            bot.heartbeat()
        logger.info("Bot %s handshake confirmed (hw=%s)", bot_id, bot.hardware_class)
        return True

    async def deregister_bot(self, bot_id: str) -> None:
        """Remove a bot from the conductor registry."""
        async with self._lock:
            bot = self._bots.pop(bot_id, None)
        if bot:
            bot.state = BotState.DEAD
            logger.info("Bot %s deregistered", bot_id)

    # ------------------------------------------------------------------
    # Task dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        hardware_class: HardwareClass | None = None,
    ) -> Any:
        """Dispatch a coroutine to the resource allocator."""
        if not self._running:
            raise RuntimeError("Conductor is not running")
        return await self._allocator.dispatch(coro_factory, hardware_class)

    # ------------------------------------------------------------------
    # Parameter adjustment interface
    # ------------------------------------------------------------------

    def set_inference_power(self, power: float) -> None:
        """Adjust inference power (0.0 = minimal, 1.0 = maximum)."""
        self._allocator.set_inference_power(power)

    def set_latency_vs_accuracy(self, ratio: float) -> None:
        """0.0 = pure low-latency, 1.0 = pure high-accuracy."""
        self._allocator.set_latency_vs_accuracy(ratio)

    def set_max_bots(self, n: int) -> None:
        """Dynamically adjust the maximum number of bots."""
        if n < 1:
            raise ValueError("max_bots must be >= 1")
        self._config.max_bots = n
        logger.info("max_bots updated to %d", n)

    def set_hardware_class(self, hw: HardwareClass) -> None:
        """Set default hardware class for new tasks."""
        self._config.hardware_class = hw
        logger.info("Default hardware class set to %s", hw)

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def _health_loop(self) -> None:
        """Background loop: heartbeat timeout eviction."""
        while self._running:
            await asyncio.sleep(self._config.resource_poll_interval_s)
            await self._evict_stale_bots()

    async def _evict_stale_bots(self) -> None:
        dead: list[str] = []
        async with self._lock:
            for bid, bot in self._bots.items():
                if bot.state == BotState.ACTIVE and not bot.is_healthy:
                    bot.state = BotState.DEAD
                    dead.append(bid)
        for bid in dead:
            logger.warning("Evicting stale bot %s", bid)
            async with self._lock:
                self._bots.pop(bid, None)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def active_bot_count(self) -> int:
        return sum(1 for b in self._bots.values() if b.state == BotState.ACTIVE)

    @property
    def total_bot_count(self) -> int:
        return len(self._bots)

    @property
    def allocator(self) -> ResourceAllocator:
        return self._allocator

    def get_bot_status(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable snapshot of all bots."""
        return [
            {
                "bot_id": b.bot_id,
                "hardware_class": b.hardware_class.value,
                "state": b.state.value,
                "tasks_completed": b.tasks_completed,
                "tasks_failed": b.tasks_failed,
                "is_healthy": b.is_healthy,
            }
            for b in self._bots.values()
        ]
