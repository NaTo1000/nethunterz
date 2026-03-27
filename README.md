# NetHunterZ

**NetHunterZ** is a comprehensive Android platform that integrates the Kali NetHunter penetration testing environment with Flipper Zero hardware control, AI-powered autonomous decision making, and cloud-based firmware management.

---

## 🚀 Features

| Feature | Description |
|---|---|
| **Flipper Zero Integration** | USB CDC, UART (115200 baud), and Bluetooth SPP/BLE drivers |
| **Autonomous AI Control** | TFLite on-device ML + rule-based hybrid decision engine |
| **Firmware Management** | Build, validate, sign, and OTA-update Flipper firmware |
| **Cloud Storage** | AWS S3 and Google Cloud Storage firmware distribution |
| **Dashboard** | Flask REST API + web UI for firmware release management |
| **Kali Chroot** | Boot/manage Kali NetHunter chroot from Android |
| **HID/BadUSB** | DuckyScript payload generation and execution via Flipper |

---

## 📁 Repository Structure

```
nethunterz/
├── nethunter-app/           # Android application
│   ├── manifests/           # AndroidManifest.xml
│   ├── java/com/offsec/nethunter/
│   │   ├── flipper/         # Flipper Zero drivers (USB, UART, BT, Protocol)
│   │   ├── ai/              # AI Controller, ML Model, Decision Engine
│   │   ├── cloud/           # CloudStorageManager, CloudDashboardClient
│   │   ├── GPS/             # NMEA parser
│   │   ├── service/         # NethunterService (foreground)
│   │   └── utils/           # SystemUtils, shell command helpers
│   ├── res/                 # Layouts, strings, colors, menus
│   └── assets/              # Scripts, init.d, duckscripts, HID modules
├── firmware/
│   ├── builder/             # build_firmware.py + firmware_config.json
│   ├── validator/           # validate_firmware.py
│   └── updater/             # autonomous_updater.py
├── ai/
│   ├── models/              # flipper_control_model.py (TensorFlow/Keras)
│   ├── decision_engine/     # engine.py + rules.json
│   └── training/            # train_model.py
├── cloud/
│   ├── storage/             # s3_uploader.py, gcs_uploader.py
│   └── dashboard/           # Flask dashboard server + HTML template
├── security/
│   ├── signing/             # sign_firmware.sh, verify_firmware.sh
│   └── crypto/              # FirmwareSigner.java
├── .github/workflows/       # CI/CD pipelines
│   ├── android-build.yml
│   ├── flipper-firmware.yml
│   ├── nightly-build.yml
│   ├── deploy-cloud.yml
│   └── security-scan.yml
└── docs/                    # Full project documentation
```

---

## 🔧 Quick Start

### Android App

```bash
# Build debug APK
./gradlew assembleDebug

# Run unit tests
./gradlew test
```

Requirements: JDK 17, Android SDK (API 34), Gradle 8.2

### Firmware Builder

```bash
pip install ufbt scons requests
python firmware/builder/build_firmware.py \
    --version 1.0.0 \
    --config firmware/builder/firmware_config.json \
    --output firmware/build/output
```

### AI Model Training

```bash
pip install tensorflow numpy
python ai/training/train_model.py --epochs 30 --output ai/models/output
```

### Cloud Dashboard

```bash
pip install flask requests
python cloud/dashboard/dashboard_server.py
# Access at http://localhost:5000
```

---

## 📱 Flipper Zero Connection

The app auto-connects to Flipper Zero in priority order:
1. **USB CDC** (VID: `0x0483`, PID: `0x5740`)
2. **UART** (`/dev/ttyACM0` at 115200 baud, requires root)
3. **Bluetooth SPP** (searches paired "Flipper *" devices)

---

## 🤖 AI Autonomous Mode

The AI system monitors Flipper state and autonomously takes actions:

```java
AIController ai = new AIController(context, flipperManager);
ai.initialize();
ai.startAutonomousMode();
```

Actions require ≥75% confidence before execution. Rules are defined in `ai/decision_engine/rules.json`.

---

## 🔄 CI/CD Workflows

| Workflow | Trigger | Description |
|---|---|---|
| `android-build.yml` | Push/PR | Build APK + run tests |
| `flipper-firmware.yml` | Push/PR/manual | Build + validate + sign firmware |
| `nightly-build.yml` | 02:00 UTC daily | Full nightly build + release |
| `deploy-cloud.yml` | GitHub release | Deploy firmware to S3/GCS |
| `security-scan.yml` | Push/PR/weekly | CodeQL + OWASP + secret scan |

---

## 📚 Documentation

See the [`docs/`](docs/) directory for complete documentation:

- [Flipper Integration](docs/flipper-integration.md)
- [AI Control](docs/ai-control.md)
- [Firmware Management](docs/firmware-management.md)
- [Cloud Setup](docs/cloud-setup.md)
- [CI/CD Pipeline](docs/ci-cd.md)

---

## ⚠️ Disclaimer

This tool is intended for **authorized security research and penetration testing only**. Use only on systems you own or have explicit written permission to test. The authors are not responsible for misuse.