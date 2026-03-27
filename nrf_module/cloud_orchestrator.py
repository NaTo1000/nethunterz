"""Cloud orchestrator for NRF module telemetry."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger("nethunterz.nrf.cloud_orchestrator")


@dataclass
class CloudConfig:
    endpoint: str = "https://api.nethunterz.io"
    api_key: str = ""
    timeout_s: float = 10.0


class CloudOrchestrator:
    """Manages cloud telemetry upload and frequency recommendations."""

    def __init__(
        self,
        simulation: bool = True,
        freq_upgrade_callback: Optional[Callable[[dict], None]] = None,
        config: Optional[CloudConfig] = None,
    ) -> None:
        self.simulation = simulation
        self.freq_upgrade_callback = freq_upgrade_callback
        self.config = config or CloudConfig()
        self._running = False
        self._queue: list[dict] = []

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._process_loop())
        logger.info("CloudOrchestrator started (simulation=%s)", self.simulation)

    async def stop(self) -> None:
        self._running = False
        logger.info("CloudOrchestrator stopped")

    async def enqueue_packet(self, pkt: dict) -> None:
        self._queue.append(pkt)

    async def _process_loop(self) -> None:
        while self._running:
            if self._queue:
                batch = self._queue[:]
                self._queue.clear()
                if self.simulation:
                    logger.debug("Simulated cloud upload: %d packets", len(batch))
            await asyncio.sleep(2.0)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "simulation": self.simulation,
            "queue_size": len(self._queue),
            "endpoint": self.config.endpoint,
        }
