# Troubleshooting Guide – NetHunterZ

## NRF Module Issues

### Module not detected

**Symptom**: `RF24 library not available – falling back to simulation mode`

**Cause**: The `RF24` Python library is not installed or the SPI device is not enabled.

**Fix**:
```bash
# Enable SPI on Raspberry Pi
sudo raspi-config  # Interface Options → SPI → Enable
# Install RF24
pip install RPi.GPIO spidev
pip install RF24  # or: pip install pyRF24
```

---

### No packets captured

**Symptom**: `packet_count` stays at 0 after starting capture.

**Possible causes**:
1. Wrong channel – no RF activity on the configured channel.
2. Antenna not connected.
3. PA level too low.

**Fix**:
```python
# Run a spectrum scan first
from nrf_module import PingequaDualNRF, FrequencyManager
# ... (see setup.md for full example)
stats = await freq_mgr.scan_spectrum(dwell_time_s=0.2)
best_ch = freq_mgr.select_best_channel()
```

---

### Log file permission error

**Symptom**: `Failed to write log: [Errno 13] Permission denied`

**Fix**:
```bash
mkdir -p /var/log/nethunterz && chown $USER /var/log/nethunterz
python -m nrf_module.runtime --log-dir /var/log/nethunterz
```

---

## BLE Connection Issues

### App can't find device

**Symptom**: Scan completes with no devices found.

**Checklist**:
- BLE adapter is powered on: `bluetoothctl show`
- `NRF_BLE_SECRET` is set on both device and app.
- App has `BLUETOOTH_SCAN` and `ACCESS_FINE_LOCATION` permissions.
- Device is advertising (runtime must be running).

**Check BlueZ service**:
```bash
systemctl status bluetooth
journalctl -u bluetooth -n 50
```

---

### Authentication failure

**Symptom**: `Device xxx failed authentication.` in device log.

**Cause**: The shared secret does not match between device and app.

**Fix**: Ensure `NRF_BLE_SECRET` on the device matches the secret compiled into
the Android app's `BleManager`. Restart both after changing.

---

### Auth rate limit triggered

**Symptom**: `Device xxx exceeded 5 auth attempts per minute.` / BLE keeps
disconnecting and reconnecting.

**Cause**: A mis-configured app or rogue device is repeatedly attempting authentication.

**Fix**:
1. Verify the correct secret is in use.
2. Wait 60 seconds for the rate limit window to expire.
3. Check security audit log for the device ID and block if malicious.

---

## Cloud Connectivity Issues

### `aiohttp not installed`

```bash
pip install aiohttp
```

### SSL / certificate errors

**Symptom**: `CERTIFICATE_VERIFY_FAILED` in cloud upload logs.

**Fix**:
```bash
# Use mTLS – provide cert/key paths
export CLOUD_TLS_CERT=/path/to/client.crt
export CLOUD_TLS_KEY=/path/to/client.key
```

Or disable certificate verification in dev only:
```python
# CloudConfig(tls_cert=None)  # uses default SSL context
```

### Cloud recommendations not arriving

**Checklist**:
1. `CLOUD_ENDPOINT` is set and reachable from the device.
2. `CLOUD_API_KEY` is correct.
3. At least `batch_size` (default: 50) packets have been captured.
4. The `FrequencyEngine` needs `MIN_SAMPLES_TO_RECOMMEND` (3) observations per channel.

---

## Flipper Board Issues

### `fbt not found`

```bash
# Install Flipper Build Tool
git clone --recursive https://github.com/flipperdevices/flipperzero-firmware.git
cd flipperzero-firmware
./fbt  # bootstraps the toolchain
```

### Firmware flash fails

**Symptom**: `Flash failed` in `AIFirmwareUpdater` logs.

**Fix**:
1. Ensure the Flipper is connected and `FLIPPER_PORT` is correct.
2. Manually test: `python -c "import serial; print('ok')"`
3. Check USB permissions: `sudo usermod -aG dialout $USER && newgrp dialout`

### Post-flash version mismatch → rollback triggered

This is expected behaviour when the flashed firmware reports a different
version string. To debug:
```python
info = await flipper.get_info()
print(info.firmware_version)
```
Ensure the `FirmwareRelease.version` exactly matches the string returned by
the device after flashing.

---

## CI/CD Pipeline Failures

### `pytest` collection errors

```bash
pip install pytest pytest-asyncio
pytest --collect-only  # check for import errors
```

### `flake8` errors (E501 line too long)

The CI allows lines up to 100 characters. Fix locally:
```bash
flake8 nrf_module/ cloud/ flipper/ --max-line-length=100
```

### Android Gradle build fails

```bash
cd android_app
./gradlew dependencies  # verify deps resolve
./gradlew assembleDebug --info 2>&1 | tail -50
```
