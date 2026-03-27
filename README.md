# JessicAi Medusa Cyberstack

<div align="center">

![Platform](https://img.shields.io/badge/Platform-iOS%2016%2B-blue?logo=apple)
![Swift](https://img.shields.io/badge/Swift-5.9-orange?logo=swift)
![License](https://img.shields.io/badge/License-MIT-green)
![CI](https://github.com/nethunterz/nethunterz/actions/workflows/ios-build.yml/badge.svg)

**A professional full-HD iPhone cybersecurity platform** combining LoRa mesh networking, BLE device management, AI-driven threat response, and quantum-enhanced cryptography.

</div>

---

## Features

| Module | Description |
|--------|-------------|
| 🛡️ **Auth** | Face ID / Touch ID biometric gate with fallback |
| 📡 **LoRa Telemetry** | 433 / 868 / 915 MHz half-duplex mesh, seek-and-find, beacon mode |
| 🔵 **BLE & Flipper Zero** | Scan, connect, OTA-update Flipper Zero, NRF modules, ESP32 boards |
| 📍 **Geofencing** | CLLocationManager regions + AI attack-mirror defensive response |
| 🧠 **JessicAi Orchestration** | Autonomous decision engine with command terminal + IBM Quantum panel |
| ⚙️ **Settings** | Dark / light theme, re-auth, AES-256 encryption indicator |

## Architecture

```
ios/JessicAiMedusaCyberstack/
├── JessicAiMedusaCyberstackApp.swift   # @main entry point
├── AppState.swift                       # Global ObservableObject
├── Views/
│   ├── AuthView.swift
│   ├── MainTabView.swift
│   ├── DashboardView.swift
│   ├── LoRaTelemetryView.swift
│   ├── BLEFlipperView.swift
│   ├── GeofenceView.swift
│   ├── AIOrchestrationView.swift
│   └── SettingsView.swift
├── Models/
│   ├── LoRaNode.swift
│   ├── BLEDevice.swift
│   ├── GeofenceZone.swift
│   ├── AIDecision.swift
│   └── ESP32Device.swift
├── Services/
│   ├── LoRaManager.swift
│   ├── BLEManager.swift
│   ├── GeofenceManager.swift
│   ├── AIOrchestrator.swift
│   ├── QuantumCryptoService.swift
│   └── ESP32FirmwareService.swift
└── Resources/
    └── Info.plist
```

## Requirements

- Xcode 15.4+
- iOS 16.0+ deployment target
- Swift 5.9+
- iPhone with Face ID / Touch ID (simulator falls back automatically)

## Getting Started

```bash
git clone https://github.com/nethunterz/nethunterz.git
cd nethunterz
open ios/JessicAiMedusaCyberstack.xcodeproj
```

Select an iPhone 15 Pro simulator and press ▶.

## CI/CD

GitHub Actions workflow at `.github/workflows/ios-build.yml` runs:
1. **SwiftLint** on every push / PR
2. **Build + Unit Tests** on iPhone 15 Pro iOS 17 simulator
3. **Release Archive** on merges to `main`

## Permissions

| Permission | Usage |
|-----------|-------|
| `NSBluetoothAlwaysUsageDescription` | Flipper Zero / NRF / ESP32 BLE communication |
| `NSLocationAlwaysAndWhenInUseUsageDescription` | Geofence monitoring |
| `NSFaceIDUsageDescription` | Biometric authentication |
| `NSLocalNetworkUsageDescription` | ESP32 Wi-Fi gateway communication |

## Stack

- **SwiftUI** — full HD adaptive layout
- **CoreBluetooth** — BLE scanning and OTA
- **CoreLocation** — geofence regions
- **LocalAuthentication** — Face ID / Touch ID
- **MapKit** — geofence map overlay
- **Combine** — reactive state management
- **IBM Quantum (simulated)** — QKD key rotation

---

*Powered by the NetHunterz security stack.*