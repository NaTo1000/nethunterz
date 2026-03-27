"""Quantum key generation circuit for BLE encryption enhancement."""

import logging
import hashlib
import hmac
from typing import Optional

logger = logging.getLogger(__name__)


def build_qrng_circuit(n_bits: int = 128):
    """Build a quantum random number generator circuit.

    Uses Hadamard gates to create maximally random quantum states,
    with optional entanglement for enhanced unpredictability.

    Parameters
    ----------
    n_bits : number of random bits to generate (must be <= 127 for IBMQ free tier)
    """
    from qiskit import QuantumCircuit
    # Clamp to hardware limits
    n_qubits = min(n_bits, 127)
    qc = QuantumCircuit(n_qubits, n_qubits)

    # Hadamard → uniform superposition
    qc.h(range(n_qubits))

    # Entangle pairs for quantum correlations
    for i in range(0, n_qubits - 1, 2):
        qc.cx(i, i + 1)

    # Additional mixing layer
    for i in range(n_qubits):
        if i % 3 == 0:
            qc.t(i)
        elif i % 3 == 1:
            qc.s(i)

    qc.measure(range(n_qubits), range(n_qubits))
    logger.debug("QRNG circuit: %d qubits, depth=%d", n_qubits, qc.depth())
    return qc


def derive_ble_session_key(quantum_bits: str, device_id: str = "nethunterz") -> bytes:
    """Derive a 256-bit BLE session key from quantum random bits.

    Parameters
    ----------
    quantum_bits : bitstring from quantum measurement
    device_id    : device identifier for key derivation context
    """
    raw = int(quantum_bits, 2).to_bytes((len(quantum_bits) + 7) // 8, "big")
    key = hmac.new(
        key=device_id.encode("utf-8"),
        msg=raw,
        digestmod=hashlib.sha256,
    ).digest()
    logger.debug("Derived 256-bit BLE session key from %d quantum bits", len(quantum_bits))
    return key


def generate_quantum_key(quantum_manager, key_length_bits: int = 256) -> bytes:
    """Generate a cryptographic key using quantum randomness.

    Falls back to os.urandom on any failure.
    """
    try:
        circuit = build_qrng_circuit(n_bits=min(key_length_bits, 32))
        result = quantum_manager.run_circuit(circuit, shots=1)
        counts = result.get("counts", {})
        if counts:
            bitstring = next(iter(counts))
            key = derive_ble_session_key(bitstring)
            logger.info("Generated quantum key (%d bits raw, 256-bit derived)",
                        len(bitstring))
            return key
    except Exception as exc:
        logger.error("Quantum key generation failed: %s; using classical fallback", exc)
    import os
    return os.urandom(32)
