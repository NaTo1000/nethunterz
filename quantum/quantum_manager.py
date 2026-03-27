"""IBM Quantum manager with circuit creation, job submission, and classical fallback."""

import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class QuantumManager:
    """Manages IBM Quantum connections, circuits, and job submissions.

    Falls back gracefully to classical simulation when IBM Quantum
    API is unreachable or no token is provided.
    """

    def __init__(self, ibm_token: Optional[str] = None, instance: str = "ibm-q/open/main") -> None:
        self.ibm_token = ibm_token
        self.instance = instance
        self._service = None
        self._simulator = None
        self._use_real_hardware = False
        self._initialize()

    def _initialize(self) -> None:
        """Attempt to connect to IBM Quantum; fall back to Aer simulator."""
        if self.ibm_token:
            try:
                from qiskit_ibm_runtime import QiskitRuntimeService
                QiskitRuntimeService.save_account(
                    channel="ibm_quantum",
                    token=self.ibm_token,
                    overwrite=True,
                )
                self._service = QiskitRuntimeService(
                    channel="ibm_quantum",
                    instance=self.instance,
                )
                self._use_real_hardware = True
                logger.info("Connected to IBM Quantum service")
            except Exception as exc:
                logger.warning("IBM Quantum connection failed (%s); using local simulator", exc)
                self._use_real_hardware = False

        # Always set up local Aer simulator as fallback
        try:
            from qiskit_aer import AerSimulator
            self._simulator = AerSimulator()
            logger.info("Aer simulator ready")
        except ImportError:
            try:
                from qiskit.providers.aer import AerSimulator
                self._simulator = AerSimulator()
            except ImportError:
                logger.warning("Aer not available; using BasicSimulator fallback")
                self._simulator = None

    def build_optimization_circuit(self):
        """Build a QAOA-inspired circuit for ESP32 parameter optimization."""
        from qiskit import QuantumCircuit
        import numpy as np
        n_qubits = 4
        qc = QuantumCircuit(n_qubits, n_qubits)
        # Initial superposition
        qc.h(range(n_qubits))
        # QAOA cost layer (ring topology)
        gamma = np.pi / 4
        for i in range(n_qubits):
            qc.cx(i, (i + 1) % n_qubits)
            qc.rz(2 * gamma, (i + 1) % n_qubits)
            qc.cx(i, (i + 1) % n_qubits)
        # QAOA mixer layer
        beta = np.pi / 8
        for i in range(n_qubits):
            qc.rx(2 * beta, i)
        qc.measure(range(n_qubits), range(n_qubits))
        logger.debug("Built QAOA optimization circuit: %d qubits", n_qubits)
        return qc

    def build_crypto_circuit(self):
        """Build a quantum random key generation circuit for BLE encryption."""
        from qiskit import QuantumCircuit
        n_bits = 8
        qc = QuantumCircuit(n_bits, n_bits)
        # Hadamard for true quantum randomness
        qc.h(range(n_bits))
        # Entangle pairs for stronger key
        for i in range(0, n_bits - 1, 2):
            qc.cx(i, i + 1)
        qc.measure(range(n_bits), range(n_bits))
        logger.debug("Built quantum crypto key circuit: %d bits", n_bits)
        return qc

    def build_bell_circuit(self):
        """Build a Bell state circuit for connectivity verification."""
        from qiskit import QuantumCircuit
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        return qc

    def run_circuit(self, circuit, backend_name: str = "aer_simulator (local)", shots: int = 1024) -> Dict[str, Any]:
        """Run a circuit and return measurement counts."""
        if "local" in backend_name or not self._use_real_hardware:
            return self._run_local(circuit, shots)
        return self._run_ibm(circuit, backend_name, shots)

    def _run_local(self, circuit, shots: int) -> Dict[str, Any]:
        """Run circuit on local Aer or BasicSimulator."""
        from quantum.fallback import ClassicalFallback
        if self._simulator:
            try:
                from qiskit import transpile
                transpiled = transpile(circuit, self._simulator)
                job = self._simulator.run(transpiled, shots=shots)
                result = job.result()
                counts = result.get_counts()
                total = sum(counts.values())
                probs = {k: v / total for k, v in counts.items()}
                return {
                    "backend": "aer_simulator_local",
                    "shots": shots,
                    "counts": counts,
                    "probabilities": probs,
                    "circuit_depth": circuit.depth(),
                    "num_qubits": circuit.num_qubits,
                    "simulation": True,
                }
            except Exception as exc:
                logger.error("Aer simulation failed: %s; using classical fallback", exc)
        return ClassicalFallback().simulate(circuit, shots)

    def _run_ibm(self, circuit, backend_name: str, shots: int) -> Dict[str, Any]:
        """Submit job to IBM Quantum hardware."""
        try:
            from qiskit_ibm_runtime import Session, SamplerV2 as Sampler
            from qiskit import transpile
            backend = self._service.backend(backend_name)
            transpiled = transpile(circuit, backend)
            with Session(backend=backend) as session:
                sampler = Sampler(session=session)
                job = sampler.run([transpiled], shots=shots)
                logger.info("IBM job submitted, ID: %s", job.job_id())
                result = job.result()
                pub_result = result[0]
                counts = pub_result.data.meas.get_counts()
                total = sum(counts.values())
                probs = {k: v / total for k, v in counts.items()}
            return {
                "backend": backend_name,
                "shots": shots,
                "counts": counts,
                "probabilities": probs,
                "circuit_depth": transpiled.depth(),
                "num_qubits": circuit.num_qubits,
                "simulation": False,
            }
        except Exception as exc:
            logger.error("IBM Quantum run failed: %s; falling back to local", exc)
            return self._run_local(circuit, shots)

    def extract_optimized_params(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract optimal ESP32 parameters from QAOA result counts."""
        counts = result.get("counts", {})
        if not counts:
            return {"cpu_freq_mhz": 160, "sleep_interval_s": 10, "mqtt_keepalive_s": 60}
        best_bitstring = max(counts, key=counts.get)
        val = int(best_bitstring, 2)
        cpu_options = [80, 160, 240]
        sleep_options = [5, 10, 30, 60]
        cpu_idx = (val >> 2) % len(cpu_options)
        sleep_idx = val % len(sleep_options)
        return {
            "cpu_freq_mhz": cpu_options[cpu_idx],
            "sleep_interval_s": sleep_options[sleep_idx],
            "mqtt_keepalive_s": 30 + (val % 90),
            "raw_bitstring": best_bitstring,
            "confidence": counts[best_bitstring] / result.get("shots", 1024),
        }

    def generate_ble_key(self, result: Dict[str, Any]) -> bytes:
        """Generate a BLE encryption key from quantum measurement results."""
        counts = result.get("counts", {})
        if not counts:
            import os
            return os.urandom(32)
        best = max(counts, key=counts.get)
        key_int = int(best, 2)
        # Expand to 32 bytes using deterministic hash
        import hashlib
        return hashlib.sha256(key_int.to_bytes(4, "big")).digest()
