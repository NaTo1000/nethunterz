# nethunterz

A LoRa-based Meshtastic network implementation with dual NRF module support,
AI-driven frequency management, geofencing, and autonomous defensive systems.

---

## Modules

### `lora_mesh`
Core LoRa Meshtastic layer:
- **`firmware.py`** — LoRa firmware with half-frequency operation, node simulation
- **`mesh_scanner.py`** — Seek-and-Find capable mesh node scanner
- **`frequency_ai.py`** — AI-driven dynamic frequency selection
- **`geofence.py`** — Haversine-based geofencing with enter/exit events
- **`attack_mirror.py`** — Anomaly detection, node isolation, attack mirroring
- **`autonomy.py`** — Autonomous decision engine for network health & defense
- **`gui.py`** — JSON-serializable data layer for mesh visualization

### `nrf_module`
Dual NRF24L01+ module integration:
- **`pingequa_dual_nrf.py`** — Dual-module packet capture with simulation
- **`frequency_manager.py`** — Frequency hopping across NRF channels
- **`ble_bridge.py`** — BLE bridge for device communication
- **`cloud_orchestrator.py`** — Cloud telemetry upload and recommendations
- **`security_monitor.py`** — Security audit logging and anomaly detection
- **`runtime.py`** — CLI entry point for NRF module orchestration

### `cloud`
Cloud-side services:
- **`api_server.py`** — REST API stub for packet ingestion
- **`frequency_engine.py`** — RSSI-based channel recommendation engine
- **`orchestrator.py`** — Coordinates devices and frequency analysis

### `flipper`
Flipper Zero / AIO board integration:
- **`aio_flipper.py`** — BLE command interface for AIO Flipper board
- **`ai_updater.py`** — Autonomous AI-controlled firmware update manager
- **`firmware_builder.py`** — Firmware package builder and flasher

---

## Installation

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
pytest tests/ -v --tb=short
```

## Linting

```bash
pip install flake8 flake8-bugbear
flake8 nrf_module/ cloud/ flipper/ lora_mesh/ tests/ \
  --max-line-length=100 --extend-ignore=E203,W503
```

## CI/CD

GitHub Actions workflows in `.github/workflows/`:
- **`test.yml`** — Runs tests on Python 3.10, 3.11, 3.12
- **`lint.yml`** — Flake8 linting on all modules
- **`nrf-module.yml`** — NRF-specific tests with coverage