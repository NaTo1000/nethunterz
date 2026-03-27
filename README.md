# NetHunterz – NayDoeV1 Flipper Zero Firmware Update

> **NayDoeV1 × NetHunterz** — Custom Flipper Zero firmware with an 80s-themed GUI,
> cloud filesystem integration, OTA updates, and full NetHunterz stack connectivity.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Firmware Flashing Instructions](#firmware-flashing-instructions)
4. [80s Scene Animations](#80s-scene-animations)
5. [Cloud Setup Guides](#cloud-setup-guides)
6. [Companion App Setup](#companion-app-setup)
7. [Security & Trail-Wipe](#security--trail-wipe)
8. [Theme Customisation](#theme-customisation)
9. [Developer Guide](#developer-guide)

---

## Overview

The **NayDoeV1 Flipper Zero Firmware** delivers:

| Feature | Description |
|---|---|
| **NayDoeV1 GUI** | 80s-retro typewriter-font interface for the 128×64 mono LCD |
| **Boot Splash** | Animated NayDoeV1 bot + Flipper dolphin boot sequence |
| **80s Scenes** | Baywatch, Miami Vice, Knight Rider, Bionic Man, Top Gun, Tron, BTTF |
| **OTA Updates** | Over-The-Air firmware updates via BLE companion bridge |
| **Cloud Filesystem** | AES-256 encrypted delta-sync to Google Drive, OneDrive, or VPS |
| **Security** | Trail-wipe, MAC randomisation, encrypted BLE, audit logging |
| **Companion Bridge** | BLE bridge offloading AI inference, cloud auth, and heavy transfers |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Flipper Zero Device                   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  NayDoeV1GUI │  │  Scenes80s   │  │ SplashScreen │  │
│  │  (128×64 LCD)│  │ (7 scenes)   │  │ (boot anim)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  OTAUpdater  │  │SecurityMgr   │  │CompanionBrdge│  │
│  │  (BLE OTA)   │  │(AES-256/wipe)│  │ (BLE bridge) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │ BLE
              ┌───────────┴────────────┐
              │    Companion App       │
              │  (mobile / desktop)    │
              │  - Cloud OAuth2        │
              │  - AI inference        │
              │  - Firmware compile    │
              └───────────┬────────────┘
                          │ HTTPS / SSH
       ┌──────────────────┼──────────────────┐
       │                  │                  │
  Google Drive       OneDrive             VPS/Docker
  (BLCKjACK/)       (BLCKjACK/)         (/opt/blckjack)
```

### Minimal Runtime Architecture

The Flipper Zero runs only essential services:
- BLE communication stack (`CompanionBridge`)
- UI rendering engine (`NayDoeV1GUI`, `SplashScreen`, `Scenes80s`)
- Minimal local cache for offline operation
- Security and encryption modules (`SecurityManager`)

Everything else is offloaded:
- AI processing → companion app / Grok 420 cloud
- Firmware compilation → companion app
- Cloud sync → companion app → cloud provider
- Heavy analytics → JessicAi Medusa Cyberstack

---

## Firmware Flashing Instructions

### Prerequisites

```bash
pip install -r requirements.txt
```

### Quick Start (Simulation)

```python
from flipper import NayDoeV1GUI, SplashScreen, OTAUpdater, SecurityManager

# Boot sequence
splash = SplashScreen(simulation=True)
await splash.play_boot_sequence()

# Launch GUI
gui = NayDoeV1GUI(simulation=True)
gui.update_device_status(ble=True, cloud=True)
frame = gui.render_frame()

# Check for OTA update
ota = OTAUpdater(current_version="1.0.0", simulation=True)
await ota.run_full_update()
```

### Real Device Flashing

1. Connect Flipper Zero via USB
2. Put device in DFU/recovery mode (hold `←` + `⏎` on boot)
3. Use the companion app to compile and transfer firmware:
   ```
   companion-app flash --device /dev/ttyUSB0 --firmware build/flipper/firmware_1.1.0.bin
   ```
4. The OTAUpdater handles verification (SHA-256) and flashing automatically

---

## 80s Scene Animations

Seven scene animations are available for idle, boot, and screensaver use.

### Available Scenes

| Scene | Characters | Palette | Tagline |
|---|---|---|---|
| `baywatch` | Dolphin + NayDoeV1 on beach | Warm orange/red | "RUNNING IN SLOW-MO..." |
| `miami_vice` | Both in convertible | Pink + cyan neon | "VICE CITY: NEON NEVER DIES" |
| `knight_rider` | NayDoeV1 driving KITT | Red + black | "TURBO BOOST!" |
| `bionic_man` | Bionic dolphin | Blue + silver | "6 MILLION CYCLES" |
| `top_gun` | Aviator duo + jet | Sky blue + gold | "DANGER ZONE" |
| `tron` | Both on grid | Neon blue + orange | "ENTERING THE GRID..." |
| `back_to_the_future` | DeLorean + flux cap | Lightning chrome | "88MPH! FLUX CAPACITOR" |

### Usage

```python
from flipper import Scenes80s, SceneType

scenes = Scenes80s(simulation=True)

# Play as idle animation (120 frames)
await scenes.play_scene(SceneType.BAYWATCH, num_frames=120)

# Render individual frames for screensaver
scenes.set_scene(SceneType.TRON)
frame = scenes.render_next_frame()
```

### Creating Custom 80s Scenes

1. Add your `SceneType` entry to `flipper/scenes_80s.py`
2. Add a tagline to `SCENE_TAGLINES`
3. Implement a generator function `_your_scene_frame(tick: int) -> DisplayFrame`
4. Register it in `_SCENE_GENERATORS`

Pixel art tips for the 128×64 mono LCD:
- Use `DisplayFrame.draw_rect()` for solid shapes
- Use `DisplayFrame.set_pixel()` for individual dots and line art
- Use `DisplayFrame.apply_dither()` for grayscale depth simulation
- Animate using the `tick` parameter (increments each frame at ~12 fps)

---

## Cloud Setup Guides

### Google Drive

```python
from cloud import GDriveSync, GDriveConfig

gd = GDriveSync(config=GDriveConfig(client_id="YOUR_CLIENT_ID"))

# 1. Get auth URL (open in companion app browser)
url = gd.get_auth_url()

# 2. Authenticate with returned code
await gd.authenticate(auth_code="CODE_FROM_BROWSER")

# 3. Create BLCKjACK folder structure
folders = await gd.create_folder_structure()

# 4. Upload files
await gd.upload("BLCKjACK/logs/session.log", log_data)
```

### Microsoft OneDrive

```python
from cloud import OneDriveSync, OneDriveConfig

od = OneDriveSync(config=OneDriveConfig(client_id="YOUR_CLIENT_ID"))
await od.authenticate(auth_code="CODE_FROM_BROWSER")
await od.create_folder_structure()
await od.upload("BLCKjACK/firmware_backups/fw_1.1.0.bin", firmware_data)
```

### VPS (Self-Hosted)

```python
from cloud import VPSSync, VPSConfig

vps = VPSSync(config=VPSConfig(host="your-vps.example.com", username="admin"))

# Generate and run the auto-install script
print(vps.generate_install_script())  # Review before running
await vps.connect()
await vps.run_install_script()        # Installs Docker + BLCKjACK stack
await vps.upload(firmware_data, "firmware_backups/fw_1.1.0.bin")
```

### Cloud Sync Engine

```python
from cloud import CloudFilesystem, SyncConfig, SyncProvider, SyncSchedule

fs = CloudFilesystem(config=SyncConfig(
    provider=SyncProvider.GOOGLE_DRIVE,
    schedule=SyncSchedule.HOURLY,
    encrypt_in_transit=True,
    delta_sync=True,
))

# Create local BLCKjACK folder structure
fs.create_blckjack_structure(Path("/opt/blckjack"))

# Index and sync files
fs.index_file(Path("/opt/blckjack/logs/session.log"))
await fs.sync_once()

# Start background sync daemon
await fs.start_background_sync()
```

---

## Companion App Setup

The companion app handles all heavy operations offloaded from the Flipper Zero.

### Pairing

```python
from flipper import CompanionBridge

bridge = CompanionBridge(device_name="NayDoeV1-Flipper")
await bridge.start_advertising()
# Companion app scans and connects
result = await bridge.pair(companion_key_hash)
```

### Offloading Operations

```python
# Request cloud authentication
await bridge.request_cloud_auth("google_drive")

# Offload AI inference
await bridge.request_ai_inference(prompt_bytes)

# Download a new scene animation pack
await bridge.request_scene_download("tron")
```

### Receiving Firmware Updates

```python
# Companion app initiates transfer
session = bridge.start_transfer("firmware", total_bytes=65536)
for chunk in firmware_chunks:
    bridge.receive_chunk(session.session_id, chunk)

# Once complete, flash
if session.complete:
    firmware_data = session.assemble()
    await ota.flash_firmware(tmp_path / "fw.bin")
```

---

## Security & Trail-Wipe

### AES-256 Encrypted BLE

All BLE communication is encrypted with AES-256-GCM:

```python
from flipper import SecurityManager

sm = SecurityManager()
encrypted = sm.encrypt_ble_payload(b"BLE command data")
decrypted = sm.decrypt_ble_payload(encrypted)
```

### MAC Address Randomisation

```python
new_mac = sm.randomise_mac()   # e.g., "02:a1:b2:c3:d4:e5"
sm.anonymise_ip()              # Logs intent; routing handled by OS/VPN
```

### One-Button Trail Wipe

Securely erases all local Flipper data with a single call:

```python
result = sm.trail_wipe(data_dirs=[
    Path("/opt/blckjack/logs"),
    Path("/opt/blckjack/configurations"),
])
# result = {"wiped_files": N, "cleared_events": M, "key_rotated": True}
```

**Wipe modes** (configurable via `SecurityConfig.wipe_mode`):
- `SINGLE_PASS` — one zero-overwrite pass
- `DOD_3_PASS` — DoD 5220.22-M (zeros → ones → random)
- `GUTMANN_7` — 7-pass random overwrite

### Auto-Wipe on Auth Failures

Configure `max_failed_auth` in `SecurityConfig` to auto-trigger trail-wipe
after N failed companion app authentication attempts.

---

## Theme Customisation

### Changing the Active Scene

The GUI Settings panel (`MenuSection.SETTINGS`) controls the active theme:

```python
gui = NayDoeV1GUI()
gui.state.active_section = MenuSection.SETTINGS
frame = gui.render_frame()  # Shows settings with current theme
```

### Pixel Art Asset Guidelines

- **Canvas size**: 128×64 pixels (1-bit monochrome)
- **Sprite size**: 10×11 for characters, 40×16 for vehicles
- **Frame rate**: target 12 fps (80 ms per frame)
- **Dithering**: use `DisplayFrame.apply_dither()` for depth effects
- **Text**: 5×7 pixel typewriter font, max 21 characters per row at x=2

---

## Developer Guide

### Running Tests

```bash
pytest tests/ -v --tb=short
```

### Linting

```bash
flake8 flipper/ cloud/ tests/ --max-line-length=100 --extend-ignore=E203,W503
```

### Module Structure

```
flipper/
├── __init__.py          # Package exports
├── aio_flipper.py       # AIO Flipper board integration
├── ai_updater.py        # AI-controlled firmware update manager
├── firmware_builder.py  # Firmware build and packaging
├── gui.py               # NayDoeV1 80s-themed GUI system
├── splash_screen.py     # Boot splash + animated sequences
├── scenes_80s.py        # 80s movie/TV scene animations
├── ota_updater.py       # OTA firmware update engine
├── security.py          # AES-256, trail-wipe, MAC randomisation
└── companion_bridge.py  # BLE companion app bridge

cloud/
├── __init__.py          # Package exports
├── cloud_fs.py          # Delta-sync engine + AES-256 transfer
├── gdrive_sync.py       # Google Drive OAuth2 connector
├── onedrive_sync.py     # Microsoft OneDrive Graph API connector
└── vps_sync.py          # VPS SSH/SFTP + Docker auto-install
```

### NetHunterz Stack Integration

This firmware integrates with the full NetHunterz stack:
- **JessicAi Medusa Cyberstack** — AI decision offloading via `CompanionBridge.request_ai_inference()`
- **Grok 420 Orchestration** — OTA managed by `OTAUpdater` with orchestration hook points
- **BLCKjACK Arch** — VPS nodes auto-provisioned by `VPSSync.run_install_script()`
- **LoRa Mesh** — Status visible in `NayDoeV1GUI` Dashboard panel
- **ESP32** — Connected devices tracked in `GUIState.connected_devices`
