# NetHunterZ – Setup Guide

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| Raspberry Pi / Linux host | Python 3.10+ |
| Pingequa Dual NRF board | Two NRF24L01+ modules on SPI bus |
| Android phone | Android 8.0+ (API 26) with BLE 5.0 |
| Cloud (optional) | Any host with Python 3.11 / Docker |

---

## 1. Clone the repository

```bash
git clone https://github.com/NaTo1000/nethunterz.git
cd nethunterz
```

## 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### Optional – real hardware

```bash
pip install RF24               # Pingequa NRF hardware driver
pip install bless              # BLE GATT server (Linux/BlueZ)
pip install serial-asyncio     # Flipper serial over USB
```

---

## 3. Run the NRF Module runtime

### Simulation mode (no hardware required)

```bash
python -m nrf_module.runtime --simulation
```

### Real hardware mode

```bash
# ensure NRF modules are wired on /dev/spidev0.0 (CE=GPIO17)
python -m nrf_module.runtime --no-simulation --log-dir /var/log/nethunterz
```

### With frequency hopping enabled

```bash
python -m nrf_module.runtime --simulation --hop
```

---

## 4. Module configuration

Modules default to:

| Module | Channel | Frequency | Data Rate |
|--------|---------|-----------|-----------|
| Primary (0) | 76 | 2476 MHz | 1 Mbps |
| Secondary (1) | 100 | 2500 MHz | 1 Mbps |

To change defaults, edit `nrf_module/pingequa_dual_nrf.py` and adjust `ModuleConfig`.

---

## 5. Start the cloud API server

```bash
CLOUD_API_KEY=your-secret-key python -m cloud.api_server
```

Or with Docker:

```bash
docker build -f cloud/Dockerfile -t nethunterz-cloud .
docker run -p 8080:8080 -e CLOUD_API_KEY=your-secret-key nethunterz-cloud
```

---

## 6. Connect the Android app

1. Build and install the APK from `android_app/`.
2. Tap **Scan for Devices** – the app will find the `NetHunterZ-NRF` BLE device.
3. Once connected, live packet data and module status appear in the main dashboard.
4. Use the **Frequency Upgrade** card to hot-switch channels without stopping capture.
5. View **Logs** for full packet history and operational events.
6. Open **Freq Tracker** to see the channel-change graph.

---

## 7. Flipper AIO board

```bash
FLIPPER_PORT=/dev/ttyACM0 python - <<'EOF'
import asyncio
from flipper.aio_flipper import AIOFlipperController
from flipper.ai_updater import AIFirmwareUpdater

async def main():
    fc = AIOFlipperController(simulation=False)
    await fc.connect()
    info = await fc.get_info()
    print(info)
    updater = AIFirmwareUpdater(fc, auto_approve=False)
    await updater.start()
    await asyncio.sleep(10)
    await updater.stop()
    await fc.disconnect()

asyncio.run(main())
EOF
```

---

## 8. Environment variables

| Variable | Purpose |
|----------|---------|
| `CLOUD_ENDPOINT` | Base URL of cloud API |
| `CLOUD_API_KEY` | Bearer token for cloud auth |
| `CLOUD_DEVICE_ID` | Unique device identifier |
| `NRF_BLE_SECRET` | Shared secret for BLE HMAC auth |
| `NRF_LOG_KEY` | AES-256-GCM key (hex) for encrypted logs |
| `ALERT_WEBHOOK_URL` | Webhook URL for security alerts |
| `FLIPPER_PORT` | Serial device for Flipper board |
| `FIRMWARE_RELEASE_ENDPOINT` | URL for firmware update checks |
| `FIRMWARE_API_KEY` | API key for firmware release server |
