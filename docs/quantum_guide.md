# IBM Quantum Integration Guide

## Overview

NethunterZ integrates IBM Quantum to:
1. **Optimise ESP32 runtime parameters** using QAOA
2. **Generate cryptographic keys** for BLE session encryption using QRNG
3. **Demonstrate quantum-classical hybrid workflows** in an IoT context

## Setup

```bash
pip install qiskit qiskit-ibm-runtime qiskit-aer
```

Register at [quantum.ibm.com](https://quantum.ibm.com) for a free API token, or leave blank to use the local Aer simulator.

## Circuits

### QAOA Optimisation (4 qubits, 2 layers)
Finds optimal ESP32 config (CPU freq, sleep interval, WiFi TX power):
```python
qm = QuantumManager(ibm_token="YOUR_TOKEN")
result = qm.run_circuit(qm.build_optimization_circuit(), shots=2048)
params = qm.extract_optimized_params(result)
# → {"cpu_freq_mhz": 160, "sleep_interval_s": 10, "wifi_tx_power_dbm": 13}
```

### QRNG Key Generation (8 qubits)
Generates 256-bit BLE session keys from quantum randomness:
```python
result = qm.run_circuit(qm.build_crypto_circuit(), shots=1)
key = qm.generate_ble_key(result)  # → 32 bytes
```

### Bell State Test (2 qubits)
Verifies quantum connectivity. Expected: ~50% |00⟩, ~50% |11⟩.

## Classical Fallback

Automatically invoked when IBM Quantum is unreachable — uses `os.urandom()` for keys and sensible defaults for params. Interfaces are identical.

## Available Backends

| Backend | Type |
|---------|------|
| `aer_simulator` (local) | Classical sim, always available |
| `ibm_qasm_simulator` | Cloud sim, free account |
| `ibm_nairobi` / `ibm_oslo` | Real 7-qubit QPU |

## GUI Usage

Open the **Quantum** tab → paste token → select circuit type → set shots → click **⚛ Run Quantum Circuit**.
