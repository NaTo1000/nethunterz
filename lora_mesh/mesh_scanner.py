"""Mesh scanner with Seek and Find capability."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional
from .firmware import LoRaFirmware, LoRaNode

logger = logging.getLogger("nethunterz.lora.scanner")


@dataclass
class ScanResult:
    node_id: str
    rssi: float
    snr: float
    frequency_mhz: float
    last_seen: float
    active: bool
    latitude: float = 0.0
    longitude: float = 0.0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "rssi": self.rssi,
            "snr": self.snr,
            "frequency_mhz": self.frequency_mhz,
            "last_seen": self.last_seen,
            "active": self.active,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class MeshScanner:
    """Scans mesh nodes, records signal strength, proximity, activity.
    Supports 'Seek and Find' for locating specific or unresponsive nodes."""

    INACTIVE_TIMEOUT_S = 60.0

    def __init__(self, firmware: LoRaFirmware, beacon_interval_s: float = 5.0):
        self.firmware = firmware
        self.beacon_interval_s = beacon_interval_s
        self._scan_results: dict[str, ScanResult] = {}
        self._seek_targets: set[str] = set()
        self._running = False
        firmware.add_packet_callback(self._on_node_update)

    def _on_node_update(self, node: LoRaNode) -> None:
        self._scan_results[node.node_id] = ScanResult(
            node_id=node.node_id,
            rssi=node.rssi,
            snr=node.snr,
            frequency_mhz=node.frequency_mhz,
            last_seen=node.last_seen,
            active=node.active,
            latitude=node.latitude,
            longitude=node.longitude,
        )

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._beacon_loop())
        logger.info("MeshScanner started")

    async def stop(self) -> None:
        self._running = False
        logger.info("MeshScanner stopped")

    async def _beacon_loop(self) -> None:
        while self._running:
            now = time.time()
            for res in self._scan_results.values():
                if now - res.last_seen > self.INACTIVE_TIMEOUT_S:
                    res.active = False
            if self._seek_targets:
                logger.info("Sending seek beacons for: %s", self._seek_targets)
            await asyncio.sleep(self.beacon_interval_s)

    def seek(self, node_id: str) -> None:
        """Add a node to the seek-and-find target list."""
        self._seek_targets.add(node_id)
        logger.info("Seeking node: %s", node_id)

    def cancel_seek(self, node_id: str) -> None:
        self._seek_targets.discard(node_id)

    def get_all_nodes(self) -> list[ScanResult]:
        return list(self._scan_results.values())

    def get_node(self, node_id: str) -> Optional[ScanResult]:
        return self._scan_results.get(node_id)

    def get_inactive_nodes(self) -> list[ScanResult]:
        return [r for r in self._scan_results.values() if not r.active]

    def get_status(self) -> dict:
        return {
            "total_nodes": len(self._scan_results),
            "active_nodes": sum(1 for r in self._scan_results.values() if r.active),
            "inactive_nodes": sum(1 for r in self._scan_results.values() if not r.active),
            "seek_targets": list(self._seek_targets),
        }
