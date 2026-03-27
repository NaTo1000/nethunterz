"""Dual NRF module simulation for nethunterz."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("nethunterz.nrf.pingequa")


@dataclass
class ModuleConfig:
    module_id: int
    channel: int = 76


@dataclass
class NRFPacket:
    module_id: int
    channel: int
    payload: bytes
    rssi: float
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "channel": self.channel,
            "payload": self.payload.hex(),
            "rssi": self.rssi,
            "timestamp": self.timestamp,
        }


class PingequaDualNRF:
    """Dual NRF module with simulation support."""

    def __init__(
        self,
        primary: ModuleConfig,
        secondary: ModuleConfig,
        log_dir: Path = None,
        simulation: bool = True,
        packet_callback: Optional[Callable[[NRFPacket], None]] = None,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.log_dir = log_dir if log_dir is not None else Path("logs/nrf")
        self.simulation = simulation
        self.packet_callback = packet_callback
        self._open = False
        self._running = False
        self._captured_packets: list[NRFPacket] = []

    def open(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._open = True
        logger.info(
            "PingequaDualNRF opened (primary=%d, secondary=%d, sim=%s)",
            self.primary.module_id,
            self.secondary.module_id,
            self.simulation,
        )

    def close(self) -> None:
        self._open = False
        logger.info("PingequaDualNRF closed")

    async def start_capture(self) -> None:
        if not self._open:
            raise RuntimeError("Module not opened")
        self._running = True
        if self.simulation:
            asyncio.create_task(self._simulate_packets())
        logger.info("Capture started")

    async def stop_capture(self) -> None:
        self._running = False
        logger.info("Capture stopped")

    async def _simulate_packets(self) -> None:
        modules = [self.primary, self.secondary]
        while self._running:
            mod = random.choice(modules)
            pkt = NRFPacket(
                module_id=mod.module_id,
                channel=mod.channel,
                payload=random.randbytes(16),
                rssi=random.uniform(-90.0, -30.0),
                timestamp=time.time(),
            )
            self._captured_packets.append(pkt)
            if self.packet_callback:
                self.packet_callback(pkt)
            await asyncio.sleep(0.1)

    def get_status(self) -> dict:
        return {
            "open": self._open,
            "running": self._running,
            "simulation": self.simulation,
            "primary_id": self.primary.module_id,
            "secondary_id": self.secondary.module_id,
            "captured_count": len(self._captured_packets),
        }

    async def get_captured_packets(self) -> list[NRFPacket]:
        return list(self._captured_packets)
