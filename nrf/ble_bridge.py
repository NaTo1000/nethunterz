"""BLE to internet bridge for cloud compute via NRF proxy."""

import logging
import threading
import queue
import json
import time
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)


class BLEBridge:
    """Bridges BLE packets to internet/cloud services via NRF.
    
    Receives data from ESP32 over BLE (via NRF packet relay),
    forwards to cloud endpoints, and returns responses.
    """

    def __init__(self, cloud_endpoint: str = "https://api.nethunterz.local/data",
                 api_key: str = "") -> None:
        self.cloud_endpoint = cloud_endpoint
        self.api_key = api_key
        self._inbound:  queue.Queue = queue.Queue(maxsize=256)
        self._outbound: queue.Queue = queue.Queue(maxsize=256)
        self._running   = False
        self._callbacks: Dict[str, Callable] = {}
        self._stats = {"packets_in": 0, "packets_out": 0, "errors": 0}

    def start(self) -> None:
        self._running = True
        self._inbound_thread  = threading.Thread(target=self._process_inbound,  daemon=True)
        self._outbound_thread = threading.Thread(target=self._process_outbound, daemon=True)
        self._inbound_thread.start()
        self._outbound_thread.start()
        logger.info("BLE bridge started, endpoint: %s", self.cloud_endpoint)

    def stop(self) -> None:
        self._running = False
        logger.info("BLE bridge stopped. Stats: %s", self._stats)

    def receive_from_ble(self, nrf_packet: bytes) -> None:
        """Called when an NRF packet arrives from the BLE relay."""
        try:
            self._inbound.put_nowait(nrf_packet)
            self._stats["packets_in"] += 1
        except queue.Full:
            logger.warning("Inbound queue full, dropping packet")

    def register_callback(self, msg_type: str, callback: Callable) -> None:
        self._callbacks[msg_type] = callback

    def _process_inbound(self) -> None:
        while self._running:
            try:
                raw = self._inbound.get(timeout=0.5)
                msg = self._decode_packet(raw)
                if msg:
                    self._route_message(msg)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("Inbound processing error: %s", exc)
                self._stats["errors"] += 1

    def _process_outbound(self) -> None:
        while self._running:
            try:
                msg = self._outbound.get(timeout=0.5)
                self._send_to_cloud(msg)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("Outbound processing error: %s", exc)
                self._stats["errors"] += 1

    def _decode_packet(self, raw: bytes) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw": raw.hex(), "type": "binary"}

    def _route_message(self, msg: Dict[str, Any]) -> None:
        msg_type = msg.get("type", "unknown")
        if msg_type in self._callbacks:
            self._callbacks[msg_type](msg)
        else:
            self._outbound.put_nowait(msg)

    def _send_to_cloud(self, msg: Dict[str, Any]) -> bool:
        try:
            import requests
            resp = requests.post(
                self.cloud_endpoint,
                json=msg,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                timeout=5,
            )
            self._stats["packets_out"] += 1
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("Cloud send failed: %s (offline?)", exc)
            return False

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)
