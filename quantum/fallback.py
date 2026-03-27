"""Classical fallback implementations when IBM Quantum API is unreachable."""

import logging
import random
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ClassicalFallback:
    """Provides classical implementations of quantum algorithms.

    Used when IBM Quantum API is unavailable (no token, network issues, etc.)
    All methods maintain the same interface as quantum versions.
    """

    def simulate(self, circuit, shots: int = 1024) -> Dict[str, Any]:
        """Classically simulate a simple quantum circuit."""
        try:
            from qiskit import transpile
            from qiskit.providers.basic_provider import BasicSimulator
            backend = BasicSimulator()
            transpiled = transpile(circuit, backend)
            job = backend.run(transpiled, shots=shots)
            result = job.result()
            counts = result.get_counts()
        except Exception as exc:
            logger.warning("BasicSimulator failed (%s); generating pseudo-random counts", exc)
            counts = self._pseudo_random_counts(circuit.num_qubits, shots)

        total = sum(counts.values())
        probs = {k: v / total for k, v in counts.items()}
        return {
            "backend": "classical_fallback",
            "shots": shots,
            "counts": counts,
            "probabilities": probs,
            "circuit_depth": getattr(circuit, "depth", lambda: 0)(),
            "num_qubits": getattr(circuit, "num_qubits", 4),
            "simulation": True,
            "fallback": True,
        }

    def _pseudo_random_counts(self, n_qubits: int, shots: int) -> Dict[str, int]:
        """Generate pseudo-random measurement counts."""
        n_states = min(2 ** n_qubits, 256)
        states = [format(i, f"0{n_qubits}b") for i in range(n_states)]
        counts: Dict[str, int] = {}
        remaining = shots
        for state in states[:-1]:
            c = random.randint(0, remaining // max(n_states, 1))
            if c > 0:
                counts[state] = c
                remaining -= c
        if remaining > 0:
            counts[states[-1]] = remaining
        return counts

    def generate_key(self, n_bytes: int = 32) -> bytes:
        """Generate cryptographically-secure random key (classical)."""
        return os.urandom(n_bytes)

    def optimize_params(self) -> Dict[str, Any]:
        """Return sensible default ESP32 parameters (classical optimisation)."""
        return {
            "cpu_freq_mhz": 160,
            "sleep_interval_s": 10,
            "mqtt_keepalive_s": 60,
            "wifi_tx_power_dbm": 13,
            "confidence": 1.0,
            "backend": "classical_defaults",
            "fallback": True,
        }

    def bell_test(self, shots: int = 1024) -> Dict[str, Any]:
        """Simulate Bell state measurements classically."""
        # Perfect Bell state: 50/50 |00> and |11>
        counts = {"00": shots // 2, "11": shots - shots // 2}
        return {
            "backend": "classical_fallback",
            "shots": shots,
            "counts": counts,
            "probabilities": {"00": 0.5, "11": 0.5},
            "simulation": True,
            "fallback": True,
        }
