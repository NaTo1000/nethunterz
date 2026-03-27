# NethunterZ Installation Guide

## Prerequisites

- Python 3.9+
- Git
- USB cable (for ESP32 flashing)
- ESP32 development board (esp32dev, ESP32-S2/S3/C3)

---

## 1. Flashing ESP32 Firmware

### Using PlatformIO (recommended)

```bash
# Install PlatformIO
pip install platformio

# Clone and enter project
git clone https://github.com/nethunterz/nethunterz.git
cd nethunterz

# Build and flash
cd firmware
pio run -e esp32 --target upload --upload-port /dev/ttyUSB0

# Monitor serial output
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

### Using the flash script

```bash
# Full install + build + flash
./scripts/install_dependencies.sh
./scripts/flash_firmware.sh --build --port /dev/ttyUSB0 --monitor
```

### Using esptool directly (pre-built binaries)

```bash
pip install esptool

esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 \
  write_flash -z \
  0x1000  bootloader.bin \
  0x8000  partitions.bin \
  0x10000 firmware.bin
```

### Linux serial port permissions

```bash
sudo usermod -aG dialout $USER
# Log out and back in, or:
sudo chmod 666 /dev/ttyUSB0
```

---

## 2. Setting Up the GUI (Computer)

### Install Python dependencies

```bash
cd gui
pip install -r requirements.txt
```

### Launch the GUI

```bash
./scripts/run_gui.sh
# or directly:
cd gui && python main.py
```

### Connecting to ESP32

1. Connect ESP32 via USB
2. In GUI: **File → Connect Serial**
3. Select the correct COM port (Windows: `COM3`, Linux: `/dev/ttyUSB0`, macOS: `/dev/cu.usbserial-*`)
4. The Dashboard will start receiving live data

---

## 3. Installing the Flipper Zero App

### Requirements

- Flipper Zero with firmware 0.94+
- [ufbt](https://github.com/flipperdevices/flipperzero-ufbt) (micro Flipper Build Tool)

### Build and install

```bash
# Install ufbt
pip install ufbt

# Build the app
cd flipper/esp32_controller
ufbt build

# Deploy to connected Flipper Zero
ufbt launch
```

### Manual install (pre-built .fap)

Copy the `.fap` file to your Flipper's SD card:
```
/ext/apps/GPIO/esp32_controller.fap
```

---

## 4. Configuring IBM Quantum

### Get an IBM Quantum API token

1. Create a free account at [quantum.ibm.com](https://quantum.ibm.com)
2. Navigate to **Account → API Token**
3. Copy your token

### Configure in GUI

1. Open the **Quantum** tab
2. Paste your API token in the **API Token** field
3. Select a backend (e.g., `ibm_qasm_simulator` for free tier)
4. Click **Run Quantum Circuit**

### Configure programmatically

```python
from quantum.quantum_manager import QuantumManager

qm = QuantumManager(ibm_token="YOUR_TOKEN_HERE")
circuit = qm.build_optimization_circuit()
result = qm.run_circuit(circuit, "ibm_qasm_simulator", shots=1024)
params = qm.extract_optimized_params(result)
print(params)
```

### Without a token (local simulation)

Leave the token field empty. The system automatically uses Qiskit Aer local simulator.

---

## 5. NRF24L01+ Setup (Raspberry Pi)

### Hardware connections

**Radio A (Scanner):**
| NRF24L01+ | Raspberry Pi GPIO |
|-----------|------------------|
| CE        | GPIO 22          |
| CSN       | GPIO 21          |
| SCK       | GPIO 11 (SPI CLK)|
| MOSI      | GPIO 10          |
| MISO      | GPIO 9           |
| VCC       | 3.3V             |
| GND       | GND              |

**Radio B (Transmitter):** CE=GPIO17, CSN=GPIO16, shared SPI bus.

### Install Raspberry Pi dependencies

```bash
sudo apt-get install python3-dev
pip install spidev RPi.GPIO

# Enable SPI
sudo raspi-config  # → Interface Options → SPI → Enable
```

### Run

```bash
./scripts/runtime_nrf.sh --interval 30 --log /var/log/nrf_scan.jsonl
```

---

## 6. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ESP_PORT` | `/dev/ttyUSB0` | Serial port for flashing |
| `ESP_BAUD` | `921600` | Upload baud rate |
| `ESP_CHIP` | `esp32` | Target chip |
| `DISPLAY` | *(auto)* | X11 display for GUI |
| `CE_A` | `22` | NRF Radio A CE GPIO |
| `CSN_A` | `21` | NRF Radio A CSN GPIO |
| `SCAN_INTERVAL` | `30` | NRF scan interval seconds |
