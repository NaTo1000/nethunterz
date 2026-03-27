# NethunterZ System Architecture

## Overview

NethunterZ is a multi-layer IoT platform consisting of:

1. **ESP32 Firmware** – Real-time embedded firmware (C, FreeRTOS)
2. **Desktop GUI** – Python PyQt5 management application
3. **Quantum Module** – IBM Quantum circuit integration
4. **Flipper Zero App** – Mobile control interface
5. **NRF Radio Runtime** – Dual-module frequency management
6. **Error Resolution** – Automated error monitoring and fix application

---

## Firmware Architecture

### Task Topology

```
app_main()
│
├── errlog_task     (APP_CPU, Pri 3) ──→ NVS ring buffer flush
├── wifi_task       (PRO_CPU, Pri 5) ──→ WiFi STA/AP state machine
│                                         ↓ xEventGroupSetBits(WIFI_CONNECTED)
├── ble_task        (APP_CPU, Pri 5) ──→ GATT server + GAP advertising
├── iot_task        (APP_CPU, Pri 4) ──→ waits WIFI_CONNECTED
│                                         ↓ MQTT pub/sub + metrics
├── power_task      (APP_CPU, Pri 2) ──→ battery ADC + DVFS + sleep
└── ota_task        (APP_CPU, Pri 3) ──→ waits ulTaskNotifyTake()
                                          ↓ HTTPS OTA download + verify + apply
```

### Event Group Bits

| Bit | Name | Set by | Cleared by |
|-----|------|--------|------------|
| 0 | `NOTIF_WIFI_CONNECTED` | wifi_task | wifi_task (disconnect) |
| 1 | `NOTIF_WIFI_DISCONNECTED` | wifi_task | wifi_task (connect) |
| 2 | `NOTIF_BLE_CONNECTED` | ble_task | ble_task (disconnect) |
| 3 | `NOTIF_OTA_TRIGGER` | iot_task / BLE write | ota_task |
| 4 | `NOTIF_SLEEP_REQUEST` | power_task | — |

### Memory Layout (ESP32, 4MB flash)

```
0x00000000  Factory app (256 KB)
0x00010000  OTA Slot 0 (1.5 MB)  ← active firmware
0x001A0000  OTA Slot 1 (1.5 MB)  ← OTA target
0x003D0000  NVS (20 KB)          ← config, error logs
0x003E0000  OTA data (8 KB)      ← boot selection
```

### BLE Service Structure

```
Primary Service (UUID: AB CD EF 01 ...)
├── Control Characteristic (Read/Write)
│   └── Accept JSON commands: {"cmd":"reboot"}, {"cmd":"set_config",...}
├── OTA Characteristic (Notify)
│   └── Push: {"ota_state":2,"progress":50}
└── Status Characteristic (Notify)
    └── Push: {"heap":180000,"uptime":3600,"wifi_rssi":-65}
```

---

## GUI Architecture

```
main.py → MainWindow
          │
          ├── SerialManager (QObject, background thread)
          │   └── signals: connection_changed, data_received, error_occurred
          │
          ├── DashboardTab    ← updates from data_received signal
          ├── FirmwareTab     ← OTAWorker (QThread)
          ├── ErrorLogTab     ← BackgroundResearcher (QThread)
          ├── ConfigTab       ← sends JSON config over serial
          ├── MetricsTab      ← LiveChart (matplotlib Qt5Agg)
          └── QuantumTab      ← QuantumWorker (QThread)
```

### Data Flow: ESP32 → GUI

```
ESP32 UART (115200 baud)
  → JSON line: {"heap":180000,"wifi_rssi":-65,"uptime":3600}
  → SerialManager._read_loop() (background thread)
  → data_received.emit(line)
  → DashboardTab.update_from_serial(data)
  → MetricsTab.update_from_serial(data)
```

---

## Quantum Integration Architecture

```
QuantumManager
├── _initialize()
│   ├── Try: QiskitRuntimeService (IBM Quantum)  ← uses ibm_token
│   └── Fallback: AerSimulator (local)
│
├── build_optimization_circuit() → QAOA, 4 qubits, 2 layers
├── build_crypto_circuit()       → QRNG, 8 qubits
├── build_bell_circuit()         → Bell state, 2 qubits
│
└── run_circuit(circuit, backend, shots)
    ├── _run_ibm()    ← SamplerV2 via Session
    └── _run_local()  → ClassicalFallback.simulate()
        └── _pseudo_random_counts() (worst case fallback)
```

---

## NRF Radio Architecture

```
NRFRuntime (SPI bus 0)
├── Radio A (CE=22, CSN=21) → Scanner mode
│   └── scan_all_channels() → RPD register polling, 126 channels × 5ms
│
├── Radio B (CE=17, CSN=16) → Transmitter mode
│   └── send_packet(data, channel)
│
├── FrequencyManager → score_channel() → select_best_channel()
│   └── Penalises: WiFi channels 1-13, BT even channels 0-80
│   └── Bonuses: channels 76, 100, 110, 120, 125
│
└── BLEBridge
    ├── Inbound queue  → _process_inbound → _route_message
    └── Outbound queue → _process_outbound → _send_to_cloud(HTTPS POST)
```

---

## CI/CD Pipeline

```
git push
│
├── firmware_build.yml   → PlatformIO build (esp32/s2/s3/c3)
│                          → Upload firmware.bin artifact
│
├── gui_test.yml         → PyQt5 import tests
│                          → Quantum circuit tests
│                          → flake8 lint
│
├── sandbox_test.yml     → pytest (test_firmware, test_ble, test_wifi, test_quantum)
│                          → Runtime benchmarks
│                          → Upload test-results.json
│
└── release.yml (on tag) → Build all 4 firmware variants
                           → Run pre-release tests
                           → Create GitHub Release with .bin attachments
```
