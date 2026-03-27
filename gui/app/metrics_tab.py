"""Metrics tab – live performance charts using matplotlib."""

import collections
import logging
import json
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox
)
from PyQt5.QtCore import pyqtSlot, QTimer
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

logger = logging.getLogger(__name__)
MAX_POINTS = 120


class LiveChart(FigureCanvas):
    """Embeddable matplotlib chart for live data."""

    def __init__(self, title: str, ylabel: str, color: str = "#4CAF50") -> None:
        self._fig = Figure(figsize=(5, 2.5), facecolor="#2d2d2d", tight_layout=True)
        super().__init__(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor("#1e1e1e")
        self._ax.set_title(title, color="white", fontsize=9)
        self._ax.set_ylabel(ylabel, color="white", fontsize=8)
        self._ax.tick_params(colors="white", labelsize=7)
        for spine in self._ax.spines.values():
            spine.set_edgecolor("#555")
        self._data = collections.deque([0] * MAX_POINTS, maxlen=MAX_POINTS)
        self._x = list(range(MAX_POINTS))
        self._line, = self._ax.plot(self._x, list(self._data), color=color, linewidth=1.5)
        self._color = color

    def push(self, value: float) -> None:
        self._data.append(value)
        self._line.set_ydata(list(self._data))
        if self._data:
            mn, mx = min(self._data), max(self._data)
            pad = max(1.0, (mx - mn) * 0.1)
            self._ax.set_ylim(mn - pad, mx + pad)
        self.draw_idle()


class MetricsTab(QWidget):
    """Live performance metrics charts."""

    def __init__(self, serial_manager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self._build_ui()
        self._last_update = time.time()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Controls
        ctrl = QHBoxLayout()
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self._on_pause)
        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.clicked.connect(self._on_clear)
        ctrl.addWidget(self.pause_btn)
        ctrl.addWidget(self.clear_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Charts
        self.heap_chart    = LiveChart("Free Heap", "bytes", "#4CAF50")
        self.rssi_chart    = LiveChart("WiFi RSSI", "dBm", "#2196F3")
        self.battery_chart = LiveChart("Battery Voltage", "mV", "#FFC107")

        for chart in (self.heap_chart, self.rssi_chart, self.battery_chart):
            layout.addWidget(chart)

        # Stats row
        stats = QHBoxLayout()
        self.heap_stat = QLabel("Heap: — bytes")
        self.rssi_stat = QLabel("RSSI: — dBm")
        self.rate_stat = QLabel("Update rate: — Hz")
        for lbl in (self.heap_stat, self.rssi_stat, self.rate_stat):
            stats.addWidget(lbl)
        stats.addStretch()
        layout.addLayout(stats)

    @pyqtSlot(str)
    def update_from_serial(self, data: str) -> None:
        if self.pause_btn.isChecked():
            return
        try:
            obj = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return

        now = time.time()
        dt = now - self._last_update
        if dt > 0:
            self.rate_stat.setText(f"Update rate: {1/dt:.1f} Hz")
        self._last_update = now

        if "heap" in obj:
            v = float(obj["heap"])
            self.heap_chart.push(v)
            self.heap_stat.setText(f"Heap: {v:,.0f} bytes")

        if "wifi_rssi" in obj:
            v = float(obj["wifi_rssi"])
            self.rssi_chart.push(v)
            self.rssi_stat.setText(f"RSSI: {v:.0f} dBm")

        if "battery_mv" in obj:
            self.battery_chart.push(float(obj["battery_mv"]))

    @pyqtSlot()
    def _on_pause(self) -> None:
        self.pause_btn.setText("▶ Resume" if self.pause_btn.isChecked() else "⏸ Pause")

    @pyqtSlot()
    def _on_clear(self) -> None:
        for chart in (self.heap_chart, self.rssi_chart, self.battery_chart):
            chart._data.clear()
            chart._data.extend([0] * MAX_POINTS)
