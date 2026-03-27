"""Main application window with tab navigation."""

import logging
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar,
    QMenuBar, QAction, QMessageBox, QWidget, QVBoxLayout, QLabel
)
from PyQt5.QtCore import QTimer, pyqtSlot
from PyQt5.QtGui import QIcon

from .serial_manager import SerialManager
from .dashboard_tab import DashboardTab
from .firmware_tab import FirmwareTab
from .error_log_tab import ErrorLogTab
from .config_tab import ConfigTab
from .metrics_tab import MetricsTab
from .quantum_tab import QuantumTab

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """NethunterZ main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NethunterZ Control Panel v1.0.0")
        self.resize(1280, 800)
        self.setMinimumSize(800, 600)

        self.serial_manager = SerialManager()

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()
        self._connect_signals()

        # Refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._on_refresh)
        self._refresh_timer.start()

        logger.info("Main window initialised")

    def _build_menu(self) -> None:
        menubar: QMenuBar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        connect_action = QAction("&Connect Serial", self)
        connect_action.setShortcut("Ctrl+K")
        connect_action.triggered.connect(self._on_connect_serial)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect_serial)
        file_menu.addAction(disconnect_action)
        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = DashboardTab(self.serial_manager)
        self.firmware_tab  = FirmwareTab(self.serial_manager)
        self.error_log_tab = ErrorLogTab(self.serial_manager)
        self.config_tab    = ConfigTab(self.serial_manager)
        self.metrics_tab   = MetricsTab(self.serial_manager)
        self.quantum_tab   = QuantumTab()

        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tabs.addTab(self.firmware_tab,  "⬆ Firmware Update")
        self.tabs.addTab(self.error_log_tab, "⚠ Error Logs")
        self.tabs.addTab(self.config_tab,    "⚙ Device Config")
        self.tabs.addTab(self.metrics_tab,   "📈 Metrics")
        self.tabs.addTab(self.quantum_tab,   "⚛ Quantum")

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._conn_label = QLabel("Disconnected")
        self.status_bar.addPermanentWidget(self._conn_label)
        self.status_bar.showMessage("Ready")

    def _connect_signals(self) -> None:
        self.serial_manager.connection_changed.connect(self._on_connection_changed)
        self.serial_manager.data_received.connect(self._on_data_received)

    @pyqtSlot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        if connected:
            self._conn_label.setText(f"Connected: {self.serial_manager.port}")
            self.status_bar.showMessage("Serial connected", 3000)
        else:
            self._conn_label.setText("Disconnected")
            self.status_bar.showMessage("Serial disconnected", 3000)

    @pyqtSlot(str)
    def _on_data_received(self, data: str) -> None:
        self.dashboard_tab.update_from_serial(data)
        self.metrics_tab.update_from_serial(data)

    @pyqtSlot()
    def _on_refresh(self) -> None:
        if self.serial_manager.is_connected:
            self.serial_manager.request_status()

    @pyqtSlot()
    def _on_connect_serial(self) -> None:
        from PyQt5.QtWidgets import QInputDialog
        ports = SerialManager.list_ports()
        if not ports:
            QMessageBox.warning(self, "No Ports", "No serial ports detected.")
            return
        port, ok = QInputDialog.getItem(self, "Select Port", "Serial port:", ports, 0, False)
        if ok and port:
            try:
                self.serial_manager.connect(port, 115200)
            except Exception as exc:
                QMessageBox.critical(self, "Connection Error", str(exc))

    @pyqtSlot()
    def _on_disconnect_serial(self) -> None:
        self.serial_manager.disconnect()

    @pyqtSlot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About NethunterZ",
            "<h2>NethunterZ Control Panel</h2>"
            "<p>Version 1.0.0</p>"
            "<p>ESP32 firmware management, BLE monitoring, "
            "OTA updates, and IBM Quantum integration.</p>",
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self.serial_manager.disconnect()
        self._refresh_timer.stop()
        event.accept()
