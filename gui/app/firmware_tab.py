"""Firmware Update tab – upload binary, trigger OTA, show version info."""

import logging
import os
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QProgressBar, QTextEdit, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThread, QObject
import requests

logger = logging.getLogger(__name__)


class OTAWorker(QObject):
    """Worker thread for triggering OTA updates."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, serial_manager, url: str) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self.url = url

    def run(self) -> None:
        try:
            self.progress.emit(10, "Sending OTA trigger to device...")
            self.serial_manager.trigger_ota(self.url)
            self.progress.emit(50, "OTA trigger sent. Waiting for device response...")
            import time
            time.sleep(2)
            self.progress.emit(100, "OTA command delivered.")
            self.finished.emit(True, "OTA trigger delivered to device.")
        except Exception as exc:
            self.finished.emit(False, str(exc))


class FirmwareTab(QWidget):
    """Firmware upload and OTA update management tab."""

    def __init__(self, serial_manager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self._ota_thread: QThread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Current version ─────────────────────────────────────────
        info_group = QGroupBox("Device Firmware Info")
        il = QHBoxLayout()
        il.addWidget(QLabel("Running version:"))
        self.version_label = QLabel("unknown")
        self.version_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        il.addWidget(self.version_label)
        il.addStretch()
        self.refresh_version_btn = QPushButton("Refresh")
        self.refresh_version_btn.clicked.connect(self._on_refresh_version)
        il.addWidget(self.refresh_version_btn)
        info_group.setLayout(il)
        layout.addWidget(info_group)

        # ── OTA update ──────────────────────────────────────────────
        ota_group = QGroupBox("OTA Update via URL")
        ol = QVBoxLayout()
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Firmware URL:"))
        self.ota_url_edit = QLineEdit("https://update.nethunterz.local/firmware.bin")
        url_row.addWidget(self.ota_url_edit)
        ol.addLayout(url_row)

        self.ota_progress = QProgressBar()
        self.ota_progress.setRange(0, 100)
        self.ota_progress.setValue(0)
        ol.addWidget(self.ota_progress)

        self.ota_log = QTextEdit()
        self.ota_log.setReadOnly(True)
        self.ota_log.setMaximumHeight(120)
        ol.addWidget(self.ota_log)

        btn_row = QHBoxLayout()
        self.trigger_ota_btn = QPushButton("⬆  Trigger OTA Update")
        self.trigger_ota_btn.setStyleSheet("background-color: #1565C0; color: white; padding: 6px;")
        self.trigger_ota_btn.clicked.connect(self._on_trigger_ota)
        btn_row.addWidget(self.trigger_ota_btn)
        btn_row.addStretch()
        ol.addLayout(btn_row)

        ota_group.setLayout(ol)
        layout.addWidget(ota_group)

        # ── Local binary upload ─────────────────────────────────────
        local_group = QGroupBox("Local Binary Flash (via esptool)")
        ll = QVBoxLayout()
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Binary file:"))
        self.file_path_edit = QLineEdit()
        file_row.addWidget(self.file_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        file_row.addWidget(browse_btn)
        ll.addLayout(file_row)

        self.flash_btn = QPushButton("⚡ Flash Firmware (esptool)")
        self.flash_btn.setStyleSheet("background-color: #BF360C; color: white; padding: 6px;")
        self.flash_btn.clicked.connect(self._on_flash)
        ll.addWidget(self.flash_btn)

        self.flash_log = QTextEdit()
        self.flash_log.setReadOnly(True)
        self.flash_log.setMaximumHeight(120)
        ll.addWidget(self.flash_log)

        local_group.setLayout(ll)
        layout.addWidget(local_group)
        layout.addStretch()

    @pyqtSlot()
    def _on_refresh_version(self) -> None:
        self.serial_manager.send_json({"cmd": "version"})

    @pyqtSlot(str)
    def update_version(self, version: str) -> None:
        self.version_label.setText(version)

    @pyqtSlot()
    def _on_trigger_ota(self) -> None:
        url = self.ota_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a firmware URL.")
            return
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to device first.")
            return

        self.trigger_ota_btn.setEnabled(False)
        self.ota_progress.setValue(0)
        self.ota_log.clear()

        self._ota_thread = QThread()
        self._ota_worker = OTAWorker(self.serial_manager, url)
        self._ota_worker.moveToThread(self._ota_thread)
        self._ota_thread.started.connect(self._ota_worker.run)
        self._ota_worker.progress.connect(self._on_ota_progress)
        self._ota_worker.finished.connect(self._on_ota_finished)
        self._ota_worker.finished.connect(self._ota_thread.quit)
        self._ota_thread.start()

    @pyqtSlot(int, str)
    def _on_ota_progress(self, pct: int, msg: str) -> None:
        self.ota_progress.setValue(pct)
        self.ota_log.append(msg)

    @pyqtSlot(bool, str)
    def _on_ota_finished(self, success: bool, msg: str) -> None:
        self.trigger_ota_btn.setEnabled(True)
        self.ota_log.append(f"{'SUCCESS' if success else 'FAILED'}: {msg}")

    @pyqtSlot()
    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Firmware Binary", "", "Binary files (*.bin);;All files (*)"
        )
        if path:
            self.file_path_edit.setText(path)

    @pyqtSlot()
    def _on_flash(self) -> None:
        path = self.file_path_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Invalid Path", "Select a valid firmware binary.")
            return
        import subprocess
        port = self.serial_manager.port or "/dev/ttyUSB0"
        cmd = ["esptool.py", "--port", port, "--baud", "921600",
               "write_flash", "0x10000", path]
        self.flash_log.append(f"Running: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            self.flash_log.append(proc.stdout)
            if proc.returncode != 0:
                self.flash_log.append(f"ERROR: {proc.stderr}")
            else:
                self.flash_log.append("Flash complete!")
        except Exception as exc:
            self.flash_log.append(f"Exception: {exc}")
