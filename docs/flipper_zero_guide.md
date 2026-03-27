# Flipper Zero App Guide

## Overview

The NethunterZ Flipper Zero app provides a portable control interface for your ESP32 device, accessible without a computer.

## Navigation

| Button | Action |
|--------|--------|
| ↑ / ↓ | Navigate menu / scroll error logs |
| OK     | Select / confirm action |
| Back   | Return to previous screen |
| Left / Right | (reserved for future use) |

## Main Menu

```
┌──────────────────────┐
│  NethunterZ ESP32    │
├──────────────────────┤
│ ► BLE Status         │
│   Error Logs         │
│   Trigger OTA        │
│   Diagnostics        │
│   Freq Scanner       │
│   Exit               │
└──────────────────────┘
```

## Screens

### BLE Status
Shows the current BLE connection state with the ESP32:
- **Disconnected** – Press OK to initiate scan
- **Scanning...** – Actively searching for NethunterZ device
- **Connected** – Shows firmware version, IP address, WiFi RSSI

### Error Logs
Fetches and displays the ESP32 error ring buffer:
- Shows timestamp, error message
- Use ↑/↓ to scroll through up to 64 entries
- Errors are fetched fresh on each visit

### Trigger OTA
Sends an OTA update command to the connected ESP32:
- Device must be BLE connected
- Shows progress bar (0–100%)
- Device reboots automatically after successful update

### Diagnostics
Live device metrics:
- Free heap memory (bytes)
- Battery voltage (mV)
- Uptime (seconds)
- WiFi / MQTT connection status indicators

### Frequency Scanner
Scans 2.4 GHz spectrum (channels 1–13):
- Identifies clearest channel with lowest interference
- Shows best channel number and estimated RSSI
- Results update on each scan

## Building the App

```bash
pip install ufbt
ufbt update
cd flipper/esp32_controller
ufbt build
ufbt launch
```

## Troubleshooting

**App won't install:** Ensure Flipper firmware is 0.94 or later.

**BLE scan finds nothing:** Ensure ESP32 is powered, BLE advertising is active, and Flipper is within 10m.

**OTA trigger has no effect:** BLE connection required; verify ESP32 WiFi is connected and OTA_UPDATE_URL is set.
