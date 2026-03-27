"""All-In-One Flipper board integration."""
from __future__ import annotations

import logging

logger = logging.getLogger("nethunterz.flipper.aio_flipper")


class AIOFlipper:
    """AIO Flipper board integration with BLE and firmware management."""

    def __init__(self, device_path: str = "/dev/ttyUSB0", simulation: bool = True) -> None:
        self.device_path = device_path
        self.simulation = simulation
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        logger.info("AIOFlipper connected (sim=%s)", self.simulation)

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("AIOFlipper disconnected")

    async def send_ble_command(self, command: dict) -> dict:
        logger.info("BLE command: %s", command)
        return {"status": "ok", "simulation": self.simulation}

    def get_status(self) -> dict:
        return {"connected": self._connected, "simulation": self.simulation}
