# Flipper Zero Integration Guide

## Overview

NetHunterZ integrates with the Flipper Zero multi-tool via three transport methods:

| Method | Class | Speed | Notes |
|---|---|---|---|
| USB CDC | `FlipperUSBDriver` | Fast | Preferred; VID=0x0483, PID=0x5740 |
| UART Serial | `FlipperUARTDriver` | Medium | `/dev/ttyACM0` at 115200 baud |
| Bluetooth SPP | `FlipperBluetoothDriver` | Slower | Requires pairing first |

## Connection Priority

The `FlipperManager.tryAutoConnect()` method tries connections in this order:
1. USB (most reliable, lowest latency)
2. UART (direct serial, requires root)
3. Bluetooth (wireless, highest latency)

## USB Connection

The Flipper Zero exposes a CDC ACM USB interface when connected via USB-C.

**Permissions:** The app requests USB permission via `UsbManager`. The `AndroidManifest.xml` includes an intent filter for `USB_DEVICE_ATTACHED` with the Flipper's VID/PID.

```java
FlipperManager manager = new FlipperManager(context);
manager.addConnectionListener(new FlipperManager.ConnectionListener() {
    @Override
    public void onConnected(FlipperManager.ConnectionType type) {
        // Connection established
    }
    // ...
});
boolean connected = manager.connect(FlipperManager.ConnectionType.USB);
```

## UART Connection

Requires root access to set permissions on `/dev/ttyACM0`.

```java
boolean connected = manager.connect(FlipperManager.ConnectionType.UART);
```

The driver automatically configures the port with `stty`:
```
stty -F /dev/ttyACM0 115200 cs8 -cstopb -parenb raw -echo
```

## Bluetooth Connection

Pair the Flipper Zero in Android Settings first. The driver searches for devices named "Flipper *".

```java
boolean connected = manager.connect(FlipperManager.ConnectionType.BLUETOOTH);
```

## CLI Commands

Once connected, use `FlipperProtocol.sendCliCommand()` to send CLI commands:

```java
String version  = protocol.sendCliCommand("version");
String storage  = protocol.sendCliCommand("storage info /");
boolean alive   = protocol.ping();
```

## Firmware Updates

Use `FirmwareUpdater` to push firmware over the active connection:

```java
FirmwareUpdater updater = new FirmwareUpdater(context);
updater.addListener(new FirmwareUpdater.UpdateListener() {
    @Override
    public void onProgress(int percent) {
        progressBar.setProgress(percent);
    }
    // ...
});
updater.startUpdate("/sdcard/nethunter/firmware/flipper.bin", protocol);
```
