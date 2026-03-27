"""
aio_flipper.py – All-In-One Flipper board controller.

Provides serial / USB communication with a Flipper Zero (or compatible
AIO board) with capabilities for:

* Reading device info, firmware version, and installed plugins.
* Sending CLI commands over USB serial.
* Streaming sub-GHz, NFC, IR, and GPIO data.
* Triggering firmware flash operations.
* Exposing an async command API consumed by the AI updater and cloud layer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# Serial protocol constants
FLIPPER_BAUD = 230400
PROMPT = b">: "
EOL = b"\r\n"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FlipperInfo:
    firmware_version: str
    firmware_commit: str
    hardware_version: str
    radio_stack: str
    uptime_s: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SubGHzReading:
    timestamp: float
    frequency_hz: int
    modulation: str
    rssi_dbm: float
    raw_data: str  # hex string


# ---------------------------------------------------------------------------
# Flipper controller
# ---------------------------------------------------------------------------

class AIOFlipperController:
    """
    High-level async controller for Flipper Zero / AIO boards.

    When a serial port is not available (CI / no hardware) the controller
    operates in simulation mode, returning canned responses.
    """

    def __init__(
        self,
        *,
        port: Optional[str] = None,
        simulation: bool = True,
        data_callback: Optional[Callable[[dict], None]] = None,
    ):
        self._port = port or os.environ.get("FLIPPER_PORT", "/dev/ttyACM0")
        self._simulation = simulation
        self._data_callback = data_callback
        self._serial = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._readings: List[SubGHzReading] = []
        self._info: Optional[FlipperInfo] = None
        self._listen_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    async def connect(self) -> bool:
        if self._simulation:
            self._connected = True
            logger.info("[SIM] Flipper board connected (simulation mode).")
            self._listen_task = asyncio.create_task(self._sim_listen())
            return True
        try:
            import serial_asyncio  # type: ignore
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self._port, baudrate=FLIPPER_BAUD
            )
            self._connected = True
            logger.info("Flipper board connected on %s.", self._port)
            self._listen_task = asyncio.create_task(self._listen())
            return True
        except Exception as exc:
            logger.error("Failed to connect to Flipper: %s", exc)
            return False

    async def disconnect(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._writer:
            self._writer.close()
        self._connected = False
        logger.info("Flipper board disconnected.")

    # ------------------------------------------------------------------
    # Command API
    # ------------------------------------------------------------------
    async def get_info(self) -> FlipperInfo:
        if self._simulation:
            self._info = FlipperInfo(
                firmware_version="0.82.3",
                firmware_commit="abc1234",
                hardware_version="f7",
                radio_stack="BLE5.2",
                uptime_s=int(time.time() % 86400),
            )
            return self._info
        response = await self._send_command("info")
        lines = response.splitlines()
        kv = {}
        for line in lines:
            if ":" in line:
                k, _, v = line.partition(":")
                kv[k.strip().lower().replace(" ", "_")] = v.strip()
        self._info = FlipperInfo(
            firmware_version=kv.get("firmware_version", "unknown"),
            firmware_commit=kv.get("firmware_commit", "unknown"),
            hardware_version=kv.get("hardware_version", "unknown"),
            radio_stack=kv.get("radio_stack", "unknown"),
            uptime_s=int(kv.get("uptime", "0").rstrip("s") or 0),
        )
        return self._info

    async def get_installed_plugins(self) -> List[str]:
        if self._simulation:
            return ["NRF-Pingequa", "Sub-GHz-Scanner", "IR-Blaster", "NetHunterZ-Link"]
        response = await self._send_command("plugins list")
        return [line.strip() for line in response.splitlines() if line.strip()]

    async def send_subghz_command(
        self,
        *,
        frequency_hz: int = 433920000,
        modulation: str = "AM650",
        raw_data: str = "",
    ) -> bool:
        cmd = f"subghz tx {frequency_hz} {modulation} {raw_data}"
        if self._simulation:
            logger.debug("[SIM] SubGHz TX: %s", cmd)
            return True
        resp = await self._send_command(cmd)
        return "ok" in resp.lower()

    async def flash_firmware(self, firmware_path: str) -> bool:
        """
        Flash a new firmware image to the Flipper board.

        In simulation mode this validates the file exists and logs the action.
        """
        if not os.path.exists(firmware_path):
            logger.error("Firmware file not found: %s", firmware_path)
            return False
        if self._simulation:
            logger.info("[SIM] Flashing firmware: %s", firmware_path)
            await asyncio.sleep(2)  # simulate flash time
            logger.info("[SIM] Firmware flash complete.")
            return True
        resp = await self._send_command(f"update install {firmware_path}")
        return "success" in resp.lower()

    async def execute_script(self, script: str) -> str:
        """Execute a multi-line flipper CLI script and return output."""
        if self._simulation:
            return f"[SIM] Script executed: {len(script)} chars"
        lines = [l.strip() for l in script.splitlines() if l.strip()]
        outputs = []
        for line in lines:
            out = await self._send_command(line)
            outputs.append(out)
        return "\n".join(outputs)

    # ------------------------------------------------------------------
    # Serial helpers
    # ------------------------------------------------------------------
    async def _send_command(self, cmd: str, timeout: float = 5.0) -> str:
        if not self._writer:
            return ""
        self._writer.write((cmd + "\r\n").encode())
        await self._writer.drain()
        try:
            data = await asyncio.wait_for(self._reader.readuntil(PROMPT), timeout=timeout)
            return data.decode(errors="replace").strip()
        except asyncio.TimeoutError:
            logger.warning("Command timeout: %s", cmd)
            return ""

    async def _listen(self) -> None:
        while self._connected and self._reader:
            try:
                line = await self._reader.readline()
                text = line.decode(errors="replace").strip()
                if text:
                    self._process_line(text)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Read error: %s", exc)
                break

    async def _sim_listen(self) -> None:
        """Generate simulated sub-GHz readings."""
        import random
        while self._connected:
            await asyncio.sleep(2)
            reading = SubGHzReading(
                timestamp=time.time(),
                frequency_hz=random.choice([433920000, 868000000, 315000000]),
                modulation=random.choice(["AM650", "AM270", "FM476"]),
                rssi_dbm=random.uniform(-90.0, -40.0),
                raw_data="AA" * random.randint(4, 16),
            )
            self._readings.append(reading)
            if self._data_callback:
                try:
                    self._data_callback({"type": "subghz", "data": asdict(reading)})
                except Exception as exc:  # pragma: no cover
                    logger.error("Data callback error: %s", exc)

    def _process_line(self, line: str) -> None:
        if self._data_callback:
            self._data_callback({"type": "raw", "line": line})

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_readings(self) -> List[SubGHzReading]:
        return list(self._readings)

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "simulation": self._simulation,
            "port": self._port,
            "info": self._info.to_dict() if self._info else None,
            "reading_count": len(self._readings),
        }
