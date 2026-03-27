"""LoRa Meshtastic firmware layer with half-frequency operation."""
from __future__ import annotations
import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger("nethunterz.lora.firmware")

HALF_FREQ_BANDS = {
    "US": [433.175, 915.0],    # MHz - standard / half-step
    "EU": [433.175, 869.5],
    "AU": [915.0, 433.175],
}


@dataclass
class LoRaConfig:
    region: str = "US"
    frequency_mhz: float = 915.0
    bandwidth_hz: int = 125000
    spreading_factor: int = 7
    tx_power_dbm: int = 20
    half_frequency_mode: bool = True


@dataclass
class LoRaNode:
    node_id: str
    address: int
    frequency_mhz: float
    rssi: float = -100.0
    snr: float = 0.0
    last_seen: float = field(default_factory=time.time)
    active: bool = True
    latitude: float = 0.0
    longitude: float = 0.0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "frequency_mhz": self.frequency_mhz,
            "rssi": self.rssi,
            "snr": self.snr,
            "last_seen": self.last_seen,
            "active": self.active,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class LoRaFirmware:
    """LoRa Meshtastic firmware with half-frequency operation."""

    def __init__(self, config: Optional[LoRaConfig] = None, simulation: bool = True):
        self.config = config or LoRaConfig()
        self.simulation = simulation
        self._running = False
        self._nodes: dict[str, LoRaNode] = {}
        self._packet_callbacks: list[Callable] = []
        logger.info(
            "LoRaFirmware initialized: region=%s freq=%.3f MHz half=%s",
            self.config.region,
            self.config.frequency_mhz,
            self.config.half_frequency_mode,
        )

    def add_packet_callback(self, cb: Callable) -> None:
        self._packet_callbacks.append(cb)

    async def start(self) -> None:
        self._running = True
        if self.simulation:
            asyncio.create_task(self._simulate_packets())
        logger.info("LoRaFirmware started")

    async def stop(self) -> None:
        self._running = False
        logger.info("LoRaFirmware stopped")

    async def _simulate_packets(self) -> None:
        node_ids = [f"node_{i:04x}" for i in range(1, 6)]
        while self._running:
            nid = random.choice(node_ids)
            node = LoRaNode(
                node_id=nid,
                address=int(nid.split("_")[1], 16),
                frequency_mhz=self.config.frequency_mhz,
                rssi=random.uniform(-120.0, -40.0),
                snr=random.uniform(-5.0, 10.0),
                latitude=random.uniform(-90.0, 90.0),
                longitude=random.uniform(-180.0, 180.0),
            )
            self._nodes[nid] = node
            for cb in self._packet_callbacks:
                cb(node)
            await asyncio.sleep(0.2)

    def set_frequency(self, freq_mhz: float) -> None:
        if self.config.half_frequency_mode:
            freq_mhz = freq_mhz / 2.0
        self.config.frequency_mhz = freq_mhz
        logger.info(
            "Frequency set to %.3f MHz (half_mode=%s)",
            freq_mhz,
            self.config.half_frequency_mode,
        )

    def get_nodes(self) -> dict[str, LoRaNode]:
        return dict(self._nodes)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "region": self.config.region,
            "frequency_mhz": self.config.frequency_mhz,
            "half_frequency_mode": self.config.half_frequency_mode,
            "node_count": len(self._nodes),
            "simulation": self.simulation,
        }
