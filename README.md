# NetHunter – Android Security & Penetration Testing Platform

[![Build APK](https://github.com/nethunterz/nethunterz/actions/workflows/build.yml/badge.svg)](https://github.com/nethunterz/nethunterz/actions/workflows/build.yml)
[![Tests](https://github.com/nethunterz/nethunterz/actions/workflows/test.yml/badge.svg)](https://github.com/nethunterz/nethunterz/actions/workflows/test.yml)
[![Lint](https://github.com/nethunterz/nethunterz/actions/workflows/lint.yml/badge.svg)](https://github.com/nethunterz/nethunterz/actions/workflows/lint.yml)

NetHunter is an Android penetration testing platform based on the [Kali Linux NetHunter](https://www.kali.org/docs/nethunter/) project. It provides a native Android application that manages a Kali Linux chroot environment, offers GPS/NMEA spoofing utilities, a USB HID injection framework (DuckHunter), and a built-in terminal.

---

## Features

| Feature | Description |
|---------|-------------|
| **Kali Chroot** | Mount/unmount the Kali Linux chroot with bind-mounts for `/proc`, `/sys`, `/dev` |
| **GPS / NMEA** | Parse NMEA 0183 sentences from gpsd; inject mock Android locations |
| **DuckHunter** | USB HID keyboard injection via `/dev/hidg0` using DuckScript payloads |
| **Terminal** | In-app shell terminal with root command execution |
| **Services** | Foreground service management with auto-restart policies |
| **Boot receiver** | Optionally auto-start services on device boot |

---

## Requirements

- Rooted Android device (API 21+)
- Kali NetHunter chroot installed at `/data/local/nhsystem/kali-<arch>`
- `su` binary accessible in `PATH`

---

## Project Structure

```
nethunterz/
├── nethunter-app/
│   ├── manifests/
│   │   └── AndroidManifest.xml
│   ├── java/com/offsec/nethunter/
│   │   ├── GPS/
│   │   │   ├── GPSService.java          # Foreground GPS service + mock location
│   │   │   ├── NMEAParser.java          # Full NMEA 0183 parser
│   │   │   └── NMEADataStreamer.java     # File/socket NMEA streaming
│   │   ├── service/
│   │   │   ├── NetHunterService.java    # Core chroot foreground service
│   │   │   └── ServiceManager.java      # Service registry + health-check
│   │   ├── updateReceiver/
│   │   │   ├── BootReceiver.java        # Auto-start on boot
│   │   │   └── UpdateReceiver.java      # Re-extract assets after update
│   │   ├── utils/
│   │   │   ├── FileManager.java         # Asset extraction, ZIP, checksum
│   │   │   ├── Logger.java              # Rotating file logger
│   │   │   ├── NetHunterPaths.java      # All path constants
│   │   │   ├── ShellExecutor.java       # Root/non-root shell execution
│   │   │   └── SystemUtils.java         # Root detection, arch, CPU/RAM info
│   │   ├── MainActivity.java
│   │   ├── NetHunterApplication.java
│   │   └── *Fragment.java               # GPS, Services, Terminal, Settings
│   ├── assets/
│   │   ├── etc.init.d/99nethunter       # Chroot init script
│   │   ├── scripts/bootkali             # Chroot mount/launch script
│   │   ├── nh_files/modules/
│   │   │   ├── keyseed.py               # HID key report generator
│   │   │   └── duckhunter.py            # DuckScript interpreter
│   │   └── nh_files/duckscripts/        # Sample DuckScript payloads
│   └── res/                             # Layouts, drawables, values
├── .github/workflows/
│   ├── build.yml                        # Build debug + release APKs
│   ├── test.yml                         # Unit tests + JaCoCo coverage
│   ├── lint.yml                         # Android lint + Checkstyle
│   └── release.yml                      # Tag-triggered GitHub Release
├── config/checkstyle/checkstyle.xml
├── build.gradle
├── settings.gradle
└── gradle.properties
```

---

## Building

```bash
# Debug build
./gradlew :nethunter-app:assembleDebug

# Release build
./gradlew :nethunter-app:assembleRelease

# Run unit tests
./gradlew :nethunter-app:testDebugUnitTest

# Run lint
./gradlew :nethunter-app:lintDebug
```

---

## Installing

```bash
adb install -r nethunter-app/build/outputs/apk/debug/nethunter-app-debug.apk
```

---

## Architecture

The application targets **API 21–34** (Android 5.0 – Android 14).

- **Language**: Java 11
- **Architecture**: Single-activity with Jetpack Navigation fragments
- **Build system**: Gradle 8 + Android Gradle Plugin 8.1
- **UI**: Material Components 3 (dark Kali Linux theme)
- **Services**: Foreground services with wake locks
- **Testing**: JUnit 4 + Mockito + Robolectric (unit) / Espresso (instrumented)

---

## Permissions

| Permission | Purpose |
|-----------|---------|
| `ACCESS_FINE_LOCATION` | GPS data |
| `ACCESS_MOCK_LOCATION` | Inject mock GPS fix |
| `FOREGROUND_SERVICE` | Long-running chroot service |
| `RECEIVE_BOOT_COMPLETED` | Auto-start on boot |
| `WAKE_LOCK` | Keep CPU active during operations |
| `INTERNET` | Network tools inside chroot |

---

## License

This project is released under the [GNU General Public License v3.0](LICENSE).

> **Disclaimer**: NetHunter is intended for legal security research and authorised penetration testing only. Misuse of this software against systems you do not own or have explicit permission to test is illegal. The authors accept no liability for misuse.