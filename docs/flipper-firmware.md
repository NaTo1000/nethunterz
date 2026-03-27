# Flipper Zero Firmware Guide

## Overview

The NetHunterz Flipper Zero firmware integrates NayDoeV1 AI with a spectacular
80s-themed GUI featuring:
- Full boot animation with Dolphin + NayDoeV1 bot
- Typewriter text effects
- Five 80s theme modes
- Real-time operations dashboard
- Network map visualization
- Voice activity indicator
- Device constellation view

## Themes

### Available Themes

| Theme | Inspiration | Primary Color | Tagline |
|-------|-------------|---------------|---------|
| `naydoe_default` | NayDoeV1 | Neon Purple/Green | NayDoeV1 ONLINE |
| `miami_vice` | Miami Vice (1984) | Hot Pink/Teal | MIAMI VICE MODE ENGAGED |
| `baywatch` | Baywatch (1989) | Crimson/Gold | RUNNING ON THE BEACH... |
| `night_rider` | Knight Rider (1982) | Cyan/Blue | K.I.T.T. ONLINE |
| `bionic_man` | Six Million Dollar Man | Silver/Green | WE CAN REBUILD IT |

### Switching Themes

```python
from flipper.firmware import FlipperZeroFirmware

flipper = FlipperZeroFirmware(theme="miami_vice")
await flipper.boot()

# Switch themes at runtime
flipper.switch_theme("night_rider")
flipper.switch_theme("baywatch")
```

## Boot Sequence

The boot sequence plays automatically on startup:

1. **Dolphin Animation** — Dolphin swims and jumps (3 frames)
2. **NayDoeV1 Bot** — Bot appears, waves, starts hacking (3 frames)
3. **Splash Screen** — Full NayDoeV1 ASCII art logo
4. **Typewriter Messages** — 10 status messages typed out in real-time:
   - "INITIALIZING NAYDOEV1 CONDUCTOR..."
   - "LOADING PINEDAP MODULES..."
   - "ESTABLISHING ENCRYPTED CHANNELS..."
   - "AI SUBSYSTEMS: ONLINE"
   - ... (10 total)

```python
frames = await flipper.boot()
for frame in frames:
    print(frame)  # Render each animation frame
```

## Screens

### Dashboard (`FlipperScreen.DASHBOARD`)
Shows:
- System uptime
- AI/Voice status
- Operations: registered / completed / success
- Active PineDAP modules count

### Network Map (`FlipperScreen.NETWORK_MAP`)
Shows discovered networks with:
- SSID names
- Signal strength bars

### Voice Indicator (`FlipperScreen.VOICE`)
Shows:
- Active/Inactive indicator (●/○)
- Audio waveform animation when active
- Current transcript/transcription

### Device Constellation
Shows all connected NetHunterz devices with online/offline status.

## Typewriter Effect

```python
from flipper.firmware import TypewriterEffect

tw = TypewriterEffect(speed_ms=50)
tw.set_text("INITIALIZING NAYDOEV1...")
result = await tw.animate_full()
print(result)
```

## Cloud Filesystem Integration

The Flipper Zero can install and sync with the cloud filesystem:

```python
from cloud import CloudFilesystem

cloud = CloudFilesystem.setup_google_drive(root_path="/nethunterz")
flipper = FlipperZeroFirmware(cloud_filesystem=cloud)
await flipper.boot()
await flipper.install_cloud_filesystem()
```

## Minimal Runtime Footprint

The firmware is designed for minimal RAM/CPU footprint on the Flipper Zero:
- All heavy AI processing delegated to the connected Pineapple Pager
- Only rendering and I/O handled locally
- Animations use ASCII art (no binary assets)
- Cloud sync runs on a separate thread with configurable interval
