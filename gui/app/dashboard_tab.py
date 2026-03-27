"""Dashboard tab – real-time device status monitoring."""

import json
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QProgressBar, QGridLayout, QPushButton
)
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtGui import QColor, QPalette

logger = logging.getLogger(__name__)

_GREEN  = "#4CAF50"
_YELLOW = "#FFC107"
_RED    = "#F44336"
_GREY   = "#9E9E9E"


def _signal_color(rssi: int) -> str:
    if rssi >= -60: return _GREEN
    if rssi >= -75: return _YELLOW
    return _RED


class StatusIndicator(QLabel):
    """Coloured circle status indicator."""

    def __init__(self, label: str) -> None:
        super().__init__(f"● {label}")
        self.set_offline()

    def set_online(self) -> None:
        self.setStyleSheet(f"color: {_GREEN}; font-weight: bold;")

    def set_offline(self) -> None:
        self.setStyleSheet(f"color: {_GREY};")

    def set_warning(self) -> None:
        self.setStyleSheet(f"color: {_YELLOW}; font-weight: bold;")

    def set_error(self) -> None:
        self.setStyleSheet(f"color: {_RED}; font-weight: bold;")


class DashboardTab(QWidget):
    """Real-time device status monitoring tab."""

    def __init__(self, serial_manager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Status row ──────────────────────────────────────────────
        status_group = QGroupBox("System Status")
        status_layout = QHBoxLayout()
        self.wifi_indicator  = StatusIndicator("WiFi")
        self.ble_indicator   = StatusIndicator("BLE")
        self.mqtt_indicator  = StatusIndicator("MQTT")
        self.power_indicator = StatusIndicator("Power")
        for w in (self.wifi_indicator, self.ble_indicator,
                  self.mqtt_indicator, self.power_indicator):
            status_layout.addWidget(w)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # ── Metrics grid ────────────────────────────────────────────
        metrics_group = QGroupBox("Live Metrics")
        grid = QGridLayout()

        def add_row(row, name, unit=""):
            lbl = QLabel(f"{name}:")
            val = QLabel("—")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)
            if unit:
                grid.addWidget(QLabel(unit), row, 2)
            return val

        self.cpu_val        = add_row(0, "CPU Frequency", "MHz")
        self.heap_val       = add_row(1, "Free Heap",     "bytes")
        self.min_heap_val   = add_row(2, "Min Heap",      "bytes")
        self.uptime_val     = add_row(3, "Uptime",        "s")
        self.wifi_rssi_val  = add_row(4, "WiFi RSSI",     "dBm")
        self.battery_val    = add_row(5, "Battery",       "mV")
        self.err_count_val  = add_row(6, "Error Count",   "")

        # Heap bar
        self.heap_bar = QProgressBar()
        self.heap_bar.setRange(0, 100)
        self.heap_bar.setFormat("Heap %p%")
        grid.addWidget(QLabel("Heap Usage:"), 7, 0)
        grid.addWidget(self.heap_bar, 7, 1, 1, 2)

        metrics_group.setLayout(grid)
        layout.addWidget(metrics_group)

        # ── WiFi details ────────────────────────────────────────────
        wifi_group = QGroupBox("WiFi Details")
        wl = QGridLayout()
        self.wifi_ssid_val    = add_wifi_row(wl, 0, "SSID")
        self.wifi_ip_val      = add_wifi_row(wl, 1, "IP Address")
        self.wifi_channel_val = add_wifi_row(wl, 2, "Channel")
        wifi_group.setLayout(wl)
        layout.addWidget(wifi_group)

        # ── Control buttons ─────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.clicked.connect(self._on_refresh)
        self.reboot_btn = QPushButton("⟲ Reboot Device")
        self.reboot_btn.clicked.connect(self._on_reboot)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.reboot_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()

    @pyqtSlot(str)
    def update_from_serial(self, data: str) -> None:
        """Parse incoming JSON line and update UI."""
        try:
            obj = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return

        if "heap" in obj:
            heap = int(obj["heap"])
            self.heap_val.setText(f"{heap:,}")
            # Approximate max heap 300 KB
            pct = max(0, min(100, 100 - heap * 100 // 307200))
            self.heap_bar.setValue(pct)

        if "min_heap" in obj:
            self.min_heap_val.setText(f'{obj["min_heap"]:,}')

        if "uptime" in obj:
            self.uptime_val.setText(str(obj["uptime"]))

        if "wifi_rssi" in obj:
            rssi = int(obj["wifi_rssi"])
            self.wifi_rssi_val.setText(str(rssi))
            self.wifi_rssi_val.setStyleSheet(f"color: {_signal_color(rssi)}")
            self.wifi_indicator.set_online() if rssi < 0 else self.wifi_indicator.set_offline()

        if "ble_connected" in obj:
            if obj["ble_connected"]:
                self.ble_indicator.set_online()
            else:
                self.ble_indicator.set_offline()

        if "battery_mv" in obj:
            self.battery_val.setText(str(obj["battery_mv"]))

        if "ssid" in obj:
            self.wifi_ssid_val.setText(obj["ssid"])

        if "ip" in obj:
            self.wifi_ip_val.setText(obj["ip"])

        if "wifi_channel" in obj:
            self.wifi_channel_val.setText(str(obj["wifi_channel"]))

        if "error_count" in obj:
            count = int(obj["error_count"])
            self.err_count_val.setText(str(count))
            if count > 0:
                self.err_count_val.setStyleSheet(f"color: {_RED};")

    @pyqtSlot()
    def _on_refresh(self) -> None:
        self.serial_manager.request_status()

    @pyqtSlot()
    def _on_reboot(self) -> None:
        self.serial_manager.send_json({"cmd": "reboot"})


def add_wifi_row(grid: QGridLayout, row: int, name: str) -> QLabel:
    lbl = QLabel(f"{name}:")
    val = QLabel("—")
    val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    grid.addWidget(lbl, row, 0)
    grid.addWidget(val, row, 1)
    return val
