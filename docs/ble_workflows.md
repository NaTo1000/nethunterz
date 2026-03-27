# BLE Workflows – NetHunterZ

## Architecture

```
Android App  ←──BLE GATT──→  NRF Runtime (nrf_module/ble_bridge.py)
                                   │
                                   ├── PingequaDualNRF (capture / replay)
                                   ├── FrequencyManager (channel management)
                                   └── CloudOrchestrator ←──HTTPS──→ Cloud API
```

---

## GATT Services and Characteristics

| UUID suffix | Name | Properties |
|------------|------|------------|
| `def1` | Status | Read, Notify |
| `def2` | Command | Write |
| `def3` | Log Stream | Notify |
| `def4` | Frequency Upgrade | Write, Notify |
| `def5` | Auth | Write |

All UUIDs share prefix `12345678-1234-5678-1234-56789abcde__`.

---

## Authentication Flow

```
App                    Device
 │                       │
 │──── Auth Request ─────▶ (generate challenge)
 │◀─── Challenge ─────────│
 │                         │
 │  compute HMAC-SHA256(secret, challenge)
 │                         │
 │──── Response ──────────▶ (verify HMAC)
 │◀─── Auth OK / Reject ───│
```

**Secret management**: set `NRF_BLE_SECRET` on the device and configure the
matching secret in the Android app's `BleManager`. In production, provision
secrets via the cloud during initial device registration.

---

## Command Payloads (JSON over CHAR_COMMAND)

### Start capture
```json
{"action": "start_capture"}
```

### Stop capture
```json
{"action": "stop_capture"}
```

### Upgrade frequency
```json
{"action": "upgrade_frequency", "module_id": 0, "channel": 110}
```

### Rewrite (replay) last N packets
```json
{"action": "rewrite", "module_id": 1, "count": 10, "delay_ms": 50}
```

---

## Notification Payloads

### Status notification (CHAR_STATUS)
```json
{
  "nrf": {
    "running": true,
    "packet_count": 1024,
    "modules": [
      {"id": 0, "channel": 76, "frequency_mhz": 2476.0},
      {"id": 1, "channel": 100, "frequency_mhz": 2500.0}
    ]
  },
  "cloud": {"running": true},
  "security": {"total_alerts": 0}
}
```

### Packet notification (CHAR_LOG_STREAM)
```json
{
  "channel": 76,
  "frequency_mhz": 2476.0,
  "timestamp": 1711555082.123,
  "rssi": -72,
  "payload": "aabbccdd…",
  "module_id": 0
}
```

### Frequency upgrade notification (CHAR_FREQ_UPGRADE)
```json
{
  "module_id": 0,
  "channel": 110,
  "frequency_mhz": 2510.0,
  "reason": "cloud recommendation"
}
```

---

## Cloud-Initiated Frequency Upgrades

The cloud API server analyses incoming packet telemetry and emits
frequency recommendations when congestion is detected:

1. Device uploads packets → `POST /api/v1/packets`
2. `FrequencyEngine.analyse()` computes channel scores.
3. Recommendation returned in HTTP response or pushed via WebSocket.
4. `CloudOrchestrator._apply_recommendation()` calls `FrequencyManager.apply_cloud_recommendation()`.
5. `FrequencyManager` calls `PingequaDualNRF.upgrade_frequency()` (live, no restart).
6. `BLEBridge.notify_frequency_upgrade()` pushes the event to the Android app.

---

## BLE Security Best Practices

- Never hardcode `NRF_BLE_SECRET` – use environment variables or a secrets manager.
- Rotate the shared secret periodically via the cloud update mechanism.
- The `SecurityMonitor` rate-limits auth attempts (max 5 per minute per device).
- All BLE command writes are validated server-side before execution.
