"""Background thread that monitors error DB and auto-applies fixes."""

import time
import logging
import threading
from typing import Dict, Optional, List
from .error_database import ErrorDatabase, ErrorRecord

logger = logging.getLogger(__name__)

KNOWN_FIXES: Dict[str, str] = {
    "wifi_manager_init": "Ensure nvs_flash_init() is called before wifi_manager_init(). Check heap >= 60KB.",
    "ble_manager_init": "Call esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT) before BLE init.",
    "ota_perform": "Check OTA_UPDATE_URL, TLS certificate, and partition table size >= 1.5MB each slot.",
    "mqtt error": "Verify MQTT broker URI and port. Ensure WiFi is connected before MQTT init.",
    "battery critical": "Battery below 3100mV. Device will deep sleep. Recharge required.",
    "deep sleep": "Device entered deep sleep mode. Will wake after 30 seconds.",
    "wifi reconnect": "WiFi disconnected and reconnecting. Check SSID/password in NVS config.",
    "heap": "Low heap memory detected. Consider reducing task stack sizes or enabling PSRAM.",
}


class BackgroundResolver:
    """Monitors error database and automatically researches/applies fixes."""

    def __init__(self, db: Optional[ErrorDatabase] = None,
                 poll_interval_s: float = 30.0) -> None:
        self.db = db or ErrorDatabase()
        self.poll_interval_s = poll_interval_s
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._resolved_ids: set = set()

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="bg_resolver")
        self._thread.start()
        logger.info("Background resolver started (poll interval: %.0fs)", self.poll_interval_s)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Background resolver stopped")

    def _run_loop(self) -> None:
        while self._running:
            try:
                self._process_unresolved()
            except Exception as exc:
                logger.error("Resolver loop error: %s", exc)
            time.sleep(self.poll_interval_s)

    def _process_unresolved(self) -> None:
        unresolved = self.db.get_unresolved()
        new_errors = [e for e in unresolved if e.id not in self._resolved_ids]
        if not new_errors:
            return
        logger.info("Processing %d new error(s)...", len(new_errors))
        for error in new_errors:
            fix = self._lookup_fix(error)
            if fix:
                logger.info("Auto-resolving error #%d [%s]: %s",
                            error.id, error.source_name, fix[:80])
                self.db.mark_resolved(error.id, fix)
                self._resolved_ids.add(error.id)
            else:
                logger.debug("No known fix for error #%d: %s", error.id, error.message)
                self._resolved_ids.add(error.id)

    def _lookup_fix(self, error: ErrorRecord) -> Optional[str]:
        msg_lower = error.message.lower()
        for keyword, fix in KNOWN_FIXES.items():
            if keyword in msg_lower:
                return fix
        # Code-based lookup
        code_fixes = {
            -1: "Generic error. Check logs for context.",
            0x103: "ESP_ERR_NVS_NOT_FOUND: Key not in NVS. Using defaults.",
            0x105: "ESP_ERR_NVS_INVALID_LENGTH: NVS value too large.",
            0x202: "ESP_ERR_WIFI_NOT_INIT: Call esp_wifi_init() first.",
            0x206: "ESP_ERR_WIFI_CONN: Connection failed. Check SSID/password.",
        }
        return code_fixes.get(error.error_code)

    def get_resolution_stats(self) -> dict:
        return {**self.db.get_statistics(), "auto_resolved": len(self._resolved_ids)}
