"""Bot Army — self-healing bot network managed by NayDoev1 Conductor.

Provides infinite horizontal scaling dependent on hardware capability.
The army manager replicates bots, monitors health, and performs automatic
failover and recovery.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from grok420.bot_army.bot import Bot, BotConfig, BotStatus
from grok420.config import ConductorConfig

logger = logging.getLogger(__name__)


class BotArmy:
    """Manages a horizontally-scalable army of :class:`Bot` workers.

    The army auto-scales within ``max_bots`` based on queue depth and
    hardware profile.  Self-healing detects dead bots and spawns
    replacements.
    """

    def __init__(
        self,
        conductor_config: ConductorConfig | None = None,
        initial_size: int = 4,
    ) -> None:
        self._config = conductor_config or ConductorConfig()
        self._initial_size = min(initial_size, self._config.max_bots)
        self._bots: dict[str, Bot] = {}
        self._lock = asyncio.Lock()
        self._health_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for _ in range(self._initial_size):
            await self._spawn_bot()
        self._health_task = asyncio.create_task(self._health_loop())
        logger.info("BotArmy started with %d bots", len(self._bots))

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            bots = list(self._bots.values())
        for bot in bots:
            await bot.stop()
        async with self._lock:
            self._bots.clear()
        logger.info("BotArmy stopped")

    async def __aenter__(self) -> "BotArmy":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Task dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Assign task to the least-loaded healthy bot."""
        bot = await self._pick_bot()
        if bot is None:
            raise RuntimeError("No healthy bots available")
        return await bot.submit(coro_factory)

    async def dispatch_all(
        self,
        coro_factories: list[Callable[[], Coroutine[Any, Any, Any]]],
    ) -> list[Any]:
        """Distribute tasks across all healthy bots concurrently."""
        return await asyncio.gather(
            *[self.dispatch(f) for f in coro_factories],
            return_exceptions=True,
        )

    # ------------------------------------------------------------------
    # Scaling
    # ------------------------------------------------------------------

    async def scale_to(self, n: int) -> None:
        """Scale the army to exactly *n* bots."""
        n = min(n, self._config.max_bots)
        async with self._lock:
            current = len(self._bots)
        delta = n - current
        if delta > 0:
            for _ in range(delta):
                await self._spawn_bot()
            logger.info("Scaled up by %d bots (total=%d)", delta, n)
        elif delta < 0:
            await self._scale_down(-delta)

    async def _scale_down(self, count: int) -> None:
        async with self._lock:
            bot_ids = list(self._bots.keys())[:count]
        for bid in bot_ids:
            async with self._lock:
                bot = self._bots.pop(bid, None)
            if bot:
                await bot.stop()
        logger.info("Scaled down by %d bots", count)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _spawn_bot(self, config: BotConfig | None = None) -> Bot:
        bot = Bot(config or BotConfig(hardware_class=self._config.hardware_class.value))
        await bot.start()
        async with self._lock:
            self._bots[bot.bot_id] = bot
        return bot

    async def _pick_bot(self) -> Bot | None:
        async with self._lock:
            healthy = [b for b in self._bots.values() if b.is_healthy]
        if not healthy:
            return None
        # Least-loaded by queue proxy: prefer IDLE bots
        idle = [b for b in healthy if b.status == BotStatus.IDLE]
        return idle[0] if idle else healthy[0]

    async def _health_loop(self) -> None:
        while self._running:
            await asyncio.sleep(5.0)
            await self._heal()

    async def _heal(self) -> None:
        dead: list[str] = []
        async with self._lock:
            for bid, bot in self._bots.items():
                if not bot.is_healthy:
                    dead.append(bid)

        for bid in dead:
            async with self._lock:
                bot = self._bots.pop(bid, None)
            if bot:
                await bot.stop()
            replacement = await self._spawn_bot()
            logger.warning("Replaced dead bot %s with %s", bid, replacement.bot_id)

    # ------------------------------------------------------------------
    # Dynamic parameter controls
    # ------------------------------------------------------------------

    def set_max_bots(self, n: int) -> None:
        if n < 1:
            raise ValueError("max_bots must be >= 1")
        self._config.max_bots = n

    def set_hardware_class(self, hw: str) -> None:
        self._config.hardware_class = hw  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def bot_count(self) -> int:
        return len(self._bots)

    @property
    def healthy_bot_count(self) -> int:
        return sum(1 for b in self._bots.values() if b.is_healthy)

    def get_army_status(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self._bots.values()]
