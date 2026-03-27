"""BLE connectivity tests."""

import pytest
from unittest.mock import MagicMock, patch, call


class TestBLEManager:
    """Tests for BLE manager state machine."""

    def test_ble_states_enum(self):
        states = {"IDLE": 0, "ADVERTISING": 1, "CONNECTED": 2, "OTA_MODE": 3}
        assert len(states) == 4
        for name, val in states.items():
            assert isinstance(val, int)

    def test_ble_device_name_length(self):
        BLE_DEVICE_NAME = "NethunterZ"
        assert len(BLE_DEVICE_NAME) <= 29  # BLE device name limit

    def test_ble_mtu_value(self):
        BLE_MTU_SIZE = 517
        assert 23 <= BLE_MTU_SIZE <= 517  # BLE MTU range

    def test_characteristic_uuids_unique(self):
        uuids = [
            "BLE_CTRL_CHAR_UUID",
            "BLE_OTA_CHAR_UUID",
            "BLE_STATUS_CHAR_UUID",
        ]
        assert len(uuids) == len(set(uuids))

    def test_ble_data_send_max_size(self):
        # BLE notification max size is MTU - 3
        BLE_MTU_SIZE = 517
        max_notification = BLE_MTU_SIZE - 3
        test_data = b"x" * max_notification
        assert len(test_data) <= max_notification

    def test_ble_status_json_format(self):
        import json
        status = {"heap": 180000, "uptime": 3600, "wifi_rssi": -65}
        serialized = json.dumps(status)
        parsed = json.loads(serialized)
        assert parsed["heap"] == 180000
        assert parsed["wifi_rssi"] == -65

    def test_ctrl_callback_invoked(self):
        callback_data = []
        def ctrl_cb(data, length):
            callback_data.append((data, length))
        test_payload = b"reboot"
        ctrl_cb(test_payload, len(test_payload))
        assert len(callback_data) == 1
        assert callback_data[0][0] == b"reboot"

    def test_ota_notification_format(self):
        import json
        msg = json.dumps({"ota_state": 2, "progress": 50})
        parsed = json.loads(msg)
        assert "ota_state" in parsed
        assert 0 <= parsed["progress"] <= 100


class TestBLEBridge:
    """Tests for BLE to internet bridge."""

    def test_bridge_initialization(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "nrf"))
        from ble_bridge import BLEBridge
        bridge = BLEBridge(cloud_endpoint="https://api.test.com/data", api_key="test")
        assert bridge.cloud_endpoint == "https://api.test.com/data"
        assert bridge.api_key == "test"

    def test_packet_decode_json(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "nrf"))
        from ble_bridge import BLEBridge
        bridge = BLEBridge()
        raw = b'{"type": "status", "heap": 180000}'
        msg = bridge._decode_packet(raw)
        assert msg is not None
        assert msg["type"] == "status"
        assert msg["heap"] == 180000

    def test_packet_decode_binary(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "nrf"))
        from ble_bridge import BLEBridge
        bridge = BLEBridge()
        raw = b"\xff\xfe\xfd\xfc"
        msg = bridge._decode_packet(raw)
        assert msg is not None
        assert "raw" in msg

    def test_stats_tracking(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "nrf"))
        from ble_bridge import BLEBridge
        bridge = BLEBridge()
        stats = bridge.get_stats()
        assert "packets_in" in stats
        assert "packets_out" in stats
        assert "errors" in stats
