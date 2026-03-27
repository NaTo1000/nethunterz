# NethunterZ

> **Comprehensive ESP32 IoT Firmware Platform** with BLE, WiFi, MQTT, OTA updates, Flipper Zero integration, dual NRF24L01+ radio management, and IBM Quantum-enhanced optimization.

[![Firmware Build](https://github.com/nethunterz/nethunterz/actions/workflows/firmware_build.yml/badge.svg)](https://github.com/nethunterz/nethunterz/actions/workflows/firmware_build.yml)
[![Tests](https://github.com/nethunterz/nethunterz/actions/workflows/sandbox_test.yml/badge.svg)](https://github.com/nethunterz/nethunterz/actions/workflows/sandbox_test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌟 Features

### ESP32 Firmware (C / FreeRTOS)
- **WiFi Management** – Station + AP fallback, auto-reconnect with configurable retry, RSSI monitoring
- **BLE GATT Server** – Three characteristics: device control, OTA notifications, status reporting; 517-byte MTU
- **IoT / MQTT** – Cloud telemetry, command subscription, periodic metrics publishing
- **OTA Updates** – HTTPS firmware update with SHA-256 verification and progress callbacks
- **Power Management** – Deep sleep, light sleep, dynamic voltage/frequency scaling (DVFS), battery ADC monitoring
- **Error Logging** – NVS ring-buffer (64 entries), structured JSON log entries, automatic flush
- **Custom Bootloader** – Dual-partition slot management with SHA-256 integrity check and error recovery

### Python GUI (PyQt5)
- **Dashboard Tab** – Real-time CPU, heap, WiFi RSSI, BLE status, battery voltage monitoring
- **Firmware Tab** – OTA URL trigger, local binary flash via esptool, version display
- **Error Log Tab** – Tabular error display, CSV export, one-click background error research
- **Config Tab** – WiFi/MQTT/BLE/power settings editor with send-to-device
- **Metrics Tab** – Live matplotlib charts (heap, RSSI, battery voltage) with pause/clear
- **Quantum Tab** – IBM Quantum circuit submission, local Aer fallback, results display

### IBM Quantum Integration
- QAOA circuit for ESP32 parameter optimization (CPU freq, sleep intervals, WiFi TX power)
- Quantum random number generation for BLE session key derivation
- Graceful classical fallback when IBM Quantum API unreachable

### Flipper Zero App
- Flipper SDK native app with ViewPort rendering
- BLE connection status and device diagnostics
- Scrollable error log viewer
- OTA trigger with progress bar
- 2.4 GHz channel frequency scanner (2400–2525 MHz)

### Dual NRF24L01+ Radio (Pingequa Module)
- Scan all 126 channels (2400–2525 MHz)
- Intelligent channel scoring (avoids WiFi/BT congestion zones)
- Dynamic frequency hopping with configurable interval
- Packet record, rewrite rules, and replay functionality
- BLE-to-internet bridge for cloud compute offload

### Error Resolution System
- SQLite error database with source/code/message indexing
- Background resolver thread with known-fix knowledge base
- Sandboxed pytest runner for fix verification

---

## 🏗 Architecture

```
nethunterz/
├── firmware/          # ESP32 C firmware (ESP-IDF + PlatformIO)
│   ├── main/          # Application code (6 FreeRTOS tasks)
│   └── bootloader/    # Custom bootloader with SHA-256 check
├── gui/               # Python PyQt5 desktop application
│   └── app/           # Tab widgets, serial manager, background workers
├── quantum/           # IBM Quantum integration
│   └── circuits/      # QAOA optimization + QRNG crypto circuits
├── flipper/           # Flipper Zero SDK app
│   └── esp32_controller/
├── nrf/               # NRF24L01+ dual-module runtime
├── sandbox/           # Pytest test suites and benchmarks
├── error_resolution/  # SQLite error DB + background auto-resolver
├── scripts/           # Utility shell scripts
└── .github/workflows/ # CI/CD pipelines
```

### FreeRTOS Task Map

| Task | Core | Priority | Stack | Purpose |
|------|------|----------|-------|---------|
| `errlog_task` | APP | 3 | 2 KB | Flush error ring buffer every 5s |
| `wifi_task` | PRO | 5 | 4 KB | WiFi STA/AP + reconnect logic |
| `ble_task` | APP | 5 | 4 KB | GATT server + status notifications |
| `iot_task` | APP | 4 | 4 KB | MQTT pub/sub + metrics every 30s |
| `power_task` | APP | 2 | 2 KB | Battery ADC + DVFS + sleep logic |
| `ota_task` | APP | 3 | 8 KB | HTTPS OTA (waits for notification) |

---

## 🚀 Quick Start

### 1. Flash ESP32 Firmware

```bash
# Install dependencies
./scripts/install_dependencies.sh

# Build and flash (auto-detects port)
./scripts/flash_firmware.sh --build --port /dev/ttyUSB0

# Flash pre-built binary
./scripts/flash_firmware.sh --firmware firmware.bin --port /dev/ttyUSB0
```

### 2. Launch GUI

```bash
./scripts/run_gui.sh
```

### 3. Run Tests

```bash
cd sandbox
pytest -v
```

### 4. Start NRF Runtime (Raspberry Pi)

```bash
./scripts/runtime_nrf.sh --interval 30
```

---

## 📋 Supported Targets

| Target | Board | Notes |
|--------|-------|-------|
| ESP32 | esp32dev | Primary target, dual-core, PSRAM support |
| ESP32-S2 | esp32-s2-saola-1 | Single-core, native USB |
| ESP32-S3 | esp32-s3-devkitc-1 | Dual-core, enhanced BLE/WiFi |
| ESP32-C3 | esp32-c3-devkitm-1 | RISC-V, low power |

---

## 🔧 Configuration

Edit `firmware/main/config.h` for compile-time settings:

```c
#define WIFI_SSID_DEFAULT    "YourNetwork"
#define WIFI_PASS_DEFAULT    "YourPassword"
#define MQTT_BROKER_URI      "mqtt://your.broker.com"
#define OTA_UPDATE_URL       "https://your.server.com/firmware.bin"
```

Or configure at runtime via:
- **GUI Config Tab** → sends JSON config over serial
- **BLE Control Characteristic** → `{"cmd":"set_config","wifi_ssid":"..."}`
- **MQTT Command Topic** → `nethunterz/cmd`

---

## 📚 Documentation

- [Installation Guide](INSTALL.md)
- [System Architecture](docs/architecture.md)
- [Flipper Zero Guide](docs/flipper_zero_guide.md)
- [IBM Quantum Guide](docs/quantum_guide.md)

---

## 🔐 Security

- BLE encryption enhanced with quantum-derived session keys (QRNG + HMAC-SHA256)
- OTA updates verified with SHA-256 integrity check
- HTTPS-only OTA endpoint (configurable TLS certificate pinning)
- NVS secrets stored in encrypted flash (enable via `CONFIG_NVS_ENCRYPTION=y`)

---

## 📄 License

MIT License – see [LICENSE](LICENSE) for details.
