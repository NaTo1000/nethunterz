"""Quantum integration tests with mocking."""

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestQuantumManager:
    def test_init_no_token(self):
        with patch.dict("sys.modules", {"qiskit_ibm_runtime": MagicMock(),
                                         "qiskit_aer": MagicMock()}):
            from quantum.quantum_manager import QuantumManager
            qm = QuantumManager(ibm_token=None)
            assert not qm._use_real_hardware

    def test_build_optimization_circuit(self):
        try:
            from qiskit import QuantumCircuit
            from quantum.quantum_manager import QuantumManager
            qm = QuantumManager(ibm_token=None)
            qc = qm.build_optimization_circuit()
            assert qc.num_qubits == 4
            assert qc.num_clbits == 4
        except ImportError:
            pytest.skip("Qiskit not installed")

    def test_build_crypto_circuit(self):
        try:
            from qiskit import QuantumCircuit
            from quantum.quantum_manager import QuantumManager
            qm = QuantumManager(ibm_token=None)
            qc = qm.build_crypto_circuit()
            assert qc.num_qubits == 8
        except ImportError:
            pytest.skip("Qiskit not installed")

    def test_build_bell_circuit(self):
        try:
            from quantum.quantum_manager import QuantumManager
            qm = QuantumManager(ibm_token=None)
            qc = qm.build_bell_circuit()
            assert qc.num_qubits == 2
        except ImportError:
            pytest.skip("Qiskit not installed")

    def test_extract_optimized_params(self):
        from quantum.quantum_manager import QuantumManager
        qm = QuantumManager.__new__(QuantumManager)
        result = {"counts": {"1010": 512, "0101": 256, "1100": 256}, "shots": 1024}
        params = qm.extract_optimized_params(result)
        assert "cpu_freq_mhz" in params
        assert "sleep_interval_s" in params
        assert params["cpu_freq_mhz"] in [80, 160, 240]

    def test_extract_optimized_params_empty(self):
        from quantum.quantum_manager import QuantumManager
        qm = QuantumManager.__new__(QuantumManager)
        result = {"counts": {}, "shots": 0}
        params = qm.extract_optimized_params(result)
        assert params["cpu_freq_mhz"] == 160

    def test_generate_ble_key_length(self):
        from quantum.quantum_manager import QuantumManager
        qm = QuantumManager.__new__(QuantumManager)
        result = {"counts": {"10101010": 1024}, "shots": 1024}
        key = qm.generate_ble_key(result)
        assert len(key) == 32

    def test_generate_ble_key_fallback(self):
        from quantum.quantum_manager import QuantumManager
        qm = QuantumManager.__new__(QuantumManager)
        result = {"counts": {}, "shots": 0}
        key = qm.generate_ble_key(result)
        assert len(key) == 32


class TestClassicalFallback:
    def test_simulate_returns_valid_structure(self):
        from quantum.fallback import ClassicalFallback
        mock_circuit = MagicMock()
        mock_circuit.num_qubits = 4
        mock_circuit.depth.return_value = 5
        fallback = ClassicalFallback()
        with patch.object(fallback, "_pseudo_random_counts",
                          return_value={"0000": 512, "1111": 512}):
            result = fallback.simulate(mock_circuit, shots=1024)
        assert "counts" in result
        assert result["fallback"] is True
        assert result["shots"] == 1024

    def test_generate_key_length(self):
        from quantum.fallback import ClassicalFallback
        key = ClassicalFallback().generate_key(32)
        assert len(key) == 32

    def test_optimize_params_defaults(self):
        from quantum.fallback import ClassicalFallback
        params = ClassicalFallback().optimize_params()
        assert params["cpu_freq_mhz"] in [80, 160, 240]
        assert params["fallback"] is True

    def test_bell_test_probabilities(self):
        from quantum.fallback import ClassicalFallback
        result = ClassicalFallback().bell_test(shots=1000)
        assert abs(result["probabilities"]["00"] - 0.5) < 0.01
        assert abs(result["probabilities"]["11"] - 0.5) < 0.01
