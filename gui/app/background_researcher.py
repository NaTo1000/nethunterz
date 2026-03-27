"""Background error research using threading."""

import logging
import time
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class BackgroundResearcher(QObject):
    """Searches for solutions to ESP32 errors in background thread."""

    result_ready = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, query: str) -> None:
        super().__init__()
        self.query = query

    def run(self) -> None:
        """Run research (uses local knowledge base + optional web lookup)."""
        try:
            result = self._search_local_kb(self.query)
            if not result:
                result = self._search_esp_idf_docs(self.query)
            self.result_ready.emit(result)
        except Exception as exc:
            logger.exception("Research error")
            self.result_ready.emit(f"Research failed: {exc}")
        finally:
            self.finished.emit()

    def _search_local_kb(self, query: str) -> str:
        """Search local knowledge base for common ESP32 errors."""
        kb = {
            "wifi_manager_init": (
                "WiFi manager init failure. Common causes:\n"
                "1. NVS not initialised before wifi_manager_init()\n"
                "2. Insufficient heap memory (need ~60KB)\n"
                "3. WiFi driver already started\n\n"
                "Fix: Ensure nvs_flash_init() is called first. Check heap with esp_get_free_heap_size()."
            ),
            "ble_manager_init": (
                "BLE init failure. Common causes:\n"
                "1. Classic BT memory not released before BLE init\n"
                "2. Insufficient IRAM for BT stack\n\n"
                "Fix: Call esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT) first.\n"
                "Check sdkconfig: CONFIG_BT_ENABLED=y, CONFIG_BTDM_CTRL_MODE_BLE_ONLY=y"
            ),
            "ota": (
                "OTA update failure. Common causes:\n"
                "1. Invalid firmware URL or certificate mismatch\n"
                "2. Insufficient flash partition size for OTA\n"
                "3. Network timeout during download\n\n"
                "Fix: Verify OTA_UPDATE_URL, check partition table has ota_0/ota_1 partitions >=1.5MB.\n"
                "Increase OTA_RECV_TIMEOUT_MS if on slow network."
            ),
            "mqtt": (
                "MQTT connection failure. Common causes:\n"
                "1. Broker URI unreachable (check WiFi is connected first)\n"
                "2. Wrong port or auth credentials\n"
                "3. TLS certificate mismatch\n\n"
                "Fix: Verify broker is accessible with ping. Check MQTT_BROKER_URI in config.h.\n"
                "Test with mosquitto_pub/sub from same network."
            ),
            "battery critical": (
                "Battery critical voltage detected. Device entered deep sleep.\n"
                "Action needed: Recharge battery.\n"
                "BATTERY_CRITICAL_MV threshold: 3100mV\n"
                "Device will auto-wake after DEEP_SLEEP_DURATION_US (30s default)."
            ),
        }
        query_lower = query.lower()
        for keyword, solution in kb.items():
            if keyword in query_lower:
                return f"Local KB match for '{keyword}':\n\n{solution}"
        return ""

    def _search_esp_idf_docs(self, query: str) -> str:
        """Attempt to search ESP-IDF documentation (network optional)."""
        try:
            import requests
            search_url = f"https://docs.espressif.com/projects/esp-idf/en/latest/esp32/search.html?q={query[:80]}"
            resp = requests.get(search_url, timeout=5)
            if resp.status_code == 200:
                return (f"ESP-IDF docs search: {search_url}\n\n"
                        "Note: Check the ESP-IDF documentation for detailed error information.\n"
                        "Common resources:\n"
                        "- https://docs.espressif.com/projects/esp-idf/\n"
                        "- https://github.com/espressif/esp-idf/issues\n"
                        "- https://esp32.com/viewforum.php?f=2")
        except Exception:
            pass
        return (f"No local match found for query: {query}\n\n"
                "Suggested resources:\n"
                "1. https://docs.espressif.com/projects/esp-idf/\n"
                "2. https://github.com/espressif/esp-idf/issues\n"
                "3. https://esp32.com/\n"
                "4. https://stackoverflow.com/questions/tagged/esp32")
