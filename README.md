# NetHunterZ

An Android application for NetHunter — providing chroot GPS support, boot services, utility shell execution, and supporting scripts for the Kali NetHunter penetration-testing platform.

## Project Structure

```
nethunter-app/
  src/main/
    AndroidManifest.xml          ← Permissions & component declarations
    java/com/offsec/nethunter/
      MainActivity.java          ← App entry point
      GPS/
        NMEAHandler.java         ← Parses NMEA sentences for chroot GPS
        GpsService.java          ← Foreground service streaming GPS to chroot
      updateReceiver/
        BootReceiver.java        ← Starts NethunterService on BOOT_COMPLETED
      service/
        NethunterService.java    ← Background service (start/stop chroot)
      utils/
        RootUtils.java           ← Root shell command execution
        NethunterPaths.java      ← Path constants (chroot, scripts, nh_files)
        SystemUtils.java         ← Package/network/version helpers
    res/
      layout/activity_main.xml  ← Main activity layout
      menu/main_menu.xml         ← App toolbar menu
      values/strings.xml         ← String resources
      values/colors.xml          ← Color palette
      values/themes.xml          ← Material theme
    assets/
      scripts/bootkali           ← Chroot bootstrap script
      scripts/check_services.sh  ← Service status checker
      etc.init.d/99nethunter     ← Init.d startup script
      nh_files/configs/          ← App config files (copied to sdcard)
      nh_files/duckscripts/      ← Default Ducky Script payloads
      nh_files/modules/keyseed.py← HID keyboard seed generator
```

## Building

### Prerequisites
- JDK 11+
- Android SDK (API 33)

### Debug build
```bash
./gradlew assembleDebug
```

### Run unit tests
```bash
./gradlew test
```

### Lint
```bash
./gradlew lint
```

## CI/CD

GitHub Actions workflows are defined in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `build.yml` | push/PR → `main` | Compile & upload debug APK |
| `lint.yml` | push/PR | Android lint checks |
| `test.yml` | push/PR | JUnit unit tests |
| `release.yml` | push tag `v*` | Build release APK & create GitHub Release |

## License

Apache 2.0
