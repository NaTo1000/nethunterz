"""Device Configuration tab."""

import json
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QPushButton, QMessageBox,
    QCheckBox, QLabel, QHBoxLayout
)
from PyQt5.QtCore import pyqtSlot

logger = logging.getLogger(__name__)


class ConfigTab(QWidget):
    """Device configuration editor."""

    def __init__(self, serial_manager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── WiFi ────────────────────────────────────────────────────
        wifi_group = QGroupBox("WiFi Settings")
        wf = QFormLayout()
        self.wifi_ssid = QLineEdit()
        self.wifi_ssid.setPlaceholderText("Network SSID")
        self.wifi_pass = QLineEdit()
        self.wifi_pass.setEchoMode(QLineEdit.Password)
        self.wifi_pass.setPlaceholderText("Password")
        self.wifi_ap_mode = QCheckBox("Enable AP Fallback Mode")
        wf.addRow("SSID:", self.wifi_ssid)
        wf.addRow("Password:", self.wifi_pass)
        wf.addRow("", self.wifi_ap_mode)
        wifi_group.setLayout(wf)
        layout.addWidget(wifi_group)

        # ── MQTT ────────────────────────────────────────────────────
        mqtt_group = QGroupBox("MQTT / IoT Settings")
        mf = QFormLayout()
        self.mqtt_uri = QLineEdit()
        self.mqtt_uri.setPlaceholderText("mqtt://broker.example.com")
        self.mqtt_port = QSpinBox()
        self.mqtt_port.setRange(1, 65535)
        self.mqtt_port.setValue(1883)
        self.mqtt_user = QLineEdit()
        self.mqtt_pass = QLineEdit()
        self.mqtt_pass.setEchoMode(QLineEdit.Password)
        self.mqtt_keepalive = QSpinBox()
        self.mqtt_keepalive.setRange(10, 3600)
        self.mqtt_keepalive.setValue(60)
        mf.addRow("Broker URI:", self.mqtt_uri)
        mf.addRow("Port:", self.mqtt_port)
        mf.addRow("Username:", self.mqtt_user)
        mf.addRow("Password:", self.mqtt_pass)
        mf.addRow("Keepalive (s):", self.mqtt_keepalive)
        mqtt_group.setLayout(mf)
        layout.addWidget(mqtt_group)

        # ── BLE ─────────────────────────────────────────────────────
        ble_group = QGroupBox("BLE Settings")
        bf = QFormLayout()
        self.ble_name = QLineEdit("NethunterZ")
        self.ble_enabled = QCheckBox("BLE Enabled")
        self.ble_enabled.setChecked(True)
        bf.addRow("Device Name:", self.ble_name)
        bf.addRow("", self.ble_enabled)
        ble_group.setLayout(bf)
        layout.addWidget(ble_group)

        # ── Power ───────────────────────────────────────────────────
        pwr_group = QGroupBox("Power Management")
        pf = QFormLayout()
        self.cpu_freq = QSpinBox()
        self.cpu_freq.setRange(80, 240)
        self.cpu_freq.setSingleStep(80)
        self.cpu_freq.setValue(240)
        self.light_sleep_en = QCheckBox("Enable Light Sleep")
        pf.addRow("Max CPU Freq (MHz):", self.cpu_freq)
        pf.addRow("", self.light_sleep_en)
        pwr_group.setLayout(pf)
        layout.addWidget(pwr_group)

        # ── Buttons ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("✔ Apply Config")
        self.apply_btn.setStyleSheet("background-color: #2E7D32; color: white; padding: 6px;")
        self.apply_btn.clicked.connect(self._on_apply)
        self.load_btn = QPushButton("⟳ Load from Device")
        self.load_btn.clicked.connect(self._on_load)
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.load_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    @pyqtSlot()
    def _on_apply(self) -> None:
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to device first.")
            return
        cfg = {
            "cmd": "set_config",
            "wifi_ssid": self.wifi_ssid.text(),
            "wifi_pass": self.wifi_pass.text(),
            "wifi_ap_mode": self.wifi_ap_mode.isChecked(),
            "mqtt_uri": self.mqtt_uri.text(),
            "mqtt_port": self.mqtt_port.value(),
            "mqtt_user": self.mqtt_user.text(),
            "mqtt_pass": self.mqtt_pass.text(),
            "mqtt_keepalive": self.mqtt_keepalive.value(),
            "ble_name": self.ble_name.text(),
            "ble_enabled": self.ble_enabled.isChecked(),
            "cpu_freq": self.cpu_freq.value(),
            "light_sleep": self.light_sleep_en.isChecked(),
        }
        self.serial_manager.send_json(cfg)
        QMessageBox.information(self, "Config Sent", "Configuration sent to device.")

    @pyqtSlot()
    def _on_load(self) -> None:
        self.serial_manager.send_json({"cmd": "get_config"})
