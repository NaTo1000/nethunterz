# nethunterz

[![NRF Module CI](https://github.com/NaTo1000/nethunterz/actions/workflows/nrf-module.yml/badge.svg)](https://github.com/NaTo1000/nethunterz/actions/workflows/nrf-module.yml)
[![Android Build](https://github.com/NaTo1000/nethunterz/actions/workflows/android-build.yml/badge.svg)](https://github.com/NaTo1000/nethunterz/actions/workflows/android-build.yml)
[![Firmware CI](https://github.com/NaTo1000/nethunterz/actions/workflows/firmware.yml/badge.svg)](https://github.com/NaTo1000/nethunterz/actions/workflows/firmware.yml)

A comprehensive wireless security research platform featuring:

- **Pingequa Dual NRF Module** – dual-channel 2.4 GHz capture, record, replay, and live frequency upgrades.
- **BLE Connectivity** – seamless pairing and control via the NetHunterZ Android app.
- **Cloud Orchestration** – real-time frequency recommendation engine and packet telemetry.
- **AIO Flipper Integration** – AI-driven autonomous firmware management for Flipper Zero boards.
- **Security Monitoring** – flood detection, replay-attack prevention, encrypted audit logs.
- **CI/CD Pipelines** – automated build, test, and deployment for NRF runtime, Android app, cloud API, and firmware.

---

## Repository Structure

```
nethunterz/
├── nrf_module/             # Pingequa Dual NRF runtime (Python)
│   ├── pingequa_dual_nrf.py  – core capture / replay driver
│   ├── frequency_manager.py  – spectrum scan + live frequency upgrades
│   ├── ble_bridge.py         – BLE GATT server (BlueZ / simulation)
│   ├── cloud_orchestrator.py – cloud upload + recommendation relay
│   ├── security_monitor.py   – anomaly detection + encrypted logs
│   └── runtime.py            – entry point: `python -m nrf_module.runtime`
├── cloud/                  # Server-side cloud API (Python + aiohttp)
│   ├── orchestrator.py       – multi-device session manager
│   ├── frequency_engine.py   – RF congestion analysis + recommendations
│   ├── api_server.py         – REST + WebSocket API
│   └── Dockerfile
├── flipper/                # AIO Flipper board integration (Python)
│   ├── aio_flipper.py        – serial / USB controller
│   ├── ai_updater.py         – autonomous firmware updater
│   └── firmware_builder.py   – fbt / Docker build pipeline
├── android_app/            # NetHunterZ Android app (Kotlin)
│   └── app/src/main/java/com/nethunterz/
│       ├── MainActivity.kt
│       ├── MainViewModel.kt
│       ├── BleManager.kt
│       ├── CloudClient.kt
│       ├── LogsActivity.kt
│       ├── FrequencyTrackerActivity.kt
│       └── PacketAdapter.kt
├── tests/                  # Python unit tests (pytest + asyncio)
├── docs/                   # Documentation
│   ├── setup.md
│   ├── ble_workflows.md
│   └── troubleshooting.md
└── .github/workflows/      # CI/CD pipelines
    ├── nrf-module.yml        – lint + test + smoke test (Python)
    ├── android-build.yml     – debug/release APK build
    ├── firmware.yml          – firmware build + integrity validation
    └── cloud-deploy.yml      – cloud API test + Docker build + deploy
```

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Run the NRF runtime in simulation mode
python -m nrf_module.runtime --simulation

# 3. Run the test suite
pytest tests/ -v
```

See [`docs/setup.md`](docs/setup.md) for full setup instructions,
[`docs/ble_workflows.md`](docs/ble_workflows.md) for BLE integration details,
and [`docs/troubleshooting.md`](docs/troubleshooting.md) for common issues.
