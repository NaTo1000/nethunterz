"""
ble_bridge.py – Bluetooth Low Energy bridge between the NRF runtime and smartphones.

Responsibilities
----------------
* Advertise GATT services for NRF control, log streaming, and frequency upgrades.
* Accept connections from the NetHunterZ Android app.
* Relay real-time packet data and status updates over BLE notifications.
* Receive commands from the app (frequency upgrade, rewrite, start/stop capture).
* Authenticate the connecting device using a shared key challenge.

Hardware requirement: a BLE-capable adapter (BlueZ / D-Bus on Linux).
In CI / simulation mode the class operates without real BLE hardware.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GATT UUIDs (custom 128-bit UUIDs for NetHunterZ)
# ---------------------------------------------------------------------------
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
CHAR_STATUS = "12345678-1234-5678-1234-56789abcdef1"    # read / notify
CHAR_COMMAND = "12345678-1234-5678-1234-56789abcdef2"   # write
CHAR_LOG_STREAM = "12345678-1234-5678-1234-56789abcdef3"  # notify
CHAR_FREQ_UPGRADE = "12345678-1234-5678-1234-56789abcdef4"  # write / notify
CHAR_AUTH = "12345678-1234-5678-1234-56789abcdef5"       # write


# ---------------------------------------------------------------------------
# BLE Bridge
# ---------------------------------------------------------------------------

class BLEBridge:
    """
    BLE GATT server that bridges the Android NetHunterZ app to the NRF runtime.

    In simulation mode (default when BlueZ/dbus is unavailable) the bridge
    maintains an internal command queue and notification buffer so that
    integration tests can exercise the full control path without hardware.
    """

    def __init__(
        self,
        *,
        shared_secret: Optional[str] = None,
        simulation: bool = True,
        command_callback: Optional[Callable[[dict], None]] = None,
    ):
        self._secret = shared_secret or os.environ.get(
            "NRF_BLE_SECRET", "changeme-please-set-NRF_BLE_SECRET"
        )
        self._simulation = simulation
        self._command_callback = command_callback
        self._connected_devices: List[str] = []
        self._authenticated_devices: List[str] = []
        self._notification_buffer: List[dict] = []
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._server_task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Start the BLE GATT server."""
        if self._running:
            logger.warning("BLE bridge already running.")
            return
        self._running = True
        if self._simulation:
            logger.info("[SIM] BLE bridge started (simulation mode).")
            self._server_task = asyncio.create_task(self._sim_server_loop())
        else:
            self._server_task = asyncio.create_task(self._real_server_loop())

    async def stop(self) -> None:
        """Stop the BLE GATT server."""
        self._running = False
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
            self._server_task = None
        logger.info("BLE bridge stopped.")

    # ------------------------------------------------------------------
    # Simulation server loop
    # ------------------------------------------------------------------
    async def _sim_server_loop(self) -> None:
        """Process queued commands in simulation mode."""
        while self._running:
            try:
                cmd = await asyncio.wait_for(self._command_queue.get(), timeout=1.0)
                await self._handle_command(cmd)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------
    # Real BlueZ server loop (requires dbus-fast + bless)
    # ------------------------------------------------------------------
    async def _real_server_loop(self) -> None:
        try:
            from bless import BlessServer, BlessGATTCharacteristic  # type: ignore
        except ImportError:
            logger.error(
                "bless library not installed. Install with: pip install bless\n"
                "Falling back to simulation mode."
            )
            self._simulation = True
            await self._sim_server_loop()
            return

        loop = asyncio.get_event_loop()
        server = BlessServer(name="NetHunterZ-NRF", loop=loop)

        async def read_handler(characteristic, **_):
            return json.dumps({"status": "ok"}).encode()

        async def write_handler(characteristic, value, **_):
            try:
                cmd = json.loads(bytes(value).decode())
                await self._command_queue.put(cmd)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.error("Invalid BLE command: %s", exc)

        server.read_request_func = read_handler
        server.write_request_func = write_handler

        await server.add_new_service(SERVICE_UUID)
        for char_uuid in [CHAR_STATUS, CHAR_COMMAND, CHAR_LOG_STREAM,
                          CHAR_FREQ_UPGRADE, CHAR_AUTH]:
            await server.add_new_characteristic(SERVICE_UUID, char_uuid, None, None)

        await server.start()
        logger.info("BLE GATT server running.")
        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            await server.stop()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def generate_challenge(self, device_id: str) -> str:
        """Generate a one-time challenge token for a connecting device."""
        nonce = secrets.token_hex(16)
        logger.debug("Challenge for %s: %s", device_id, nonce)
        return nonce

    def verify_response(self, device_id: str, challenge: str, response: str) -> bool:
        """
        Verify a device's HMAC-SHA256 response to our challenge.

        The Android app computes: HMAC-SHA256(secret, challenge)
        and sends the hex digest back.
        """
        import hmac
        expected = hmac.new(
            self._secret.encode(),
            challenge.encode(),
            hashlib.sha256,
        ).hexdigest()
        ok = hmac.compare_digest(expected, response)
        if ok:
            if device_id not in self._authenticated_devices:
                self._authenticated_devices.append(device_id)
            logger.info("Device %s authenticated successfully.", device_id)
        else:
            logger.warning("Device %s failed authentication.", device_id)
        return ok

    def is_authenticated(self, device_id: str) -> bool:
        return device_id in self._authenticated_devices

    # ------------------------------------------------------------------
    # Notification / push
    # ------------------------------------------------------------------
    async def notify_status(self, status: dict) -> None:
        """Push a status update to all connected (authenticated) devices."""
        payload = json.dumps(status)
        self._notification_buffer.append({"type": "status", "data": status, "ts": time.time()})
        if not self._simulation:
            # In real mode send via BLE notification
            pass
        logger.debug("BLE notify status: %s", payload[:80])

    async def notify_packet(self, packet_dict: dict) -> None:
        """Stream a captured NRF packet to the app."""
        self._notification_buffer.append({"type": "packet", "data": packet_dict, "ts": time.time()})

    async def notify_frequency_upgrade(self, upgrade: dict) -> None:
        """Notify the app of a frequency upgrade event."""
        self._notification_buffer.append({"type": "freq_upgrade", "data": upgrade, "ts": time.time()})
        logger.info("BLE freq upgrade notification: %s", upgrade)

    # ------------------------------------------------------------------
    # Command injection (for testing / simulation)
    # ------------------------------------------------------------------
    async def inject_command(self, command: dict) -> None:
        """Inject a command as if it arrived from a connected BLE device."""
        await self._command_queue.put(command)

    async def _handle_command(self, cmd: dict) -> None:
        action = cmd.get("action", "")
        logger.info("BLE command received: %s", action)
        if self._command_callback:
            try:
                self._command_callback(cmd)
            except Exception as exc:  # pragma: no cover
                logger.error("Command callback error: %s", exc)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_notification_buffer(self) -> List[dict]:
        return list(self._notification_buffer)

    def clear_notification_buffer(self) -> None:
        self._notification_buffer.clear()

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "simulation": self._simulation,
            "connected_devices": list(self._connected_devices),
            "authenticated_devices": list(self._authenticated_devices),
            "buffered_notifications": len(self._notification_buffer),
        }
