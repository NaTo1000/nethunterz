"""Serial port communication manager for ESP32."""

import json
import logging
import threading
from typing import List, Optional

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class SerialManager(QObject):
    """Manages serial communication with the ESP32 device."""

    connection_changed = pyqtSignal(bool)
    data_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._serial: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.port: str = ""

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @staticmethod
    def list_ports() -> List[str]:
        """Return available serial port names."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str, baudrate: int = 115200) -> None:
        """Open serial connection and start reader thread."""
        if self.is_connected:
            self.disconnect()
        self._serial = serial.Serial(port, baudrate, timeout=1)
        self.port = port
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self.connection_changed.emit(True)
        logger.info("Connected to %s @ %d baud", port, baudrate)

    def disconnect(self) -> None:
        """Close the serial connection."""
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self.connection_changed.emit(False)
        logger.info("Serial disconnected")

    def send(self, data: str) -> bool:
        """Send a UTF-8 string over serial."""
        if not self.is_connected:
            return False
        try:
            self._serial.write((data + "\n").encode("utf-8"))
            return True
        except serial.SerialException as exc:
            logger.error("Serial send error: %s", exc)
            self.error_occurred.emit(str(exc))
            return False

    def send_json(self, obj: dict) -> bool:
        """Serialise dict to JSON and send."""
        return self.send(json.dumps(obj))

    def request_status(self) -> None:
        """Request a status dump from the ESP32."""
        self.send_json({"cmd": "status"})

    def trigger_ota(self, url: str = "") -> None:
        """Trigger an OTA update on the device."""
        self.send_json({"cmd": "ota", "url": url})

    def _read_loop(self) -> None:
        """Background thread: read lines and emit data_received."""
        while self._running and self._serial and self._serial.is_open:
            try:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self.data_received.emit(line)
            except serial.SerialException as exc:
                if self._running:
                    logger.error("Read error: %s", exc)
                    self.error_occurred.emit(str(exc))
                    self.connection_changed.emit(False)
                break
