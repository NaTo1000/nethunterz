"""QAOA circuit for ESP32 parameter optimization."""

from typing import List, Tuple, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


def build_qaoa_circuit(n_params: int = 4, p_layers: int = 2,
                       gammas: Optional[List[float]] = None,
                       betas: Optional[List[float]] = None):
    """Build a QAOA circuit for optimising ESP32 configuration parameters.

    Parameters
    ----------
    n_params : number of binary parameters to optimise
    p_layers : QAOA depth (number of cost+mixer layer repetitions)
    gammas   : cost layer rotation angles (length p_layers)
    betas    : mixer layer rotation angles (length p_layers)

    Returns
    -------
    qiskit.QuantumCircuit
    """
    from qiskit import QuantumCircuit
    if gammas is None:
        gammas = [np.pi / (2 * (i + 1)) for i in range(p_layers)]
    if betas is None:
        betas = [np.pi / (4 * (i + 1)) for i in range(p_layers)]

    qc = QuantumCircuit(n_params, n_params)

    # Initial uniform superposition
    qc.h(range(n_params))
    qc.barrier()

    for layer in range(p_layers):
        # ── Cost layer ────────────────────────────────────────────────
        gamma = gammas[layer]
        for i in range(n_params):
            j = (i + 1) % n_params
            qc.cx(i, j)
            qc.rz(2 * gamma, j)
            qc.cx(i, j)
        qc.barrier()

        # ── Mixer layer ───────────────────────────────────────────────
        beta = betas[layer]
        for i in range(n_params):
            qc.rx(2 * beta, i)
        qc.barrier()

    qc.measure(range(n_params), range(n_params))
    logger.debug("QAOA circuit: %d qubits, %d layers, depth=%d",
                 n_params, p_layers, qc.depth())
    return qc


def decode_result_to_params(bitstring: str) -> dict:
    """Decode a QAOA measurement bitstring to ESP32 config parameters."""
    val = int(bitstring, 2)
    cpu_freqs     = [80, 160, 240]
    sleep_times   = [5, 10, 30, 60]
    wifi_txpowers = [2, 8, 13, 20]  # dBm

    return {
        "cpu_freq_mhz":      cpu_freqs[(val >> 2) % len(cpu_freqs)],
        "sleep_interval_s":  sleep_times[(val >> 1) % len(sleep_times)],
        "wifi_tx_power_dbm": wifi_txpowers[val % len(wifi_txpowers)],
        "mqtt_keepalive_s":  30 + (val % 90),
        "source_bitstring":  bitstring,
    }


def optimize_esp32_params(quantum_manager, shots: int = 2048) -> dict:
    """Run QAOA optimisation and return decoded ESP32 parameters."""
    circuit = build_qaoa_circuit(n_params=4, p_layers=2)
    result = quantum_manager.run_circuit(circuit, shots=shots)
    counts = result.get("counts", {})
    if not counts:
        return decode_result_to_params("0000")
    best = max(counts, key=counts.get)
    params = decode_result_to_params(best)
    params["confidence"] = counts[best] / shots
    params["backend"] = result.get("backend", "unknown")
    logger.info("Optimised params: %s", params)
    return params
