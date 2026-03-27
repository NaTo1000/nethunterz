"""Error Log tab – display device error logs with background research."""

import json
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QLabel, QHeaderView, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSlot, QThread
from PyQt5.QtGui import QColor
from .background_researcher import BackgroundResearcher

logger = logging.getLogger(__name__)

SOURCE_NAMES = {0: "WiFi", 1: "BLE", 2: "IoT/MQTT", 3: "OTA", 4: "Power", 5: "User"}
SEVERITY_COLORS = {
    "critical": QColor(244, 67, 54),
    "error":    QColor(255, 152, 0),
    "warning":  QColor(255, 235, 59),
    "info":     QColor(76, 175, 80),
}


class ErrorLogTab(QWidget):
    """Error log display with one-click background research."""

    def __init__(self, serial_manager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self._entries: list = []
        self._researcher: BackgroundResearcher = None
        self._research_thread: QThread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)

        # ── Table ────────────────────────────────────────────────────
        top = QWidget()
        tl = QVBoxLayout(top)
        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("⟳ Fetch Logs")
        self.refresh_btn.clicked.connect(self._on_fetch)
        self.clear_btn = QPushButton("🗑 Clear Logs")
        self.clear_btn.clicked.connect(self._on_clear)
        self.research_btn = QPushButton("🔬 Research Selected Error")
        self.research_btn.clicked.connect(self._on_research)
        self.export_btn = QPushButton("💾 Export CSV")
        self.export_btn.clicked.connect(self._on_export)
        for b in (self.refresh_btn, self.clear_btn, self.research_btn, self.export_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        tl.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Source", "Error Code", "Message", "Severity"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        tl.addWidget(self.table)
        splitter.addWidget(top)

        # ── Research panel ───────────────────────────────────────────
        bottom = QGroupBox("Research Results")
        bl = QVBoxLayout(bottom)
        self.research_status = QLabel("Select an error and click 'Research Selected Error'")
        bl.addWidget(self.research_status)
        self.research_output = QTextEdit()
        self.research_output.setReadOnly(True)
        bl.addWidget(self.research_output)
        splitter.addWidget(bottom)

        layout.addWidget(splitter)

    def add_error_entry(self, entry: dict) -> None:
        """Add a single error entry to the table."""
        self._entries.append(entry)
        row = self.table.rowCount()
        self.table.insertRow(row)
        ts = str(entry.get("timestamp", ""))
        src = SOURCE_NAMES.get(entry.get("source", 5), "Unknown")
        code = hex(entry.get("code", 0))
        msg = entry.get("message", "")

        for col, val in enumerate([ts, src, code, msg, "error"]):
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, col, item)

    @pyqtSlot()
    def _on_fetch(self) -> None:
        self.serial_manager.send_json({"cmd": "get_errors"})

    @pyqtSlot()
    def _on_clear(self) -> None:
        self.serial_manager.send_json({"cmd": "clear_errors"})
        self.table.setRowCount(0)
        self._entries.clear()

    @pyqtSlot()
    def _on_research(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self.research_status.setText("No row selected.")
            return
        msg_item = self.table.item(row, 3)
        code_item = self.table.item(row, 2)
        if not msg_item:
            return
        query = f"ESP32 error {code_item.text() if code_item else ''}: {msg_item.text()}"
        self.research_status.setText(f"Researching: {query}")
        self.research_output.clear()

        self._research_thread = QThread()
        self._researcher = BackgroundResearcher(query)
        self._researcher.moveToThread(self._research_thread)
        self._research_thread.started.connect(self._researcher.run)
        self._researcher.result_ready.connect(self._on_research_result)
        self._researcher.finished.connect(self._research_thread.quit)
        self._research_thread.start()

    @pyqtSlot(str)
    def _on_research_result(self, result: str) -> None:
        self.research_output.setPlainText(result)
        self.research_status.setText("Research complete.")

    @pyqtSlot()
    def _on_export(self) -> None:
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "errors.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("timestamp,source,code,message\n")
                for e in self._entries:
                    f.write(
                        f'{e.get("timestamp","")},{e.get("source","")},{e.get("code","")},'
                        f'{e.get("message","").replace(",",";")}\n'
                    )
