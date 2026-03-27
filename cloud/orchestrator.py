"""Cloud orchestrator coordinating local devices and cloud."""
from __future__ import annotations

import asyncio
import logging
from .frequency_engine import FrequencyEngine

logger = logging.getLogger("nethunterz.cloud.orchestrator")


class CloudOrchestrator:
    """Coordinates between local devices and cloud frequency engine."""

    def __init__(self, simulation: bool = True) -> None:
        self.simulation = simulation
        self.frequency_engine = FrequencyEngine()
        self._running = False
        self._queue: list[dict] = []

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._process_loop())
        logger.info("Cloud CloudOrchestrator started")

    async def stop(self) -> None:
        self._running = False

    async def enqueue(self, packet: dict) -> None:
        self._queue.append(packet)

    async def _process_loop(self) -> None:
        while self._running:
            if self._queue:
                batch = self._queue[:]
                self._queue.clear()
                self.frequency_engine.ingest_telemetry(batch)
                rec = self.frequency_engine.recommend()
                logger.info("Frequency recommendation: channel=%d", rec.channel)
            await asyncio.sleep(5.0)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "queue_size": len(self._queue),
            "frequency_engine": self.frequency_engine.get_status(),
        }
