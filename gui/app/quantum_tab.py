"""Quantum tab – IBM Quantum job submission and results display."""

import json
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QComboBox, QSpinBox, QFormLayout, QMessageBox
)
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont

logger = logging.getLogger(__name__)


class QuantumWorker(QObject):
    """Background worker for IBM Quantum job submission."""

    status_update = pyqtSignal(str)
    result_ready  = pyqtSignal(dict)
    finished      = pyqtSignal()
    error         = pyqtSignal(str)

    def __init__(self, token: str, backend: str, circuit_type: str, shots: int) -> None:
        super().__init__()
        self.token = token
        self.backend = backend
        self.circuit_type = circuit_type
        self.shots = shots

    def run(self) -> None:
        try:
            self.status_update.emit("Importing Qiskit...")
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "quantum"))
            from quantum_manager import QuantumManager
            qm = QuantumManager(ibm_token=self.token or None)

            self.status_update.emit(f"Building {self.circuit_type} circuit...")
            if self.circuit_type == "optimization":
                circuit = qm.build_optimization_circuit()
            elif self.circuit_type == "crypto_key":
                circuit = qm.build_crypto_circuit()
            else:
                circuit = qm.build_bell_circuit()

            self.status_update.emit(f"Submitting to {self.backend} ({self.shots} shots)...")
            result = qm.run_circuit(circuit, self.backend, self.shots)

            self.result_ready.emit(result)
        except Exception as exc:
            logger.exception("Quantum worker error")
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class QuantumTab(QWidget):
    """IBM Quantum integration tab."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Connection ───────────────────────────────────────────────
        conn_group = QGroupBox("IBM Quantum Connection")
        cf = QFormLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Paste IBM Quantum API token (or leave blank for local sim)")
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems([
            "ibm_qasm_simulator",
            "ibmq_qasm_simulator",
            "ibm_nairobi",
            "ibm_oslo",
            "aer_simulator (local)",
        ])
        cf.addRow("API Token:", self.token_edit)
        cf.addRow("Backend:", self.backend_combo)
        conn_group.setLayout(cf)
        layout.addWidget(conn_group)

        # ── Circuit config ───────────────────────────────────────────
        circ_group = QGroupBox("Circuit Configuration")
        cl = QFormLayout()
        self.circuit_combo = QComboBox()
        self.circuit_combo.addItems(["optimization", "crypto_key", "bell_test"])
        self.shots_spin = QSpinBox()
        self.shots_spin.setRange(1, 8192)
        self.shots_spin.setValue(1024)
        cl.addRow("Circuit Type:", self.circuit_combo)
        cl.addRow("Shots:", self.shots_spin)
        circ_group.setLayout(cl)
        layout.addWidget(circ_group)

        # ── Run buttons ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("⚛ Run Quantum Circuit")
        self.run_btn.setStyleSheet("background-color: #6A1B9A; color: white; padding: 6px;")
        self.run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self.run_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Status / results ─────────────────────────────────────────
        self.status_label = QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        result_group = QGroupBox("Results")
        rl = QVBoxLayout()
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Courier New", 9))
        rl.addWidget(self.result_text)
        result_group.setLayout(rl)
        layout.addWidget(result_group)

    @pyqtSlot()
    def _on_run(self) -> None:
        self.run_btn.setEnabled(False)
        self.result_text.clear()
        self.status_label.setText("Status: Starting...")

        self._thread = QThread()
        self._worker = QuantumWorker(
            token=self.token_edit.text().strip(),
            backend=self.backend_combo.currentText(),
            circuit_type=self.circuit_combo.currentText(),
            shots=self.shots_spin.value(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status_update.connect(self._on_status)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    @pyqtSlot(str)
    def _on_status(self, msg: str) -> None:
        self.status_label.setText(f"Status: {msg}")

    @pyqtSlot(dict)
    def _on_result(self, result: dict) -> None:
        self.result_text.setPlainText(json.dumps(result, indent=2))

    @pyqtSlot(str)
    def _on_error(self, err: str) -> None:
        self.result_text.setPlainText(f"ERROR:\n{err}")
        self.status_label.setText("Status: Error")

    @pyqtSlot()
    def _on_finished(self) -> None:
        self.run_btn.setEnabled(True)
        if "Error" not in self.status_label.text():
            self.status_label.setText("Status: Complete")
