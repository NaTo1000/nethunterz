# Firmware Management Documentation

## Overview

NetHunterZ includes a complete firmware lifecycle management system:

1. **Build** - Compile custom Flipper Zero firmware using ufbt
2. **Validate** - Verify binary integrity and GPG signatures
3. **Sign** - GPG-sign release artifacts
4. **Deploy** - Push firmware to cloud storage (S3/GCS)
5. **Update** - Push firmware to connected Flipper devices

## Building Firmware

### Prerequisites

```bash
pip install ufbt
python -m ufbt update
```

### Build Command

```bash
python firmware/builder/build_firmware.py \
    --version 1.2.3 \
    --config firmware/builder/firmware_config.json \
    --output firmware/build/output
```

### Configuration

Edit `firmware/builder/firmware_config.json` to customize:
- `target` - Device target (`flipper_zero`)
- `custom_apps` - List of custom apps to bundle
- `features` - Enable/disable hardware features
- `signing` - Configure firmware signing

## Validating Firmware

```bash
python firmware/validator/validate_firmware.py \
    --firmware-dir firmware/build/output \
    --version 1.2.3 \
    --verify-signatures
```

The validator checks:
- File size bounds (1 KB - 4 MB)
- ARM Cortex-M4 vector table format
- SHA-256 checksum integrity
- GPG signature validity (if `--verify-signatures` is set)

## Signing Firmware

```bash
# Sign with GPG passphrase
bash security/signing/sign_firmware.sh firmware/build/output "your_passphrase"

# Verify signatures
bash security/signing/verify_firmware.sh firmware/signed/
```

## Android OTA Update

From the Android app:

```java
// Check for updates
CloudDashboardClient client = new CloudDashboardClient(context, dashboardUrl, apiKey);
FirmwareRelease latest = client.getLatestRelease("stable");

// Download firmware
CloudStorageManager storage = new CloudStorageManager(context);
storage.configureS3(s3BucketUrl, apiKey);
storage.downloadFirmware(latest.version, destFile, progressListener);

// Flash to Flipper
FlipperManager flipper = service.getFlipperManager();
flipper.startFirmwareUpdate(destFile.getAbsolutePath());
```

## Autonomous Update Pipeline

The `autonomous_updater.py` script coordinates the CI/CD update flow:

```bash
# Check for updates
python firmware/updater/autonomous_updater.py \
    --check \
    --current-version 1.1.0 \
    --channel stable

# Notify dashboard
python firmware/updater/autonomous_updater.py \
    --notify-dashboard \
    --version 1.2.3 \
    --sha256 abc123...
```

## Rollback

If firmware validation fails after flashing, `FirmwareUpdater` automatically triggers rollback:
1. Device detects failed boot or ping timeout
2. `FirmwareUpdater.rollback()` is called
3. Previous version info from backup is used to re-flash
4. Dashboard is notified of rollback event
