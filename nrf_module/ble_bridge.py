"""BLE bridge for NRF module communication."""
from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger("nethunterz.nrf.ble_bridge")


class BLEBridge:
    """Simulates a BLE bridge for NRF module communication."""

    def __init__(
        self,
        simulation: bool = True,
        command_callback: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.simulation = simulation
        self.command_callback = command_callback
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("BLEBridge started (simulation=%s)", self.simulation)

    async def stop(self) -> None:
        self._running = False
        logger.info("BLEBridge stopped")

    async def notify_frequency_upgrade(self, rec: dict) -> None:
        logger.info("BLE notify frequency upgrade: %s", rec)
        if self.command_callback:
            self.command_callback({"type": "frequency_upgrade", "data": rec})

    async def notify_status(self, status: dict) -> None:
        logger.info("BLE notify status: %s", status)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "simulation": self.simulation,
        }
